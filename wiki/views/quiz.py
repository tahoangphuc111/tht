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
from ..models import Article, Question, Choice
from django.db import transaction

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

        questions = article.questions.all().prefetch_related("choices")
        correct_count = 0
        results = {}

        from ..models import UserAnswer
        from ..signals import check_badges

        with transaction.atomic():
            # Prefetch existing answers to avoid database queries in the loop
            existing_answers = {
                ua.question_id: ua
                for ua in UserAnswer.objects.filter(user=request.user, question__in=questions)
            }
            answers_to_create = []
            answers_to_update = []

            for question in questions:
                ans_id = answers.get(str(question.pk))
                # Look up correct choice in-memory (using prefetched choices)
                choices_list = list(question.choices.all())
                correct_choice = next((c for c in choices_list if c.is_correct), None)
                is_correct = (
                    str(correct_choice.pk) == str(ans_id)
                    if correct_choice and ans_id
                    else False
                )
                if is_correct:
                    correct_count += 1

                if ans_id:
                    # Look up selected choice in-memory (using prefetched choices)
                    selected_choice = next((c for c in choices_list if str(c.pk) == str(ans_id)), None)
                    if selected_choice:
                        ua = existing_answers.get(question.pk)
                        if ua:
                            if ua.selected_choice_id != selected_choice.pk:
                                ua.selected_choice = selected_choice
                                answers_to_update.append(ua)
                        else:
                            answers_to_create.append(
                                UserAnswer(user=request.user, question=question, selected_choice=selected_choice)
                            )

                from martor.utils import markdownify
                results[question.pk] = {
                    "is_correct": is_correct,
                    "explanation": markdownify(question.explanation) if question.explanation else "",
                    "correct_choice_id": (correct_choice.pk if correct_choice else None),
                }

            if answers_to_create:
                UserAnswer.objects.bulk_create(answers_to_create)
            if answers_to_update:
                UserAnswer.objects.bulk_update(answers_to_update, ["selected_choice"])

        # Check and award badges after saving answers
        check_badges(request.user)

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


def parse_question_block(block):
    """
    Parses a single block text into:
    {
        "question_text": str,
        "choices": [{"content": str, "is_correct": bool}, ...],
        "explanation": str
    }
    """
    import re
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return None

    question_lines = []
    raw_choices = []  # list of tuples (key, content, is_correct)
    correct_key = None
    explanation_lines = []
    in_explanation = False

    for line in lines:
        lower_line = line.lower()

        # Check for explanation
        if lower_line.startswith("giải thích:") or lower_line.startswith("explanation:"):
            in_explanation = True
            parts = line.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                explanation_lines.append(parts[1].strip())
            continue

        if in_explanation:
            explanation_lines.append(line)
            continue

        # Check for answer key line: e.g. "Đáp án: A"
        ans_match = re.match(
            r'^(đáp án|đáp án đúng|dap an|dap an dung|answer|correct|key)\s*:\s*([A-Z]|[a-z]|\*|\+)\b',
            line,
            re.IGNORECASE
        )
        if ans_match:
            correct_key = ans_match.group(2).upper()
            continue

        # Check if it is a choice line starting with A., B., C., D. etc. (with optional correct marker * or +)
        choice_match = re.match(
            r'^(\*|\+|\[x\]|\[X\]|\[\s*\])?\s*([A-Z]|[a-z])[\.\)]\s*(.*)',
            line
        )
        if choice_match:
            marker = choice_match.group(1)
            key = choice_match.group(2).upper()
            content = choice_match.group(3).strip()
            is_correct = bool(marker and marker in ('*', '+', '[x]', '[X]'))
            raw_choices.append((key, content, is_correct))
            continue

        # Fallback choice lines starting with "-" or "+"
        fallback_choice_match = re.match(r'^([\-\+])\s*(.*)', line)
        if fallback_choice_match:
            marker = fallback_choice_match.group(1)
            content = fallback_choice_match.group(2).strip()
            is_correct = (marker == '+')
            raw_choices.append((None, content, is_correct))
            continue

        if raw_choices:
            key, prev_content, is_correct = raw_choices[-1]
            raw_choices[-1] = (key, prev_content + " " + line, is_correct)
        else:
            question_lines.append(line)

    final_choices = []
    has_any_correct = False

    for key, content, is_correct in raw_choices:
        if correct_key and key == correct_key:
            is_correct = True
        if is_correct:
            has_any_correct = True
        final_choices.append({"content": content, "is_correct": is_correct})

    if final_choices and not has_any_correct:
        final_choices[0]["is_correct"] = True

    return {
        "question_text": "\n".join(question_lines).strip(),
        "choices": final_choices,
        "explanation": "\n".join(explanation_lines).strip()
    }


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

        # Validate file extension and size
        from pathlib import Path
        allowed_extensions = {".pdf", ".docx", ".txt"}
        file_ext = Path(upload.name).suffix.lower()
        if file_ext not in allowed_extensions:
            messages.error(request, "Chỉ hỗ trợ file PDF, DOCX hoặc TXT.")
            return render(request, "wiki/quiz_upload.html", {"article": article})

        if upload.size > 15 * 1024 * 1024:
            messages.error(request, "File quá lớn. Vui lòng upload tối đa 15MB.")
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
        questions_created = 0

        try:
            with transaction.atomic():
                for index, block in enumerate(blocks):
                    parsed = parse_question_block(block)
                    if not parsed:
                        continue

                    content_text = parsed["question_text"] or block
                    question = Question.objects.create(
                        article=article,
                        content=content_text,
                        explanation=parsed["explanation"],
                        order=start_order + questions_created + 1
                    )

                    for choice_data in parsed["choices"]:
                        Choice.objects.create(
                            question=question,
                            content=choice_data["content"],
                            is_correct=choice_data["is_correct"]
                        )
                    questions_created += 1

            messages.success(request, f"Đã nhập {questions_created} câu hỏi từ file.")
        except Exception as e:
            logger.exception("Failed to save parsed quiz questions for article %s", article_pk)
            messages.error(request, f"Lỗi lưu câu hỏi vào cơ sở dữ liệu: {e}")
            return render(request, "wiki/quiz_upload.html", {"article": article})

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


@login_required
def quiz_take_view(request, article_pk):
    """View for taking the quiz of an article."""
    from django.db.models import Count, Q
    article = get_object_or_404(Article, pk=article_pk)
    if article.status != "published" and article.author != request.user and not request.user.is_superuser:
        return redirect("wiki:home")

    quiz_questions = article.questions.prefetch_related("choices").annotate(
        correct_count=Count("choices", filter=Q(choices__is_correct=True))
    ).filter(correct_count__gt=0)

    if not quiz_questions.exists():
        messages.error(request, "Bài viết này chưa có câu hỏi trắc nghiệm.")
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)

    return render(request, "wiki/quiz_take.html", {
        "article": article,
        "quiz_questions": quiz_questions,
    })
