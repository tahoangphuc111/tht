from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from ..models import Article, Category, ArticleRevision, Bookmark, UploadedFile, Profile, Comment
from ..forms import ArticleForm, CommentForm
from ..services.code_runner import get_enabled_language_choices, get_language_config
from ..utils import save_article_revision, can_publish_articles, can_manage_wiki


def _validate_article_attachments(form, files):
    """Validate article attachment uploads before saving the article."""
    if len(files) > 5:
        form.add_error(None, "Chỉ được upload tối đa 5 file đính kèm.")
        return False

    is_valid = True
    for upload in files:
        candidate = UploadedFile(file=upload)
        try:
            candidate.full_clean(exclude=["user", "article"])
        except ValidationError as error:
            form.add_error(None, f"{upload.name}: {'; '.join(error.messages)}")
            is_valid = False
    return is_valid


def _save_article_attachments(article, user, files):
    """Persist validated attachments for an article."""
    for upload in files:
        UploadedFile.objects.create(article=article, user=user, file=upload)


class ArticleListView(ListView):
    model = Article
    template_name = "wiki/article_list.html"
    context_object_name = "articles"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        can_manage = can_manage_wiki(user)
        qs = Article.objects.select_related("author", "category").annotate(
            comment_count=Count("comments", distinct=True),
            vote_balance=(
                Count("article_votes", filter=Q(article_votes__value=1), distinct=True)
                - Count("article_votes", filter=Q(article_votes__value=-1), distinct=True)
            ),
        )
        if not can_manage:
            qs = qs.filter(status="published")
        q = self.request.GET.get("q", "")
        auth = self.request.GET.get("author", "")
        cat = self.request.GET.get("category", "")
        tag = self.request.GET.get("tag", "")
        sort = self.request.GET.get("sort", "newest")
        status = self.request.GET.get("status", "")
        discussion = self.request.GET.get("discussion")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
        if auth:
            qs = qs.filter(author__username__icontains=auth)
        if cat:
            qs = qs.filter(category__slug=cat)
        if tag:
            qs = qs.filter(tags__slug=tag)
        if status and can_manage:
            qs = qs.filter(status=status)
        if discussion == "open":
            qs = qs.filter(allow_comments=True)
        elif discussion == "locked":
            qs = qs.filter(allow_comments=False)
        if sort == "updated":
            qs = qs.order_by("-updated_at", "-created_at")
        elif sort == "commented":
            qs = qs.order_by("-comment_count", "-created_at")
        elif sort == "top":
            qs = qs.order_by("-vote_balance", "-comment_count", "-updated_at")
        else:
            qs = qs.order_by("-created_at")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "query": self.request.GET.get("q", ""),
            "selected_author": self.request.GET.get("author", ""),
            "selected_category": self.request.GET.get("category", ""),
            "selected_discussion": self.request.GET.get("discussion", ""),
            "selected_sort": self.request.GET.get("sort", "newest"),
            "categories": Category.objects.all(),
            "can_publish": can_publish_articles(self.request.user),
        })
        return context


class ArticleDetailView(DetailView):
    model = Article
    template_name = "wiki/article_detail.html"
    context_object_name = "article"
    query_pk_and_slug = True

    def get_queryset(self):
        user = self.request.user
        qs = Article.objects.select_related("author", "category").annotate(
            comment_count=Count("comments", distinct=True),
            vote_balance=(
                Count("article_votes", filter=Q(article_votes__value=1), distinct=True)
                - Count("article_votes", filter=Q(article_votes__value=-1), distinct=True)
            ),
        )
        if can_manage_wiki(user):
            return qs
        if user.is_authenticated:
            return qs.filter(Q(status="published") | Q(author=user))
        return qs.filter(status="published")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        user = self.request.user
        can_manage = can_manage_wiki(user)
        coding_exercise = getattr(article, "coding_exercise", None)
        coding_language_choices = []
        coding_starter_map = {}
        coding_monaco_map = {}
        coding_samples = []
        coding_frontend_config = None
        if coding_exercise and coding_exercise.is_enabled:
            for language in get_enabled_language_choices():
                if language["key"] in (coding_exercise.allowed_languages or []):
                    coding_language_choices.append(language)
                    coding_monaco_map[language["key"]] = language["monaco_language"]
                    coding_starter_map[language["key"]] = coding_exercise.starter_code_map.get(
                        language["key"],
                        get_language_config(language["key"]).get("starter_code", ""),
                    )
            coding_samples = [{
                "name": testcase.name,
                "input": testcase.get_input_data(),
                "output": testcase.get_expected_output_data(),
            } for testcase in coding_exercise.testcases.filter(is_sample=True)]
            coding_frontend_config = {
                "articleId": article.pk,
                "runUrl": reverse("wiki:run-code", args=[article.pk]),
                "submitUrl": reverse("wiki:submit-code", args=[article.pk]),
                "statusUrl": reverse("wiki:submission-status", args=[0]),
                "starterCodeMap": coding_starter_map,
                "monacoMap": coding_monaco_map,
                "samples": coding_samples,
            }
        # Only show questions that have choices and at least one correct choice
        quiz_questions = article.questions.prefetch_related("choices").annotate(
            correct_count=Count("choices", filter=Q(choices__is_correct=True))
        ).filter(correct_count__gt=0)

        context.update({
            "quiz_questions": quiz_questions,
            "comments": article.comments.select_related("author").filter(is_approved=True),
            "related_articles": Article.objects.filter(
                category=article.category, status="published"
            ).exclude(pk=article.pk).select_related("author", "category").annotate(comment_count=Count("comments", distinct=True))[:3],
            "comment_form": kwargs.get("comment_form", CommentForm()),
            "can_comment": (article.allow_comments and user.is_authenticated and user.has_perm("wiki.add_comment")),
            "commenting_locked": not article.allow_comments,
            "can_edit_article": (can_manage or (user.is_authenticated and article.author == user
                                                and user.has_perm("wiki.change_article"))),
            "can_delete_article": (can_manage or (user.is_authenticated and article.author == user
                                                  and user.has_perm("wiki.delete_article"))),
            "article_vote_score": getattr(article, "vote_balance", article.vote_score),
            "is_bookmarked": user.is_authenticated and Bookmark.objects.filter(user=user, article=article).exists(),
            "coding_exercise": coding_exercise if coding_exercise and coding_exercise.is_enabled else None,
            "coding_language_choices": coding_language_choices,
            "coding_starter_map": coding_starter_map,
            "coding_monaco_map": coding_monaco_map,
            "coding_samples": coding_samples,
            "coding_frontend_config": coding_frontend_config,
        })
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if (
            not self.object.allow_comments
            or not request.user.is_authenticated
            or not request.user.has_perm("wiki.add_comment")
        ):
            return redirect(self.object.get_absolute_url())

        # 1. Check suspension status
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if profile.is_suspended:
            messages.error(request, "Tài khoản của bạn đang bị khóa các chức năng tương tác.")
            return redirect(self.object.get_absolute_url())

        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = self.object
            comment.author = request.user

            # 2. Rate-limiting (prevent rapid spam posting)
            from django.utils import timezone
            last_comment = Comment.objects.filter(author=request.user).order_by("-created_at").first()
            if last_comment:
                time_diff = (timezone.now() - last_comment.created_at).total_seconds()
                if time_diff < 10:
                    messages.error(request, "Bạn đang bình luận quá nhanh. Vui lòng đợi vài giây.")
                    return redirect(self.object.get_absolute_url())

            # 3. Spam filtering
            import re
            content_lower = comment.content.lower()
            spam_keywords = ["cờ bạc", "cá độ", "casino", "nhà cái", "chơi bài", "viagra", "mua bán tài khoản", "kiếm tiền online"]
            is_spam = any(keyword in content_lower for keyword in spam_keywords)

            # Detect more than 2 links
            links_count = len(re.findall(r'https?://', content_lower))
            if links_count > 2:
                is_spam = True

            if is_spam:
                comment.is_approved = False
                comment.save()
                messages.warning(request, "Bình luận của bạn chứa nội dung nghi ngờ là spam và đang được chờ kiểm duyệt.")
                return redirect(self.object.get_absolute_url())

            comment.save()
            return redirect(self.object.get_absolute_url())
        return self.render_to_response(self.get_context_data(comment_form=form))


class ArticleCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = "wiki/article_form.html"

    def test_func(self):
        return can_publish_articles(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect("wiki:article-list")
        return super().handle_no_permission()

    def form_valid(self, form):
        attachments = self.request.FILES.getlist("attachments")
        if not _validate_article_attachments(form, attachments):
            return self.form_invalid(form)
        form.instance.author = self.request.user
        response = super().form_valid(form)
        _save_article_attachments(self.object, self.request.user, attachments)
        save_article_revision(self.object, self.request.user, form.cleaned_data.get("change_summary", "Initial"))
        return response


class ArticleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = "wiki/article_form.html"

    def get_object(self, queryset=None):
        if not hasattr(self, '_cached_object'):
            self._cached_object = get_object_or_404(Article, pk=self.kwargs.get("pk"))
        return self._cached_object

    def test_func(self):
        article = self.get_object()
        user = self.request.user
        if user.is_authenticated:
            profile, _ = Profile.objects.get_or_create(user=user)
            if profile.is_suspended:
                return False
        return (user.is_superuser or user.has_perm("wiki.manage_all_articles")
                or (article.author == user and user.has_perm("wiki.change_article")))

    def handle_no_permission(self):
        return redirect("wiki:article-list")

    def form_valid(self, form):
        attachments = self.request.FILES.getlist("attachments")
        if not _validate_article_attachments(form, attachments):
            return self.form_invalid(form)
        article_fields = ["title", "slug", "content", "category", "tags", "allow_comments"]
        if not attachments and not any(f in form.changed_data for f in article_fields):
            messages.info(self.request, "Không có thay đổi nào được thực hiện.")
            return redirect(self.get_success_url())
        response = super().form_valid(form)
        _save_article_attachments(self.object, self.request.user, attachments)
        save_article_revision(self.object, self.request.user, form.cleaned_data.get("change_summary", "Cập nhật"))
        return response


class ArticleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Article
    template_name = "wiki/article_confirm_delete.html"
    success_url = reverse_lazy("wiki:article-list")

    def get_object(self, queryset=None):
        if not hasattr(self, '_cached_object'):
            self._cached_object = get_object_or_404(Article, pk=self.kwargs.get("pk"))
        return self._cached_object

    def test_func(self):
        article = self.get_object()
        user = self.request.user
        return (user.is_superuser or user.has_perm("wiki.manage_all_articles")
                or (article.author == user and user.has_perm("wiki.delete_article")))

    def handle_no_permission(self):
        return redirect("wiki:article-list")


class ArticleHistoryView(DetailView):
    model = Article
    template_name = "wiki/article_history.html"
    context_object_name = "article"

    def get_object(self, queryset=None):
        article = get_object_or_404(Article, pk=self.kwargs.get("pk"))
        user = self.request.user
        if (article.status != "published" and not can_manage_wiki(user)
                and (not user.is_authenticated or article.author != user)):
            raise Http404
        return article

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["revisions"] = self.object.revisions.select_related("author").all()
        return context


class ArticleRevisionDetailView(DetailView):
    model = ArticleRevision
    template_name = "wiki/article_revision_detail.html"
    context_object_name = "revision"

    def get_object(self, queryset=None):
        revision = get_object_or_404(ArticleRevision, pk=self.kwargs.get("pk"))
        article = revision.article
        user = self.request.user
        if (article.status != "published" and not can_manage_wiki(user)
                and (not user.is_authenticated or article.author != user)):
            raise Http404
        return revision


class ModerationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Article
    template_name = "wiki/article_list.html"
    context_object_name = "articles"
    paginate_by = 20

    def test_func(self):
        return can_manage_wiki(self.request.user)

    def get_queryset(self):
        return Article.objects.filter(status="pending").select_related("author", "category").order_by("created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_moderation_view"] = True
        return context


@require_POST
@login_required
def approve_article(request, pk):
    if not can_manage_wiki(request.user):
        return HttpResponse("Unauthorized", status=403)
    article = get_object_or_404(Article, pk=pk)
    article.status = "published"
    article.save()
    return redirect("wiki:article-list")


@require_POST
@login_required
def reject_article(request, pk):
    if not can_manage_wiki(request.user):
        return HttpResponse("Unauthorized", status=403)
    article = get_object_or_404(Article, pk=pk)
    article.status = "rejected"
    article.save()
    return redirect("wiki:article-list")


@require_POST
@login_required
def request_changes_article(request, pk):
    if not can_manage_wiki(request.user):
        return HttpResponse("Unauthorized", status=403)
    article = get_object_or_404(Article, pk=pk)
    article.status = "needs_edit"
    article.save()
    return redirect("wiki:article-list")
