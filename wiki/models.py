"""
Models for the wiki application.
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.text import slugify
from martor.models import MartorField
from taggit.managers import TaggableManager


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

    def get_absolute_url(self):
        """Return the URL for the user's public profile."""
        return reverse("wiki:public-profile", kwargs={"username": self.user.username})

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

    STATUS_CHOICES = (
        ("draft", "Bản nháp"),
        ("pending", "Chờ duyệt"),
        ("published", "Đã xuất bản"),
        ("rejected", "Bị từ chối"),
        ("needs_edit", "Yêu cầu sửa đổi"),
    )

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, blank=True, db_index=True)
    content = MartorField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True
    )
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
    tags = TaggableManager(blank=True)

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

        # Check if the slug is already taken
        if not Article.objects.filter(slug=current_slug).exclude(pk=self.pk).exists():
            return current_slug

        # Find existing slugs that start with the base_slug and match the pattern
        # We find the max suffix to avoid O(N) loop
        existing_slugs = Article.objects.filter(
            slug__startswith=current_slug
        ).exclude(pk=self.pk).values_list("slug", flat=True)

        suffixes = []
        for s in existing_slugs:
            if s.startswith(f"{current_slug}-"):
                try:
                    suffixes.append(int(s.split("-")[-1]))
                except (ValueError, IndexError):
                    pass

        if suffixes:
            next_num = max(suffixes) + 1
        else:
            next_num = 1

        suffix = f"-{next_num}"
        trimmed = base_slug[: max(0, 240 - len(suffix))]
        return f"{trimmed}{suffix}"

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

    def get_absolute_url(self):
        """Return the URL for the comment (article detail with anchor)."""
        return self.article.get_absolute_url() + f"#comment-{self.pk}"


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


def testcase_file_validator(value):
    """Validate testcase uploads for coding exercises."""
    allowed_extensions = {
        ext.lower()
        for ext in getattr(
            settings,
            "CODE_EXECUTION_ALLOWED_TESTCASE_EXTENSIONS",
            [".inp", ".out", ".txt", ".ans", ".in"],
        )
    }
    file_ext = Path(value.name).suffix.lower()
    if not file_ext or file_ext not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"Chá»‰ há»— trá»£ file testcase: {allowed}.")


def coding_case_upload_to(instance, filename):
    """Store coding testcase files under the related article directory."""
    article_id = instance.exercise.article_id if instance.exercise_id else "unassigned"
    return f"coding_cases/{article_id}/{filename}"


def default_coding_time_limit():
    """Return the configured default time limit."""
    return getattr(settings, "CODE_EXECUTION_DEFAULT_TIME_LIMIT_MS", 2000)


def default_coding_memory_limit():
    """Return the configured default memory limit."""
    return getattr(settings, "CODE_EXECUTION_DEFAULT_MEMORY_MB", 128)


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


class CodingExercise(models.Model):
    """A mini online-judge style coding exercise attached to an article."""

    COMPARE_MODE_CHOICES = (
        ("exact", "Khá»›p tuyá»‡t Ä‘á»‘i"),
        ("trim_lines", "Bá» khoáº£ng tráº¯ng Ä‘áº§u/cuá»‘i má»—i dÃ²ng"),
        ("tokenized", "So sá»›p theo token"),
    )

    article = models.OneToOneField(
        Article, on_delete=models.CASCADE, related_name="coding_exercise"
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    allowed_languages = models.JSONField(default=list, blank=True)
    default_language = models.CharField(max_length=32, blank=True)
    starter_code_map = models.JSONField(default=dict, blank=True)
    time_limit_ms = models.PositiveIntegerField(default=default_coding_time_limit)
    memory_limit_mb = models.PositiveIntegerField(default=default_coding_memory_limit)
    compare_mode = models.CharField(
        max_length=20, choices=COMPARE_MODE_CHOICES, default="trim_lines"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Metadata for CodingExercise."""

        ordering = ["article_id"]

    def __str__(self):
        return f"CodingExercise({self.article.title})"


class CodingTestCase(models.Model):
    """Testcases for coding exercises, stored as text or uploaded files."""

    exercise = models.ForeignKey(
        CodingExercise, on_delete=models.CASCADE, related_name="testcases"
    )
    name = models.CharField(max_length=120)
    input_text = models.TextField(blank=True)
    expected_output_text = models.TextField(blank=True)
    input_file = models.FileField(
        upload_to=coding_case_upload_to,
        validators=[testcase_file_validator],
        blank=True,
        null=True,
    )
    expected_output_file = models.FileField(
        upload_to=coding_case_upload_to,
        validators=[testcase_file_validator],
        blank=True,
        null=True,
    )
    is_sample = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for CodingTestCase."""

        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.exercise.article.title}: {self.name}"

    def clean(self):
        """Require both input and expected output in either text or file form."""
        if not (self.input_text or self.input_file):
            raise ValidationError({"input_text": "Cáº§n input text hoáº·c file input."})
        if not (self.expected_output_text or self.expected_output_file):
            raise ValidationError(
                {"expected_output_text": "Cáº§n output text hoáº·c file output."}
            )

    def get_input_data(self):
        """Return testcase input data as text."""
        if self.input_file:
            self.input_file.seek(0)
            return self.input_file.read().decode("utf-8")
        return self.input_text or ""

    def get_expected_output_data(self):
        """Return expected testcase output as text."""
        if self.expected_output_file:
            self.expected_output_file.seek(0)
            return self.expected_output_file.read().decode("utf-8")
        return self.expected_output_text or ""


class CodingSubmission(models.Model):
    """Stores each code run or judged submission."""

    STATUS_CHOICES = (
        ("accepted", "Accepted"),
        ("wrong_answer", "Wrong Answer"),
        ("compile_error", "Compile Error"),
        ("runtime_error", "Runtime Error"),
        ("time_limit_exceeded", "Time Limit Exceeded"),
        ("internal_error", "Internal Error"),
        ("running", "Running"),
    )

    exercise = models.ForeignKey(
        CodingExercise, on_delete=models.CASCADE, related_name="submissions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coding_submissions",
    )
    language = models.CharField(max_length=32)
    source_code = models.TextField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="running")
    compile_output = models.TextField(blank=True)
    stdout_preview = models.TextField(blank=True)
    stderr_preview = models.TextField(blank=True)
    custom_input = models.TextField(blank=True)
    is_sample_run = models.BooleanField(default=False)
    total_tests = models.PositiveIntegerField(default=0)
    passed_tests = models.PositiveIntegerField(default=0)
    runtime_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Metadata for CodingSubmission."""

        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.exercise.article.title} - {self.user} - {self.status}"


class CodingSubmissionResult(models.Model):
    """Per-testcase verdicts for a coding submission."""

    submission = models.ForeignKey(
        CodingSubmission, on_delete=models.CASCADE, related_name="results"
    )
    test_case = models.ForeignKey(
        CodingTestCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submission_results",
    )
    case_name = models.CharField(max_length=120)
    status = models.CharField(max_length=32)
    runtime_ms = models.PositiveIntegerField(default=0)
    stdout_preview = models.TextField(blank=True)
    stderr_preview = models.TextField(blank=True)
    expected_preview = models.TextField(blank=True)
    actual_preview = models.TextField(blank=True)

    class Meta:
        """Metadata for CodingSubmissionResult."""

        ordering = ["id"]

    def __str__(self):
        return f"{self.case_name}: {self.status}"


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


class Bookmark(models.Model):
    """Model for articles bookmarked by users."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks"
    )
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="bookmarked_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for Bookmark."""

        unique_together = (("user", "article"),)
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} bookmarked {self.article}"


class Notification(models.Model):
    """Model for in-app notifications."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_notifications",
        null=True,
        blank=True,
    )
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for Notification."""

        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.recipient}: {self.message}"


class Report(models.Model):
    """Model for tracking user reports for articles and comments."""

    REPORT_REASONS = (
        ("spam", "Spam / Quảng cáo"),
        ("inappropriate", "Nội dung không phù hợp"),
        ("copyright", "Vi phạm bản quyền"),
        ("error", "Lỗi nội dung / Thông tin sai lệch"),
        ("other", "Khác"),
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports"
    )
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="reports", null=True, blank=True
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="reports", null=True, blank=True
    )
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    description = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for Report."""

        ordering = ["-created_at"]

    def __str__(self):
        target = self.article or self.comment
        return f"Report by {self.reporter} on {target}"


class Badge(models.Model):
    """Model for achievements/badges."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField()
    icon = models.CharField(
        max_length=50, help_text="FontAwesome class, e.g., 'fa-trophy'"
    )

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    """Link between users and badges they have earned."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges"
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awarded_to")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadata for UserBadge."""

        unique_together = (("user", "badge"),)
        ordering = ["-awarded_at"]

    def __str__(self):
        return f"{self.user} earned {self.badge}"
