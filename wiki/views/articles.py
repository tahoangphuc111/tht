"""
Views for handling articles in the wiki app.
"""

import random
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from xhtml2pdf import pisa

from ..models import Article, Category, ArticleRevision, Bookmark
from ..forms import ArticleForm, CommentForm
from ..utils import save_article_revision, can_publish_articles


class ArticleListView(ListView):
    """View to list all articles with filtering and sorting."""

    model = Article
    template_name = "wiki/article_list.html"
    context_object_name = "articles"
    paginate_by = 10

    def get_queryset(self):
        """Annotate and filter the article queryset."""
        user = self.request.user
        can_manage = user.is_authenticated and (
            user.is_superuser or user.has_perm("wiki.manage_all_articles")
        )

        qs = Article.objects.select_related("author", "category").annotate(
            comment_count=Count("comments", distinct=True),
            vote_balance=(
                Count("article_votes", filter=Q(article_votes__value=1), distinct=True)
                - Count(
                    "article_votes", filter=Q(article_votes__value=-1), distinct=True
                )
            ),
        )

        # Non-managers only see published articles
        if not can_manage:
            qs = qs.filter(status="published")

        q = self.request.GET.get("q", "")
        auth = self.request.GET.get("author", "")
        cat = self.request.GET.get("category", "")
        tag = self.request.GET.get("tag", "")
        sort = self.request.GET.get("sort", "newest")
        status = self.request.GET.get("status", "")

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
        """Add filtering options to context."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "query": self.request.GET.get("q", ""),
                "categories": Category.objects.all(),
                "can_publish": can_publish_articles(self.request.user),
            }
        )
        return context


class ArticleDetailView(DetailView):
    """View to display article details and comments."""

    model = Article
    template_name = "wiki/article_detail.html"
    context_object_name = "article"
    query_pk_and_slug = True

    def get_queryset(self):
        """Restrict access to non-published articles."""
        user = self.request.user
        qs = super().get_queryset()
        if user.is_authenticated and (
            user.is_superuser or user.has_perm("wiki.manage_all_articles")
        ):
            return qs
        return qs.filter(Q(status="published") | Q(author=user))

    def get_context_data(self, **kwargs):
        """Add comments and permissions to context."""
        context = super().get_context_data(**kwargs)
        article = self.object
        user = self.request.user
        can_manage = user.is_authenticated and (
            user.is_superuser or user.has_perm("wiki.manage_all_articles")
        )
        context.update(
            {
                "comments": article.comments.select_related("author").filter(
                    is_approved=True
                ),
                "related_articles": Article.objects.filter(
                    category=article.category
                ).exclude(pk=article.pk)[:3],
                "comment_form": CommentForm(),
                "can_comment": (
                    article.allow_comments
                    and user.is_authenticated
                    and user.has_perm("wiki.add_comment")
                ),
                "can_edit_article": (
                    can_manage
                    or (
                        user.is_authenticated
                        and article.author == user
                        and user.has_perm("wiki.change_article")
                    )
                ),
                "can_delete_article": (
                    can_manage
                    or (
                        user.is_authenticated
                        and article.author == user
                        and user.has_perm("wiki.delete_article")
                    )
                ),
                "captcha_question": (
                    f"{random.randint(1, 8)} + {random.randint(1, 8)} = ?"
                ),
                "article_vote_score": article.vote_score,
                "is_bookmarked": user.is_authenticated and Bookmark.objects.filter(user=user, article=article).exists(),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        """Handle comment submission."""
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
    """View to create a new article."""

    model = Article
    form_class = ArticleForm
    template_name = "wiki/article_form.html"

    def test_func(self):
        """Check if user can publish articles."""
        return can_publish_articles(self.request.user)

    def handle_no_permission(self):
        """Redirect to article list if logged in but no permission."""
        if self.request.user.is_authenticated:
            return redirect("wiki:article-list")
        return super().handle_no_permission()

    def form_valid(self, form):
        """Set author and save revision on success."""
        form.instance.author = self.request.user
        response = super().form_valid(form)
        save_article_revision(
            self.object,
            self.request.user,
            form.cleaned_data.get("change_summary", "Initial"),
        )
        return response


class ArticleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View to update an existing article."""

    model = Article
    form_class = ArticleForm
    template_name = "wiki/article_form.html"

    def get_object(self, queryset=None):
        """Retrieve the article by primary key."""
        return get_object_or_404(Article, pk=self.kwargs.get("pk"))

    def test_func(self):
        """Check if user has permission to update the article."""
        article = self.get_object()
        user = self.request.user
        return (
            user.is_superuser
            or user.has_perm("wiki.manage_all_articles")
            or (article.author == user and user.has_perm("wiki.change_article"))
        )

    def handle_no_permission(self):
        """Redirect to article list on permission error."""
        return redirect("wiki:article-list")

    def form_valid(self, form):
        """Save revision on success."""
        response = super().form_valid(form)
        save_article_revision(
            self.object, self.request.user, form.cleaned_data.get("change_summary", "")
        )
        return response


class ArticleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View to delete an article."""

    model = Article
    template_name = "wiki/article_confirm_delete.html"
    success_url = reverse_lazy("wiki:article-list")

    def get_object(self, queryset=None):
        """Retrieve the article by primary key."""
        return get_object_or_404(Article, pk=self.kwargs.get("pk"))

    def test_func(self):
        """Check if user has permission to delete the article."""
        article = self.get_object()
        user = self.request.user
        return (
            user.is_superuser
            or user.has_perm("wiki.manage_all_articles")
            or (article.author == user and user.has_perm("wiki.delete_article"))
        )

    def handle_no_permission(self):
        """Redirect to article list on permission error."""
        return redirect("wiki:article-list")


class ArticleHistoryView(DetailView):
    """View to show article revision history."""

    model = Article
    template_name = "wiki/article_history.html"
    context_object_name = "article"

    def get_object(self, queryset=None):
        """Retrieve the article by primary key."""
        return get_object_or_404(Article, pk=self.kwargs.get("pk"))

    def get_context_data(self, **kwargs):
        """Add revisions to context."""
        context = super().get_context_data(**kwargs)
        context["revisions"] = self.object.revisions.select_related("author").all()
        return context


class ArticleRevisionDetailView(DetailView):
    """View to show details of a specific revision."""

    model = ArticleRevision
    template_name = "wiki/article_revision_detail.html"
    context_object_name = "revision"

    def get_object(self, queryset=None):
        """Retrieve the revision by primary key."""
        return get_object_or_404(ArticleRevision, pk=self.kwargs.get("pk"))


@login_required
def export_article_pdf(request, pk):
    """Export an article to PDF format."""
    article = get_object_or_404(Article, pk=pk)
    html = render_to_string(
        "wiki/article_pdf.html", {"article": article, "request": request}
    )
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{article.slug}.pdf"'
    if pisa.CreatePDF(html, dest=response).err:
        return HttpResponse("Lỗi PDF", status=500)
    return response


class ModerationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for admins to see articles pending moderation."""

    model = Article
    template_name = "wiki/article_list.html"  # Reuse list template
    context_object_name = "articles"
    paginate_by = 20

    def test_func(self):
        """Only admins and managers can see this list."""
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or user.has_perm("wiki.manage_all_articles")
        )

    def get_queryset(self):
        """Filter for pending articles."""
        return (
            Article.objects.filter(status="pending")
            .select_related("author", "category")
            .order_by("created_at")
        )

    def get_context_data(self, **kwargs):
        """Add context for moderation mode."""
        context = super().get_context_data(**kwargs)
        context["is_moderation_view"] = True
        return context


@login_required
def approve_article(request, pk):
    """Approve a pending article."""
    if not (request.user.is_superuser or request.user.has_perm("wiki.manage_all_articles")):
        return HttpResponse("Unauthorized", status=403)

    article = get_object_or_404(Article, pk=pk)
    article.status = "published"
    article.save()
    return redirect("wiki:article-list")


@login_required
def reject_article(request, pk):
    """Reject a pending article."""
    if not (request.user.is_superuser or request.user.has_perm("wiki.manage_all_articles")):
        return HttpResponse("Unauthorized", status=403)

    article = get_object_or_404(Article, pk=pk)
    article.status = "rejected"
    article.save()
    return redirect("wiki:article-list")
