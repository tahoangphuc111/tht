from collections import defaultdict
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from .models import ArticleRevision, Profile

User = get_user_model()


def save_article_revision(article, user, change_summary):
    ArticleRevision.objects.create(
        article=article,
        title=article.title,
        content=article.content,
        author=user,
        change_summary=change_summary,
    )


def can_publish_articles(user):
    if not user.is_authenticated:
        return False
    profile, _ = Profile.objects.get_or_create(user=user)
    if profile.is_suspended:
        return False
    publisher_roles = ["admin", "editor", "contributor"]
    return (
        user.is_superuser
        or user.groups.filter(name__in=publisher_roles).exists()
        or user.has_perm("wiki.add_article")
    )


def can_manage_wiki(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.has_perm("wiki.manage_all_articles"):
        return True
    try:
        profile = getattr(user, "profile", None)
        if profile and profile.role in ["teacher", "moderator"]:
            return True
    except Exception:
        pass
    return False


def get_profile_name(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile.display_name or user.get_full_name() or user.username


def get_safe_redirect_url(request, candidate, fallback="/"):
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def build_profile_stats(user, viewer=None):
    is_owner = viewer == user
    is_admin = bool(viewer and viewer.is_superuser)
    profile, _ = Profile.objects.get_or_create(user=user)
    can_view = not profile.is_profile_private or is_owner or is_admin

    article_queryset = user.articles.select_related("category").order_by("-updated_at")
    if not (is_owner or is_admin):
        article_queryset = article_queryset.filter(status="published")
    articles = list(article_queryset)
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
        coding_submissions = CodingSubmission.objects.filter(
            user=user, created_at__date__gte=start_date, is_sample_run=False
        )
        seen_submissions = set()
        for sub in coding_submissions:
            s_day = timezone.localtime(sub.created_at).date()
            if s_day >= start_date:
                key = (s_day, sub.exercise_id)
                if key not in seen_submissions:
                    seen_submissions.add(key)
                    contribution_edits[s_day] += 1
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

    completed_quizzes = []
    if can_view:
        from .models import Question, UserAnswer, Article
        # Fetch articles that have questions where user has answered at least one
        attempted_articles = Article.objects.filter(
            questions__user_answers__user=user
        ).distinct().prefetch_related('questions')

        for art in attempted_articles:
            total_questions = art.questions.count()
            if total_questions > 0:
                user_answers = UserAnswer.objects.filter(user=user, question__article=art).select_related('selected_choice')
                correct_answers = sum(1 for ua in user_answers if ua.selected_choice.is_correct)
                latest_answer = max(ua.created_at for ua in user_answers) if user_answers else None
                completed_quizzes.append({
                    "article": art,
                    "correct_answers": correct_answers,
                    "total_questions": total_questions,
                    "score_percent": int(correct_answers * 100 / total_questions),
                    "date_completed": latest_answer,
                })
        # Sort by date completed descending
        completed_quizzes.sort(key=lambda x: x["date_completed"] or timezone.now(), reverse=True)

    return {
        "profile": profile,
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
        "user_vote_score": profile.vote_score,
        "role_names": list(set([g.name for g in user.groups.all()] + (["admin"] if user.is_superuser else []) + ([profile.get_role_display()] if profile else []))) or ["user"],
        "edited_articles_count": ArticleRevision.objects.filter(author=user)
        .values("article")
        .distinct()
        .count(),
        "comment_count": user.comments.count(),
        "total_users": User.objects.count(),
        "badges": user.badges.select_related("badge").all(),
        "joined_date": user.date_joined,
        "upload_count": user.uploaded_files.count(),
        "public_email": user.email if profile.show_email_publicly and can_view else "",
        "author_articles_url": f"/articles/?author={user.username}",
        "completed_quizzes": completed_quizzes,
    }
