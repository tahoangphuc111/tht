import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from ..models import Article, Question, Choice

@login_required
def article_quiz_manage_view(request, article_pk):
    a = get_object_or_404(Article, pk=article_pk)
    if a.author != request.user and not request.user.is_superuser:
        return redirect('wiki:article-detail', pk=a.pk, slug=a.slug)
    return render(request, 'wiki/quiz_manage.html', {'article': a})

@login_required
@require_POST
def submit_quiz_view(request, article_pk):
    try:
        data = json.loads(request.body)
        answers = data.get('answers', {})
        article = get_object_or_404(Article, pk=article_pk)
        qs = article.questions.all()
        correct = 0; results = {}
        for q in qs:
            ans_id = answers.get(str(q.pk))
            correct_choice = q.choices.filter(is_correct=True).first()
            is_correct = str(correct_choice.pk) == str(ans_id) if correct_choice and ans_id else False
            if is_correct: correct += 1
            results[q.pk] = {
                'is_correct': is_correct,
                'explanation': q.explanation,
                'correct_choice_id': correct_choice.pk if correct_choice else None
            }
        return JsonResponse({'success': True, 'correct_count': correct, 'total_questions': qs.count(), 'results': results})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
