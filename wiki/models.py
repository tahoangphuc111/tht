"""
Models for the wiki application.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.text import slugify
from martor.models import MartorField


def get_uncategorized_category():
    """Get or create the default 'Uncategorized' category."""
    category, _ = Category.objects.get_or_create(
        slug="chua-phan-loai",
        defaults={
            "name": "Chưa phân loại",
            "description": "Các bài viết chưa được gán danh mục cụ thể.",
        },
    )
    return category.pk


class Profile(models.Model):
    """User profile model extending the base User."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
        help_text="Ảnh đại diện người dùng (jpg, png, gif).",
    )
    guide_seen = models.BooleanField(default=False)
    is_profile_private = models.BooleanField(
        default=False,
        help_text="Bật để chỉ bạn và admin có thể xem đầy đủ hồ sơ này.",
    )
    show_email_publicly = models.BooleanField(
        default=False,
        help_text="Cho phép hiển thị email trên hồ sơ công khai.",
    )

    def __str__(self):
        return self.display_name or self.user.get_username()

    @property
    def total_votes(self):
        """Aggregate total upvotes and downvotes for the user."""
        return self.user.user_votes.aggregate(
            up=Count("value", filter=Q(value=1)),
            down=Count("value", filter=Q(value=-1)),
        )

    @property
    def vote_score(self):
        """Calculate the net vote score."""
        vt = self.total_votes
        return (vt.get("up") or 0) - (vt.get("down") or 0)

    @property
    def upvotes(self):
        """Count total upvotes."""
        return self.user.user_votes.filter(value=1).count()

    @property
    def downvotes(self):
        """Count total downvotes."""
        return self.user.user_votes.filter(value=-1).count()


class Category(models.Model):
    """Category model for grouping articles."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for Category."""

        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """Return the URL for the category's article list."""
        return reverse("wiki:article-list") + f"?category={self.slug}"


class Article(models.Model):
    """Wiki article model."""

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, blank=True, db_index=True)
    content = MartorField()
    allow_comments = models.BooleanField(default=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="articles",
        blank=True,
        default=get_uncategorized_category,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        """Metadata for Article."""

        ordering = ["-created_at"]
        permissions = [
            ("manage_all_articles", "Can manage all articles"),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """Return the detail URL for the article."""
        return reverse("wiki:article-detail", kwargs={"pk": self.pk, "slug": self.slug})

    @property
    def reading_time_minutes(self):
        """Estimate reading time in minutes."""
        word_count = len((self.content or "").split())
        return max(1, round(word_count / 200)) if word_count else 1

    @property
    def vote_score(self):
        """Calculate net vote score for the article."""
        agg = self.article_votes.aggregate(
            up=Count("value", filter=Q(value=1)),
            down=Count("value", filter=Q(value=-1)),
        )
        return (agg.get("up") or 0) - (agg.get("down") or 0)

    @property
    def upvotes(self):
        """Count total upvotes for the article."""
        return self.article_votes.filter(value=1).count()

    @property
    def downvotes(self):
        """Count total downvotes for the article."""
        return self.article_votes.filter(value=-1).count()

    def _build_unique_slug(self):
        """Generate a unique slug based on the article title."""
        base_slug = slugify(self.title) or "article"
        current_slug = base_slug[:240]
        counter = 1
        while Article.objects.filter(slug=current_slug).exclude(pk=self.pk).exists():
            suffix = f"-{counter}"
            trimmed = base_slug[: max(0, 240 - len(suffix))]
            current_slug = f"{trimmed}{suffix}"
            counter += 1
        return current_slug

    def save(self, *args, **kwargs):
        """Ensure slug and category are set before saving."""
        if not self.slug:
            self.slug = self._build_unique_slug()
        elif Article.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = self._build_unique_slug()

        if not self.category:
            self.category_id = get_uncategorized_category()
        super().save(*args, **kwargs)


class Comment(models.Model):
    """Comment model for articles."""

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        """Metadata for Comment."""

        ordering = ["created_at"]

    @property
    def vote_score(self):
        """Calculate net vote score for the comment."""
        agg = self.comment_votes.aggregate(
            up=Count("value", filter=Q(value=1)),
            down=Count("value", filter=Q(value=-1)),
        )
        return (agg.get("up") or 0) - (agg.get("down") or 0)

    @property
    def upvotes(self):
        """Count total upvotes for the comment."""
        return self.comment_votes.filter(value=1).count()

    @property
    def downvotes(self):
        """Count total downvotes for the comment."""
        return self.comment_votes.filter(value=-1).count()

    def __str__(self):
        return f"Comment by {self.author} on {self.article}"


def upload_file_validator(value):
    """Validate that the uploaded file is of an allowed type."""
    allowed = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/png",
        "image/jpeg",
        "image/jpg",
    ]
    if value.file.content_type not in allowed:
        raise ValidationError("Chỉ hỗ trợ upload file pdf, docx, png, jpg.")


class UploadedFile(models.Model):
    """Model for files uploaded by users."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_files",
    )
    article = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="attachments",
        null=True,
        blank=True,
    )
    file = models.FileField(
        upload_to="uploads/%Y/%m/%d/", validators=[upload_file_validator]
    )
    description = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for UploadedFile."""

        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file.name} by {self.user.username}"


class ArticleRevision(models.Model):
    """Model for tracking article revision history."""

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    title = models.CharField(max_length=220)
    content = MartorField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    change_summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for ArticleRevision."""

        ordering = ["-created_at"]

    def __str__(self):
        return f"Revision of {self.article.title} at {self.created_at}"


class ArticleVote(models.Model):
    """Voting model for articles."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="article_votes"
    )
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="article_votes"
    )
    value = models.SmallIntegerField(choices=((1, "Upvote"), (-1, "Downvote")))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Metadata for ArticleVote."""

        unique_together = (("user", "article"),)

    def __str__(self):
        return f"ArticleVote({self.user}, {self.article}, {self.value})"


class CommentVote(models.Model):
    """Voting model for comments."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_votes"
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="comment_votes"
    )
    value = models.SmallIntegerField(choices=((1, "Upvote"), (-1, "Downvote")))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Metadata for CommentVote."""

        unique_together = (("user", "comment"),)

    def __str__(self):
        return f"CommentVote({self.user}, {self.comment}, {self.value})"


class UserVote(models.Model):
    """Voting model for users (reputation)."""

    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="given_user_votes",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_votes"
    )
    value = models.SmallIntegerField(choices=((1, "Upvote"), (-1, "Downvote")))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Metadata for UserVote."""

        unique_together = (("voter", "target"),)

    def __str__(self):
        return f"UserVote({self.voter}, {self.target}, {self.value})"


class Question(models.Model):
    """Quiz question model."""

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="questions"
    )
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    explanation = models.TextField(
        blank=True, help_text="Hiện sau khi người dùng trả lời."
    )

    class Meta:
        """Metadata for Question."""

        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.content[:50]}..."


class Choice(models.Model):
    """Quiz choice model for a question."""

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices"
    )
    content = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        """Metadata for Choice."""

        ordering = ["id"]

    def __str__(self):
        return self.content


class UserAnswer(models.Model):
    """Model for tracking user answers to quiz questions."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_answers"
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="user_answers"
    )
    selected_choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for UserAnswer."""

        unique_together = (("user", "question"),)

    def __str__(self):
        return f"Answer by {self.user} for {self.question}"
