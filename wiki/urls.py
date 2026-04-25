"""
URL configuration for the wiki application.
"""

from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from .views import (
    articles,
    base,
    categories,
    coding,
    files,
    moderation,
    quiz,
    search,
    users,
    voting,
)

app_name = "wiki"

urlpatterns = [
    # Base
    path("", base.home_view, name="home"),
    path("search/", search.search_view, name="search"),
    path("report-content/", moderation.report_content_view, name="report-content"),
    path("getting-started/", base.getting_started_view, name="getting-started"),
    path("dismiss-guide/", base.dismiss_guide_view, name="dismiss-guide"),
    path("signup/", base.signup_view, name="signup"),
    path("toggle-bookmark/<int:pk>/", base.toggle_bookmark_view, name="toggle-bookmark"),
    path("saved-articles/", base.saved_articles_view, name="saved-articles-json"),
    path("notifications/", base.NotificationListView.as_view(), name="notification-list"),
    path("notification/<int:pk>/read/", base.mark_notification_read, name="notification-read"),

    # Articles (Specific management routes first)
    path("articles/", articles.ArticleListView.as_view(), name="article-list"),
    path("article/create/", articles.ArticleCreateView.as_view(), name="article-create"),
    path("article/<int:pk>/edit/", articles.ArticleUpdateView.as_view(), name="article-edit"),
    path("article/<int:pk>/delete/", articles.ArticleDeleteView.as_view(), name="article-delete"),
    path("article/<int:pk>/history/", articles.ArticleHistoryView.as_view(), name="article-history"),

    path("revision/<int:pk>/", articles.ArticleRevisionDetailView.as_view(), name="revision-detail"),
    path("revision/<int:pk>/detail/", articles.ArticleRevisionDetailView.as_view(), name="article-revision-detail"),

    path("moderation/", articles.ModerationListView.as_view(), name="moderation-list"),
    path("article/<int:pk>/approve/", articles.approve_article, name="article-approve"),
    path("article/<int:pk>/reject/", articles.reject_article, name="article-reject"),
    path("article/<int:pk>/request-changes/", articles.request_changes_article, name="article-request-changes"),

    # Voting (Specific patterns MUST come before the catch-all article detail slug)
    path("article/<int:pk>/vote/", voting.vote_article, name="article-vote"),
    path("comment/<int:pk>/vote/", voting.vote_comment, name="comment-vote"),
    path("user/<str:username>/vote/", voting.vote_user, name="user-vote"),

    # Article Detail (Catch-all slug pattern)
    path("article/<int:pk>/<slug:slug>/", articles.ArticleDetailView.as_view(), name="article-detail"),

    # Categories
    path("categories/", categories.CategoryListView.as_view(), name="category-list"),
    path("category/create/", categories.CategoryCreateView.as_view(), name="category-create"),
    path("category/<int:pk>/edit/", categories.CategoryUpdateView.as_view(), name="category-edit"),
    path("category/<int:pk>/delete/", categories.CategoryDeleteView.as_view(), name="category-delete"),

    # Quiz
    path("article/<int:article_pk>/quiz/manage/", quiz.article_quiz_manage_view, name="article-quiz-manage"),
    path("article/<int:article_pk>/quiz/submit/", quiz.submit_quiz_view, name="submit-quiz"),
    path("article/<int:article_pk>/quiz/upload/", quiz.upload_quiz_file_view, name="upload-quiz-file"),
    path("article/<int:article_pk>/quiz/question/create/", quiz.QuestionCreateView.as_view(), name="question-create"),
    path("question/<int:pk>/edit/", quiz.QuestionUpdateView.as_view(), name="question-edit"),
    path("question/<int:pk>/delete/", quiz.QuestionDeleteView.as_view(), name="question-delete"),

    # Coding exercise
    path("article/<int:article_pk>/coding/manage/", coding.article_coding_manage_view, name="article-coding-manage"),
    path("exercise/<int:exercise_pk>/testcase/create/", coding.CodingTestCaseCreateView.as_view(), name="coding-testcase-create"),
    path("coding-testcase/<int:pk>/edit/", coding.CodingTestCaseUpdateView.as_view(), name="coding-testcase-edit"),
    path("coding-testcase/<int:pk>/delete/", coding.CodingTestCaseDeleteView.as_view(), name="coding-testcase-delete"),
    path("article/<int:article_pk>/coding/run/", coding.run_code_view, name="run-code"),
    path("article/<int:article_pk>/coding/submit/", coding.submit_code_view, name="submit-code"),

    # Files
    path("upload-files/", files.upload_file_view, name="upload-files"),

    # Users
    path("users/", users.UserListView.as_view(), name="user-list"),
    path("profile/", users.profile_view, name="profile"),
    path("profile/edit/", users.profile_edit_view, name="profile-edit"),
    path("u/<str:username>/", users.public_profile_view, name="public-profile"),

    # Auth
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-change/", auth_views.PasswordChangeView.as_view(template_name="registration/password_change_form.html", success_url=reverse_lazy("wiki:password_change_done")), name="password-change"),
    path("password-change/done/", auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
]
