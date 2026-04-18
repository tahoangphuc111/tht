"""
Utility functions for the wiki application.
"""

from collections import defaultdict
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import ArticleRevision

User = get_user_model()


def save_article_revision(article, user, change_summary):
    """Save a snapshot of an article for revision history."""
    ArticleRevision.objects.create(
        article=article,
        title=article.title,
        content=article.content,
        author=user,
        change_summary=change_summary,
    )


def can_publish_articles(user):
    """Check if the user has permission to publish or edit articles."""
    publisher_roles = ["admin", "editor", "contributor"]
    return user.is_authenticated and (
        user.is_superuser
        or user.groups.filter(name__in=publisher_roles).exists()
        or user.has_perm("wiki.add_article")
    )


def get_profile_name(user):
    """Return a displayable name for the user."""
    return user.profile.display_name or user.get_full_name() or user.username


def build_profile_stats(user, viewer=None):
    """Generate statistics and contribution data for a user's profile."""
    articles = list(user.articles.select_related("category").order_by("-updated_at"))
    now = timezone.localdate()
    start_date = now - timedelta(days=83)
    contribution_map = defaultdict(int)

    for article in articles:
        c_day = timezone.localtime(article.created_at).date()
        if c_day >= start_date:
            contribution_map[c_day] += 1
        u_day = timezone.localtime(article.updated_at).date()
        if u_day >= start_date and u_day != c_day:
            contribution_map[u_day] += 1

    contribution_days = []
    curr = start_date
    while curr <= now:
        count = contribution_map[curr]
        contribution_days.append({"date": curr, "count": count, "level": min(count, 4)})
        curr += timedelta(days=1)

    # Permission check for private profile
    is_owner = viewer == user
    is_admin = viewer and viewer.is_superuser
    can_view = not user.profile.is_profile_private or is_owner or is_admin

    return {
        "profile_user": user,
        "profile_name": get_profile_name(user),
        "can_view_profile": can_view,
        "recent_articles": articles,
        "article_count": len(articles),
        "contribution_days": contribution_days,
        "total_contributions": sum(d["count"] for d in contribution_days),
        "user_vote_score": user.profile.vote_score,
        "role_names": [g.name for g in user.groups.all()] or ["user"],
        "edited_articles_count": ArticleRevision.objects.filter(author=user)
        .values("article")
        .distinct()
        .count(),
        "comment_count": user.comments.count(),
        "total_users": User.objects.count(),
    }
