from django.shortcuts import render
from django.db.models import Q, Case, When, IntegerField
from ..models import Article


def search_view(request):
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        results = Article.objects.filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(tags__name__icontains=query),
            status='published'
        ).distinct().annotate(
            rank=Case(
                When(title__icontains=query, then=3),
                When(tags__name__icontains=query, then=2),
                When(content__icontains=query, then=1),
                default=0,
                output_field=IntegerField(),
            )
        ).order_by('-rank', '-created_at').select_related('author', 'category')
    context = {
        'query': query,
        'results': results,
        'count': results.count() if results else 0
    }
    return render(request, 'wiki/search_results.html', context)
