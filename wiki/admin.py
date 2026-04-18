"""
Admin configuration for the wiki application.
"""
from django.contrib import admin
from .models import (
    Article, Category, Comment, Profile,
    UploadedFile, ArticleVote, CommentVote, UserVote
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin interface for the Profile model."""
    list_display = ('user', 'display_name', 'guide_seen')
    search_fields = ('user__username', 'user__email', 'display_name')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for the Category model."""
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Admin interface for the Article model."""
    list_display = (
        'title', 'category', 'author',
        'allow_comments', 'created_at', 'updated_at'
    )
    list_filter = ('allow_comments', 'category', 'created_at', 'updated_at')
    search_fields = ('title', 'content', 'author__username')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Admin interface for the Comment model."""
    list_display = ('article', 'author', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('article__title', 'author__username', 'content')


@admin.register(ArticleVote)
class ArticleVoteAdmin(admin.ModelAdmin):
    """Admin interface for the ArticleVote model."""
    list_display = ('user', 'article', 'value', 'created_at')
    list_filter = ('value', 'created_at')


@admin.register(CommentVote)
class CommentVoteAdmin(admin.ModelAdmin):
    """Admin interface for the CommentVote model."""
    list_display = ('user', 'comment', 'value', 'created_at')
    list_filter = ('value', 'created_at')


@admin.register(UserVote)
class UserVoteAdmin(admin.ModelAdmin):
    """Admin interface for the UserVote model."""
    list_display = ('voter', 'target', 'value', 'created_at')


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    """Admin interface for the UploadedFile model."""
    list_display = ('file', 'user', 'description', 'created_at')
    search_fields = ('user__username', 'description', 'file')
    list_filter = ('user', 'created_at')
