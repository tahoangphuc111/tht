from django.shortcuts import render
from django.db.models import Q
from ..models import Article


def search_view(request):
    """Global search view for articles."""
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        # Search in title, content, and tags
        results = Article.objects.filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(tags__name__icontains=query),
            status='published'
        ).distinct().select_related('author', 'category')

    context = {
        'query': query,
        'results': results,
        'count': results.count() if results else 0
    }
    return render(request, 'wiki/search_results.html', context)
