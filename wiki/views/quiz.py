"""
Views for handling quizzes related to articles.
"""

import json
import logging
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.views.generic import CreateView, UpdateView, DeleteView
from ..forms import ChoiceFormSet, QuestionForm, extract_quiz_text
from ..models import Article, Question

logger = logging.getLogger(__name__)


@login_required
def article_quiz_manage_view(request, article_pk):
    """View to manage questions for an article's quiz."""
    article = get_object_or_404(Article, pk=article_pk)
    if article.author != request.user and not request.user.is_superuser:
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)
    return render(request, "wiki/quiz_manage.html", {
        "article": article,
        "questions": article.questions.all().prefetch_related('choices')
    })


@login_required
@require_POST
def submit_quiz_view(request, article_pk):
    """Handle submission and grading of a quiz."""
    try:
        data = json.loads(request.body)
        answers = data.get("answers", {})
        article = get_object_or_404(Article, pk=article_pk)
        if article.status != "published" and article.author != request.user and not request.user.is_superuser:
            return JsonResponse({"success": False, "message": "Unauthorized"}, status=403)

        questions = article.questions.all()
        correct_count = 0
        results = {}

        for question in questions:
            ans_id = answers.get(str(question.pk))
            correct_choice = question.choices.filter(is_correct=True).first()
            is_correct = (
                str(correct_choice.pk) == str(ans_id)
                if correct_choice and ans_id
                else False
            )
            if is_correct:
                correct_count += 1
            results[question.pk] = {
                "is_correct": is_correct,
                "explanation": question.explanation,
                "correct_choice_id": (correct_choice.pk if correct_choice else None),
            }
        return JsonResponse(
            {
                "success": True,
                "correct_count": correct_count,
                "total_questions": questions.count(),
                "results": results,
            }
        )
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.exception("Error grading quiz for article %s", article_pk)
        return JsonResponse({"success": False, "message": str(error)}, status=400)


@login_required
def upload_quiz_file_view(request, article_pk):
    """View to upload a file containing quiz questions."""
    article = get_object_or_404(Article, pk=article_pk)
    if article.author != request.user and not request.user.is_superuser:
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)

    if request.method == "POST":
        upload = request.FILES.get("quiz_file")
        if not upload:
            messages.error(request, "Vui lòng chọn file câu hỏi.")
            return render(request, "wiki/quiz_upload.html", {"article": article})

        try:
            text = extract_quiz_text(upload)
            if not text or len(text.strip()) < 50:
                messages.error(request, "Nội dung file quá ngắn hoặc không thể đọc được. Vui lòng kiểm tra lại file.")
                return render(request, "wiki/quiz_upload.html", {"article": article})
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to extract quiz file for article %s", article_pk)
            messages.error(request, f"Không thể đọc file: {error}")
            return render(request, "wiki/quiz_upload.html", {"article": article})

        blocks = [
            block.strip()
            for block in text.replace("\r\n", "\n").split("\n\n")
            if len(block.strip()) > 10
        ]

        if not blocks:
            messages.error(request, "File không đúng định dạng yêu cầu (cần phân tách các câu hỏi bằng 2 lần xuống dòng).")
            return render(request, "wiki/quiz_upload.html", {"article": article})

        start_order = article.questions.count()
        Question.objects.bulk_create(
            [
                Question(article=article, content=block, order=start_order + index + 1)
                for index, block in enumerate(blocks)
            ]
        )
        messages.success(request, f"Đã nhập {len(blocks)} câu hỏi từ file.")
        return redirect("wiki:article-quiz-manage", article_pk=article.pk)

    return render(request, "wiki/quiz_upload.html", {"article": article})


class QuizAuthorRequiredMixin(UserPassesTestMixin):
    """Restrict quiz editing to article owners and superusers."""

    def _get_article(self):
        if hasattr(self, "object") and self.object:
            return self.object.article

        # Priority 1: article_pk from URL
        article_pk = self.kwargs.get("article_pk")
        if article_pk:
            return get_object_or_404(Article, pk=article_pk)

        # Priority 2: pk of the question object
        pk = self.kwargs.get("pk")
        if pk:
            question = get_object_or_404(Question, pk=pk)
            return question.article

        raise AttributeError("Article context not found.")

    def test_func(self):
        """Check if the current user can manage the quiz."""
        try:
            article = self._get_article()
            return article.author == self.request.user or self.request.user.is_superuser
        except Exception:
            return False

    def handle_no_permission(self):
        """Redirect unauthorized users to the article detail page."""
        article = self._get_article()
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)


class QuestionCreateView(LoginRequiredMixin, QuizAuthorRequiredMixin, CreateView):
    model = Question
    form_class = QuestionForm
    template_name = 'wiki/question_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = get_object_or_404(Article, pk=self.kwargs['article_pk'])
        context['article'] = article
        if self.request.POST:
            context['choice_formset'] = ChoiceFormSet(self.request.POST, self.request.FILES)
        else:
            context['choice_formset'] = ChoiceFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        choice_formset = context['choice_formset']
        if form.is_valid() and choice_formset.is_valid():
            article = get_object_or_404(Article, pk=self.kwargs['article_pk'])
            form.instance.article = article
            self.object = form.save()
            choice_formset.instance = self.object
            choice_formset.save()
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse("wiki:article-quiz-manage", kwargs={"article_pk": self.kwargs['article_pk']})


class QuestionUpdateView(LoginRequiredMixin, QuizAuthorRequiredMixin, UpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'wiki/question_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['article'] = self.object.article
        if self.request.POST:
            context['choice_formset'] = ChoiceFormSet(
                self.request.POST,
                self.request.FILES,
                instance=self.object,
            )
        else:
            context['choice_formset'] = ChoiceFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        choice_formset = context['choice_formset']
        if form.is_valid() and choice_formset.is_valid():
            self.object = form.save()
            choice_formset.instance = self.object
            choice_formset.save()
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse("wiki:article-quiz-manage", kwargs={"article_pk": self.object.article.pk})


class QuestionDeleteView(LoginRequiredMixin, QuizAuthorRequiredMixin, DeleteView):
    model = Question
    template_name = 'wiki/question_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['article'] = self.object.article
        return context

    def get_success_url(self):
        return reverse("wiki:article-quiz-manage", kwargs={"article_pk": self.object.article.pk})
