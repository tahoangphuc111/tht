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


def can_manage_wiki(user):
    """Check if the user has administrative permissions for the wiki."""
    return user.is_authenticated and (
        user.is_superuser or user.has_perm("wiki.manage_all_articles")
    )


def get_profile_name(user):
    """Return a displayable name for the user."""
    return user.profile.display_name or user.get_full_name() or user.username


def build_profile_stats(user, viewer=None):
    """Generate statistics and contribution data for a user's profile."""
    articles = list(user.articles.select_related("category").order_by("-updated_at"))
    revisions = ArticleRevision.objects.filter(author=user).select_related("article")
    recent_comments = (
        user.comments.select_related("article")
        .filter(is_approved=True)
        .order_by("-created_at")[:5]
    )
    recent_uploads = user.uploaded_files.order_by("-created_at")[:5]
    now = timezone.localdate()
    start_date = now - timedelta(days=83)
    contribution_posts = defaultdict(int)
    contribution_edits = defaultdict(int)

    for article in articles:
        c_day = timezone.localtime(article.created_at).date()
        if c_day >= start_date:
            contribution_posts[c_day] += 1
        u_day = timezone.localtime(article.updated_at).date()
        if u_day >= start_date and u_day != c_day:
            contribution_edits[u_day] += 1

    for revision in revisions:
        r_day = timezone.localtime(revision.created_at).date()
        if r_day >= start_date:
            contribution_edits[r_day] += 1
            
    try:
        from .models import CodingSubmission
        coding_submissions = CodingSubmission.objects.filter(user=user)
        for sub in coding_submissions:
            s_day = timezone.localtime(sub.created_at).date()
            if s_day >= start_date:
                contribution_posts[s_day] += 1
    except ImportError:
        pass

    contribution_days = []
    curr = start_date
    while curr <= now:
        posts = contribution_posts[curr]
        edits = contribution_edits[curr]
        count = posts + edits
        contribution_days.append(
            {
                "date": curr,
                "count": count,
                "posts": posts,
                "edits": edits,
                "level": min(count, 4),
                "label": f"{curr.strftime('%d/%m/%Y')}: {count} đóng góp",
            }
        )
        curr += timedelta(days=1)

    # Permission check for private profile
    is_owner = viewer == user
    is_admin = viewer and viewer.is_superuser
    can_view = not user.profile.is_profile_private or is_owner or is_admin

    return {
        "profile": user.profile,
        "profile_user": user,
        "profile_name": get_profile_name(user),
        "can_view_profile": can_view,
        "is_own_profile": is_owner,
        "recent_articles": articles,
        "recent_comments": recent_comments,
        "recent_uploads": recent_uploads,
        "article_count": len(articles),
        "contribution_days": contribution_days,
        "total_contributions": sum(d["count"] for d in contribution_days),
        "chart_labels": [d["date"].strftime("%m/%Y") for d in contribution_days[::14]],
        "chart_posts": [sum(d["posts"] for d in contribution_days[i : i + 14]) for i in range(0, len(contribution_days), 14)],
        "chart_edits": [sum(d["edits"] for d in contribution_days[i : i + 14]) for i in range(0, len(contribution_days), 14)],
        "user_vote_score": user.profile.vote_score,
        "role_names": list(set([g.name for g in user.groups.all()] + (["admin"] if user.is_superuser else []))) or ["user"],
        "edited_articles_count": ArticleRevision.objects.filter(author=user)
        .values("article")
        .distinct()
        .count(),
        "comment_count": user.comments.count(),
        "total_users": User.objects.count(),
        "badges": user.badges.select_related("badge").all(),
        "joined_date": user.date_joined,
        "upload_count": user.uploaded_files.count(),
        "public_email": user.email if user.profile.show_email_publicly and can_view else "",
        "author_articles_url": f"/articles/?author={user.username}",
    }
