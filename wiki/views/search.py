from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from ..models import Article


def search_view(request):
    """Global search view for articles."""
    query = request.GET.get('q', '').strip()
    results_list = []

    if query:
        results_list = Article.objects.filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(tags__name__icontains=query),
            status='published'
        ).distinct().select_related('author', 'category')

    count = results_list.count() if results_list else 0

    # Paginate results
    page = request.GET.get('page', 1)
    paginator = Paginator(results_list or [], 10)  # Paginate by 10 articles per page
    try:
        results = paginator.page(page)
    except PageNotAnInteger:
        results = paginator.page(1)
    except EmptyPage:
        results = paginator.page(paginator.num_pages)

    context = {
        'query': query,
        'results': results,
        'count': count,
        'page_obj': results,
        'is_paginated': results.has_other_pages() if results else False,
    }
    return render(request, 'wiki/search_results.html', context)
