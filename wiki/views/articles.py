from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from ..models import Article, Category, ArticleRevision, Bookmark
from ..forms import ArticleForm, CommentForm
from ..services.code_runner import get_enabled_language_choices, get_language_config
from ..utils import save_article_revision, can_publish_articles, can_manage_wiki

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
            vote_score=(
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
                "starterCodeMap": coding_starter_map,
                "monacoMap": coding_monaco_map,
                "samples": coding_samples,
            }
        context.update({
            "comments": article.comments.select_related("author").filter(is_approved=True),
            "related_articles": Article.objects.filter(category=article.category, status="published")
                .exclude(pk=article.pk).annotate(comment_count=Count("comments", distinct=True))[:3],
            "comment_form": kwargs.get("comment_form", CommentForm()),
            "can_comment": (article.allow_comments and user.is_authenticated and user.has_perm("wiki.add_comment")),
            "commenting_locked": not article.allow_comments,
            "can_edit_article": (can_manage or (user.is_authenticated and article.author == user and user.has_perm("wiki.change_article"))),
            "can_delete_article": (can_manage or (user.is_authenticated and article.author == user and user.has_perm("wiki.delete_article"))),
            "article_vote_score": article.vote_score,
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
        if not self.object.allow_comments or not request.user.is_authenticated:
            return redirect(self.object.get_absolute_url())
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = self.object
            comment.author = request.user
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
        form.instance.author = self.request.user
        response = super().form_valid(form)
        save_article_revision(self.object, self.request.user, form.cleaned_data.get("change_summary", "Initial"))
        return response

class ArticleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = "wiki/article_form.html"
    def get_object(self, queryset=None):
        return get_object_or_404(Article, pk=self.kwargs.get("pk"))
    def test_func(self):
        article = self.get_object()
        user = self.request.user
        return (user.is_superuser or user.has_perm("wiki.manage_all_articles") or (article.author == user and user.has_perm("wiki.change_article")))
    def handle_no_permission(self):
        return redirect("wiki:article-list")
    def form_valid(self, form):
        article_fields = ["title", "slug", "content", "category", "tags", "allow_comments"]
        if not any(f in form.changed_data for f in article_fields):
            messages.info(self.request, "Không có thay đổi nào được thực hiện.")
            return redirect(self.get_success_url())
        response = super().form_valid(form)
        save_article_revision(self.object, self.request.user, form.cleaned_data.get("change_summary", "Cập nhật"))
        return response

class ArticleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Article
    template_name = "wiki/article_confirm_delete.html"
    success_url = reverse_lazy("wiki:article-list")
    def get_object(self, queryset=None):
        return get_object_or_404(Article, pk=self.kwargs.get("pk"))
    def test_func(self):
        article = self.get_object()
        user = self.request.user
        return (user.is_superuser or user.has_perm("wiki.manage_all_articles") or (article.author == user and user.has_perm("wiki.delete_article")))
    def handle_no_permission(self):
        return redirect("wiki:article-list")

class ArticleHistoryView(DetailView):
    model = Article
    template_name = "wiki/article_history.html"
    context_object_name = "article"
    def get_object(self, queryset=None):
        article = get_object_or_404(Article, pk=self.kwargs.get("pk"))
        user = self.request.user
        if (article.status != "published" and not can_manage_wiki(user) and (not user.is_authenticated or article.author != user)):
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
        if (article.status != "published" and not can_manage_wiki(user) and (not user.is_authenticated or article.author != user)):
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