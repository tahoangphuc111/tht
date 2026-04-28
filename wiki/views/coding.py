"""Views for the coding exercise feature."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, UpdateView, CreateView

from ..forms import CodingExerciseForm, CodingTestCaseForm
from ..models import Article, CodingExercise, CodingTestCase, CodingSubmission
from ..services.code_runner import (
    CodeRunnerError,
    execute_code,
    get_all_language_status,
    get_enabled_language_choices,
    serialize_submission,
)
from ..utils import can_manage_wiki


def _get_article_for_manage(article_pk):
    """Retrieve an article that can host a coding exercise."""
    return get_object_or_404(Article, pk=article_pk)


def _can_manage_exercise(user, article):
    """Check if the current user can configure coding exercises."""
    return can_manage_wiki(user) or article.author == user


class CodingAuthorRequiredMixin(UserPassesTestMixin):
    """Restrict testcase management to article owners and wiki managers."""

    def _get_article(self):
        if hasattr(self, "object") and self.object:
            return self.object.exercise.article
        exercise = get_object_or_404(CodingExercise, pk=self.kwargs["exercise_pk"])
        return exercise.article

    def test_func(self):
        """Validate permissions."""
        return _can_manage_exercise(self.request.user, self._get_article())

    def handle_no_permission(self):
        """Redirect unauthorized users back to the article page."""
        article = self._get_article()
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)


@login_required
def article_coding_manage_view(request, article_pk):
    """Create/update the coding exercise configuration for an article."""
    article = _get_article_for_manage(article_pk)
    if not _can_manage_exercise(request.user, article):
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)

    defaults = {
        "title": article.title,
        "is_enabled": True,
        "allowed_languages": [item["key"] for item in get_enabled_language_choices()],
        "default_language": (
            get_enabled_language_choices()[0]["key"]
            if get_enabled_language_choices()
            else ""
        ),
    }
    exercise, _ = CodingExercise.objects.get_or_create(article=article, defaults=defaults)

    if request.method == "POST":
        form = CodingExerciseForm(request.POST, instance=exercise)
        if form.is_valid():
            exercise = form.save()
            messages.success(request, "Đã cập nhật bài tập code.")
            return redirect("wiki:article-coding-manage", article_pk=article.pk)
    else:
        form = CodingExerciseForm(instance=exercise)

    return render(
        request,
        "wiki/coding_manage.html",
        {
            "article": article,
            "exercise": exercise,
            "form": form,
            "testcases": exercise.testcases.all(),
            "all_languages": get_all_language_status(),
        },
    )


class CodingTestCaseCreateView(LoginRequiredMixin, CodingAuthorRequiredMixin, CreateView):
    """Create a testcase for a coding exercise."""

    model = CodingTestCase
    form_class = CodingTestCaseForm
    template_name = "wiki/coding_testcase_form.html"

    def get_context_data(self, **kwargs):
        """Add the current article and exercise to template context."""
        context = super().get_context_data(**kwargs)
        context["exercise"] = get_object_or_404(CodingExercise, pk=self.kwargs["exercise_pk"])
        context["article"] = context["exercise"].article
        return context

    def form_valid(self, form):
        """Attach the testcase to the selected exercise."""
        exercise = get_object_or_404(CodingExercise, pk=self.kwargs["exercise_pk"])
        form.instance.exercise = exercise
        messages.success(self.request, "Đã thêm testcase.")
        return super().form_valid(form)

    def get_success_url(self):
        """Return to the coding management page."""
        return reverse(
            "wiki:article-coding-manage",
            kwargs={"article_pk": self.object.exercise.article.pk},
        )


class CodingTestCaseUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edit a coding testcase."""

    model = CodingTestCase
    form_class = CodingTestCaseForm
    template_name = "wiki/coding_testcase_form.html"

    def test_func(self):
        """Validate edit permissions."""
        return _can_manage_exercise(self.request.user, self.get_object().exercise.article)

    def handle_no_permission(self):
        """Redirect unauthorized users back to article detail."""
        article = self.get_object().exercise.article
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)

    def get_context_data(self, **kwargs):
        """Expose article and exercise in the template."""
        context = super().get_context_data(**kwargs)
        context["exercise"] = self.object.exercise
        context["article"] = self.object.exercise.article
        return context

    def form_valid(self, form):
        """Add a success flash after updating."""
        messages.success(self.request, "Đã cập nhật testcase.")
        return super().form_valid(form)

    def get_success_url(self):
        """Return to the coding management page."""
        return reverse(
            "wiki:article-coding-manage",
            kwargs={"article_pk": self.object.exercise.article.pk},
        )


class CodingTestCaseDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete a coding testcase."""

    model = CodingTestCase
    template_name = "wiki/coding_testcase_confirm_delete.html"

    def test_func(self):
        """Validate delete permissions."""
        return _can_manage_exercise(self.request.user, self.get_object().exercise.article)

    def handle_no_permission(self):
        """Redirect unauthorized users back to article detail."""
        article = self.get_object().exercise.article
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)

    def get_context_data(self, **kwargs):
        """Expose article and exercise in the template."""
        context = super().get_context_data(**kwargs)
        context["exercise"] = self.object.exercise
        context["article"] = self.object.exercise.article
        return context

    def delete(self, request, *args, **kwargs):
        """Show a message after deleting the testcase."""
        messages.success(request, "Đã xóa testcase.")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        """Return to the coding management page."""
        return reverse(
            "wiki:article-coding-manage",
            kwargs={"article_pk": self.object.exercise.article.pk},
        )


@require_POST
@login_required
def run_code_view(request, article_pk):
    """Run code against custom input or sample testcases."""
    article = get_object_or_404(Article, pk=article_pk)
    exercise = get_object_or_404(CodingExercise, article=article, is_enabled=True)
    try:
        payload = json.loads(request.body)
        language = payload.get("language", "")
        source_code = payload.get("source_code", "")
        custom_input = payload.get("custom_input", "")
        submission = execute_code(
            exercise,
            request.user,
            language,
            source_code,
            custom_input=custom_input,
            sample_only=not bool(custom_input),
        )
        return JsonResponse(serialize_submission(submission))
    except CodeRunnerError as error:
        return JsonResponse({"success": False, "message": str(error)}, status=400)
    except Exception as error:  # pylint: disable=broad-exception-caught
        return JsonResponse({"success": False, "message": str(error)}, status=500)


@require_POST
@login_required
def submit_code_view(request, article_pk):
    """Judge code against all configured testcases."""
    article = get_object_or_404(Article, pk=article_pk)
    exercise = get_object_or_404(CodingExercise, article=article, is_enabled=True)
    try:
        payload = json.loads(request.body)
        language = payload.get("language", "")
        source_code = payload.get("source_code", "")
        submission = execute_code(exercise, request.user, language, source_code)
        return JsonResponse(serialize_submission(submission))
    except CodeRunnerError as error:
        return JsonResponse({"success": False, "message": str(error)}, status=400)
    except Exception as error:  # pylint: disable=broad-exception-caught
        return JsonResponse({"success": False, "message": str(error)}, status=500)


@login_required
def submission_status_view(request, submission_pk):
    """Get the current status of a submission for polling."""
    submission = get_object_or_404(CodingSubmission, pk=submission_pk, user=request.user)
    return JsonResponse(serialize_submission(submission))
