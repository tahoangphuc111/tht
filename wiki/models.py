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
    category, _ = Category.objects.get_or_create(
        slug="chua-phan-loai",
        defaults={
            "name": "Chưa phân loại",
            "description": "Các bài viết chưa được gán danh mục cụ thể.",
        },
    )
    return category.pk


class Profile(models.Model):
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
        return reverse("wiki:public-profile", kwargs={"username": self.user.username})

    @property
    def get_avatar_url(self):
        if self.avatar and hasattr(self.avatar, "url"):
            return self.avatar.url
        return f"https://ui-avatars.com/api/?name={self.user.username}&background=random"

    @property
    def total_votes(self):
        return self.user.user_votes.aggregate(
            up=Count("value", filter=Q(value=1)),
            down=Count("value", filter=Q(value=-1)),
        )

    @property
    def vote_score(self):
        vt = self.total_votes
        return (vt.get("up") or 0) - (vt.get("down") or 0)

    @property
    def upvotes(self):
        return self.user.user_votes.filter(value=1).count()

    @property
    def downvotes(self):
        return self.user.user_votes.filter(value=-1).count()


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("wiki:article-list") + f"?category={self.slug}"


class Article(models.Model):
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
        ordering = ["-created_at"]
        permissions = [
            ("manage_all_articles", "Can manage all articles"),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("wiki:article-detail", kwargs={"pk": self.pk, "slug": self.slug})

    @property
    def reading_time_minutes(self):
        word_count = len((self.content or "").split())
        return max(1, round(word_count / 200)) if word_count else 1

    @property
    def vote_score(self):
        agg = self.article_votes.aggregate(
            up=Count("value", filter=Q(value=1)),
            down=Count("value", filter=Q(value=-1)),
        )
        return (agg.get("up") or 0) - (agg.get("down") or 0)

    @property
    def upvotes(self):
        return self.article_votes.filter(value=1).count()

    @property
    def downvotes(self):
        return self.article_votes.filter(value=-1).count()

    def _build_unique_slug(self):
        base_slug = slugify(self.title) or "article"
        current_slug = base_slug[:240]
        if not Article.objects.filter(slug=current_slug).exclude(pk=self.pk).exists():
            return current_slug
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
        if not self.slug:
            self.slug = self._build_unique_slug()
        elif Article.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = self._build_unique_slug()
        if not self.category:
            self.category_id = get_uncategorized_category()
        super().save(*args, **kwargs)


class Comment(models.Model):
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
        ordering = ["created_at"]

    @property
    def vote_score(self):
        agg = self.comment_votes.aggregate(
            up=Count("value", filter=Q(value=1)),
            down=Count("value", filter=Q(value=-1)),
        )
        return (agg.get("up") or 0) - (agg.get("down") or 0)

    @property
    def upvotes(self):
        return self.comment_votes.filter(value=1).count()

    @property
    def downvotes(self):
        return self.comment_votes.filter(value=-1).count()

    def __str__(self):
        return f"Comment by {self.author} on {self.article}"

    def get_absolute_url(self):
        return self.article.get_absolute_url() + f"#comment-{self.pk}"


def upload_file_validator(value):
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
        raise ValidationError(f"Chỉ hỗ trợ file testcase: {allowed}.")


def coding_case_upload_to(instance, filename):
    article_id = instance.exercise.article_id if instance.exercise_id else "unassigned"
    return f"coding_cases/{article_id}/{filename}"


def default_coding_time_limit():
    return getattr(settings, "CODE_EXECUTION_DEFAULT_TIME_LIMIT_MS", 2000)


def default_coding_memory_limit():
    return getattr(settings, "CODE_EXECUTION_DEFAULT_MEMORY_MB", 128)


class UploadedFile(models.Model):
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
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file.name} by {self.user.username}"


class ArticleRevision(models.Model):
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
        ordering = ["-created_at"]

    def __str__(self):
        return f"Revision of {self.article.title} at {self.created_at}"


class ArticleVote(models.Model):
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
        unique_together = (("user", "article"),)

    def __str__(self):
        return f"ArticleVote({self.user}, {self.article}, {self.value})"


class CommentVote(models.Model):
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
        unique_together = (("user", "comment"),)

    def __str__(self):
        return f"CommentVote({self.user}, {self.comment}, {self.value})"


class UserVote(models.Model):
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
        unique_together = (("voter", "target"),)

    def __str__(self):
        return f"UserVote({self.voter}, {self.target}, {self.value})"


class Question(models.Model):
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="questions"
    )
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    explanation = models.TextField(
        blank=True, help_text="Hiện sau khi người dùng trả lời."
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.content[:50]}..."


class Choice(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices"
    )
    content = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.content


class LanguageRuntime(models.Model):
    key = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=64)
    monaco = models.CharField(max_length=32, default="plaintext")
    source = models.CharField(max_length=64)
    compile_cmd = models.JSONField(default=list, blank=True)
    run_cmd = models.JSONField(default=list)
    starter = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["order", "key"]

    def __str__(self):
        return self.label

    def to_config(self):
        return {
            "label": self.label,
            "monaco_language": self.monaco,
            "source_name": self.source,
            "compile": self.compile_cmd or [],
            "run": self.run_cmd or [],
            "starter_code": self.starter,
            "enabled": self.enabled,
        }


class CodingExercise(models.Model):
    COMPARE_MODE_CHOICES = (
        ("exact", "Exact match"),
        ("trim_lines", "Trim whitespace"),
        ("tokenized", "Token-based"),
        ("custom_checker", "Custom Checker"),
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
    checker_code = models.TextField(blank=True, help_text="Mã nguồn giám khảo chấm bài (dùng cho Custom Checker)")
    checker_language = models.CharField(max_length=32, blank=True, help_text="Ngôn ngữ của mã nguồn giám khảo (ví dụ: python, cpp)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["article_id"]

    def __str__(self):
        return f"CodingExercise({self.article.title})"


class CodingTestCase(models.Model):
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
    subtask_id = models.PositiveIntegerField(default=1, help_text="ID của subtask (các testcase cùng ID sẽ gom lại thành 1 subtask)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.exercise.article.title}: {self.name}"

    def clean(self):
        if not (self.input_text or self.input_file):
            raise ValidationError({"input_text": "Cần input text hoặc file input."})
        if not (self.expected_output_text or self.expected_output_file):
            raise ValidationError(
                {"expected_output_text": "Cần output text hoặc file output."}
            )

    def get_input_data(self):
        if self.input_file:
            self.input_file.seek(0)
            return self.input_file.read().decode("utf-8")
        return self.input_text or ""

    def get_expected_output_data(self):
        if self.expected_output_file:
            self.expected_output_file.seek(0)
            return self.expected_output_file.read().decode("utf-8")
        return self.expected_output_text or ""


class CodingSubmission(models.Model):
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
    score = models.PositiveIntegerField(default=0)
    subtask_results = models.JSONField(default=dict, blank=True)
    runtime_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.exercise.article.title} - {self.user} - {self.status}"


class CodingSubmissionResult(models.Model):
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
        ordering = ["id"]

    def __str__(self):
        return f"{self.case_name}: {self.status}"


class UserAnswer(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_answers"
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="user_answers"
    )
    selected_choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "question"),)

    def __str__(self):
        return f"Answer by {self.user} for {self.question}"


class Bookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks"
    )
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="bookmarked_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "article"),)
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} bookmarked {self.article}"


class Notification(models.Model):
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
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.recipient}: {self.message}"


class Report(models.Model):
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
        ordering = ["-created_at"]

    def __str__(self):
        target = self.article or self.comment
        return f"Report by {self.reporter} on {target}"


class Badge(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField()
    icon = models.CharField(
        max_length=50, help_text="FontAwesome class, e.g., 'fa-trophy'"
    )

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges"
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awarded_to")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "badge"),)
        ordering = ["-awarded_at"]

    def __str__(self):
        return f"{self.user} earned {self.badge}"
