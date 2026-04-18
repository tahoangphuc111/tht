"""
Signals for the wiki application.
"""
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import Category, Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_profile(sender, instance, created, **kwargs):
    """Create or update user profile when User is saved."""
    # pylint: disable=unused-argument
    if created:
        Profile.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)


@receiver(post_migrate)
def ensure_default_groups(sender, **kwargs):
    """Create default groups and permissions after migration."""
    # pylint: disable=unused-argument
    if sender.name != 'wiki':
        return

    admin_group, _ = Group.objects.get_or_create(name='admin')
    editor_group, _ = Group.objects.get_or_create(name='editor')
    contributor_group, _ = Group.objects.get_or_create(name='contributor')
    user_group, _ = Group.objects.get_or_create(name='user')

    admin_permissions = Permission.objects.filter(
        content_type__app_label='wiki',
        codename__in=[
            'add_article', 'change_article', 'delete_article', 'view_article',
            'add_category', 'change_category', 'delete_category',
            'view_category', 'manage_all_articles', 'add_comment',
            'change_comment', 'delete_comment', 'view_comment',
        ],
    )
    editor_permissions = Permission.objects.filter(
        content_type__app_label='wiki',
        codename__in=[
            'add_article', 'change_article', 'delete_article', 'view_article',
            'view_category', 'add_comment', 'change_comment',
            'delete_comment', 'view_comment',
        ],
    )
    contributor_permissions = Permission.objects.filter(
        content_type__app_label='wiki',
        codename__in=[
            'add_article', 'change_article', 'delete_article', 'view_article',
            'view_category', 'add_comment', 'view_comment',
        ],
    )
    user_permissions = Permission.objects.filter(
        content_type__app_label='wiki',
        codename__in=[
            'view_article', 'view_category', 'add_comment', 'view_comment'
        ],
    )

    admin_group.permissions.set(admin_permissions)
    editor_group.permissions.set(editor_permissions)
    contributor_group.permissions.set(contributor_permissions)
    user_group.permissions.set(user_permissions)

    Category.objects.get_or_create(
        slug='chua-phan-loai',
        defaults={
            'name': 'Chưa phân loại',
            'description': 'Các bài viết chưa được gán danh mục cụ thể.',
        },
    )
