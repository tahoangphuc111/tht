"""
Signals for the wiki app to handle notifications and badges.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Article, Comment, ArticleVote, Notification, Badge, UserBadge, Profile
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a profile when a new user is created."""
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=Comment)
def notify_on_new_comment(sender, instance, created, **kwargs):
    """Notify article author when a new comment is posted."""
    if created and instance.author != instance.article.author:
        Notification.objects.create(
            recipient=instance.article.author,
            sender=instance.author,
            message=f"{instance.author} đã bình luận bài viết: {instance.article.title}",
            link=instance.article.get_absolute_url(),
        )
        # check badges for commenter
        check_badges(instance.author)


@receiver(pre_save, sender=Article)
def store_old_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Article.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Article.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Article)
def notify_on_article_status_change(sender, instance, created, **kwargs):
    """Notify author when article is approved or rejected."""
    old_status = getattr(instance, '_old_status', None)
    if old_status != instance.status:
        if instance.status == "published":
            Notification.objects.create(
                recipient=instance.author,
                message=f"Bài viết của bạn đã được duyệt: {instance.title}",
                link=instance.get_absolute_url(),
            )
            check_badges(instance.author)
        elif instance.status == "rejected":
            Notification.objects.create(
                recipient=instance.author,
                message=f"Bài viết của bạn bị từ chối: {instance.title}",
            )


@receiver(post_save, sender=ArticleVote)
def notify_on_article_vote(sender, instance, created, **kwargs):
    """Notify author when their article gets an upvote."""
    if created and instance.value == 1 and instance.user != instance.article.author:
        Notification.objects.create(
            recipient=instance.article.author,
            sender=instance.user,
            message=f"{instance.user} đã upvote bài viết của bạn: {instance.article.title}",
            link=instance.article.get_absolute_url(),
        )
        check_badges(instance.article.author)


def check_badges(user):
    """Utility to check and award badges to a user based on milestones efficiently."""
    # Get all current badge slugs for the user to avoid redundant checks
    user_badge_slugs = set(UserBadge.objects.filter(user=user).values_list('badge__slug', flat=True))

    milestones = [
        {"slug": "first-article", "name": "Người tiên phong", "icon": "fa-seedling", "desc": "Đăng bài viết đầu tiên được duyệt"},
        {"slug": "popular-author", "name": "Tác giả được yêu thích", "icon": "fa-fire", "desc": "Đạt tổng cộng 10 upvote bài viết"},
        {"slug": "active-commenter", "name": "Thành viên tích cực", "icon": "fa-comments", "desc": "Đã đăng 5 bình luận"},
    ]

    for m in milestones:
        if m["slug"] in user_badge_slugs:
            continue

        # Only run expensive count queries if user doesn't have the badge
        awarded = False
        if m["slug"] == "first-article":
            if user.articles.filter(status="published").exists():
                awarded = True
        elif m["slug"] == "popular-author":
            if ArticleVote.objects.filter(article__author=user, value=1).count() >= 10:
                awarded = True
        elif m["slug"] == "active-commenter":
            if user.comments.count() >= 5:
                awarded = True

        if awarded:
            badge, _ = Badge.objects.get_or_create(
                slug=m["slug"],
                defaults={
                    "name": m["name"],
                    "icon": m["icon"],
                    "description": m["desc"]
                }
            )
            UserBadge.objects.get_or_create(user=user, badge=badge)
