from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from .models import ArticleRevision

def save_article_revision(article, user, change_summary):
    ArticleRevision.objects.create(
        article=article, title=article.title, content=article.content,
        author=user, change_summary=change_summary
    )

def can_publish_articles(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=['admin', 'editor', 'contributor']).exists()
        or user.has_perm('wiki.add_article')
    )

def get_profile_name(user):
    return user.profile.display_name or user.get_full_name() or user.username

def build_profile_stats(user):
    articles = list(user.articles.select_related('category').order_by('-updated_at'))
    now = timezone.localdate()
    start_date = now - timedelta(days=83)
    contribution_map = defaultdict(int)

    for article in articles:
        c_day = timezone.localtime(article.created_at).date()
        if c_day >= start_date: contribution_map[c_day] += 1
        u_day = timezone.localtime(article.updated_at).date()
        if u_day >= start_date and u_day != c_day: contribution_map[u_day] += 1

    contribution_days = []
    curr = start_date
    while curr <= now:
        count = contribution_map[curr]
        contribution_days.append({'date': curr, 'count': count, 'level': min(count, 4)})
        curr += timedelta(days=1)

    return {
        'articles': articles,
        'article_count': len(articles),
        'contribution_days': contribution_days,
        'total_contributions': sum(d['count'] for d in contribution_days),
    }
