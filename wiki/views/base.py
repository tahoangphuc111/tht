"""
Base views for the wiki application.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.db.models import Count
from django.http import JsonResponse
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from ..models import Article, Category, Comment, Bookmark, Notification
from ..forms import SignUpForm
from ..utils import can_publish_articles


def home_view(request):
    """Homepage view showing featured, latest and top items."""
    featured = (
        Article.objects.select_related("author", "category")
        .annotate(comment_count=Count("comments"))
        .order_by("-updated_at")
        .first()
    )

    context = {
        "featured_article": featured,
        "latest_articles": Article.objects.select_related(
            "author", "category"
        ).order_by("-created_at")[:4],
        "recent_comments": Comment.objects.select_related("author", "article")
        .filter(is_approved=True)
        .order_by("-created_at")[:5],
        "top_categories": Category.objects.annotate(
            article_total=Count("articles")
        ).order_by("-article_total")[:6],
        "total_articles": Article.objects.count(),
        "total_comments": Comment.objects.filter(is_approved=True).count(),
        "can_publish": can_publish_articles(request.user),
    }
    return render(request, "wiki/home.html", context)


def signup_view(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect("wiki:home")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            group = Group.objects.filter(name="user").first()
            if group:
                user.groups.add(group)
            login(request, user)
            messages.success(request, "Tạo tài khoản thành công!")
            return redirect("wiki:getting-started")
    else:
        form = SignUpForm()
    return render(request, "wiki/signup.html", {"form": form})


def getting_started_view(request):
    """Introductory guide for new users."""
    return render(request, "wiki/getting_started.html")


@login_required
def dismiss_guide_view(request):
    """Mark the getting-started guide as seen by the user."""
    profile = request.user.profile
    profile.guide_seen = True
    profile.save(update_fields=["guide_seen"])
    next_url = request.POST.get("next") or reverse_lazy("wiki:article-list")
    return HttpResponseRedirect(next_url)


@login_required
def toggle_bookmark_view(request, pk):
    """AJAX view to bookmark or unbookmark an article."""
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    article = get_object_or_404(Article, pk=pk)
    bookmark, created = Bookmark.objects.get_or_create(user=request.user, article=article)

    if not created:
        bookmark.delete()
        is_bookmarked = False
    else:
        is_bookmarked = True

    return JsonResponse(
        {"is_bookmarked": is_bookmarked, "count": request.user.bookmarks.count()}
    )


@login_required
def saved_articles_view(request):
    """View returning a user's bookmarked articles as JSON."""
    bookmarks = Bookmark.objects.filter(user=request.user).select_related("article")
    data = [
        {
            "id": b.article.id,
            "title": b.article.title,
            "url": b.article.get_absolute_url(),
            "category": b.article.category.name if b.article.category else "N/A",
        }
        for b in bookmarks
    ]
    return JsonResponse({"bookmarks": data})


class NotificationListView(LoginRequiredMixin, ListView):
    """View to display all in-app notifications for the current user."""

    model = Notification
    template_name = "wiki/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        """Filter notifications for the logged-in user."""
        return Notification.objects.filter(recipient=self.request.user)


@login_required
def mark_notification_read(request, pk):
    """AJAX view to mark a specific notification as read."""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return JsonResponse({"success": True})


from django.shortcuts import get_object_or_404
