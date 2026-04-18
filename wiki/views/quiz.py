"""
Views for handling quizzes related to articles.
"""

import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from ..models import Article


@login_required
def article_quiz_manage_view(request, article_pk):
    """View to manage questions for an article's quiz."""
    article = get_object_or_404(Article, pk=article_pk)
    if article.author != request.user and not request.user.is_superuser:
        return redirect("wiki:article-detail", pk=article.pk, slug=article.slug)
    return render(request, "wiki/quiz_manage.html", {"article": article})


@login_required
@require_POST
def submit_quiz_view(request, article_pk):
    """Handle submission and grading of a quiz."""
    try:
        data = json.loads(request.body)
        answers = data.get("answers", {})
        article = get_object_or_404(Article, pk=article_pk)
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
        return JsonResponse({"success": False, "message": str(error)}, status=400)
