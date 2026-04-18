"""
URL configuration for the wiki application.
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    base, articles, users, voting, files, categories, quiz
)

app_name = 'wiki'

urlpatterns = [
    # Base
    path('', base.home_view, name='home'),
    path(
        'getting-started/',
        base.getting_started_view,
        name='getting-started'
    ),
    path('dismiss-guide/', base.dismiss_guide_view, name='dismiss-guide'),
    path('signup/', base.signup_view, name='signup'),

    # Articles (Specific routes first)
    path(
        'articles/',
        articles.ArticleListView.as_view(),
        name='article-list'
    ),
    path(
        'article/create/',
        articles.ArticleCreateView.as_view(),
        name='article-create'
    ),
    path(
        'article/<int:pk>/edit/',
        articles.ArticleUpdateView.as_view(),
        name='article-edit'
    ),
    path(
        'article/<int:pk>/delete/',
        articles.ArticleDeleteView.as_view(),
        name='article-delete'
    ),
    path(
        'article/<int:pk>/history/',
        articles.ArticleHistoryView.as_view(),
        name='article-history'
    ),
    path(
        'revision/<int:pk>/',
        articles.ArticleRevisionDetailView.as_view(),
        name='revision-detail'
    ),
    path(
        'revision/<int:pk>/detail/',
        articles.ArticleRevisionDetailView.as_view(),
        name='article-revision-detail'
    ),
    path(
        'article/<int:pk>/export-pdf/',
        articles.export_article_pdf,
        name='export-article-pdf'
    ),
    path(
        'article/<int:pk>/<slug:slug>/',
        articles.ArticleDetailView.as_view(),
        name='article-detail'
    ),

    # Categories
    path(
        'categories/',
        categories.CategoryListView.as_view(),
        name='category-list'
    ),
    path(
        'category/create/',
        categories.CategoryCreateView.as_view(),
        name='category-create'
    ),
    path(
        'category/<int:pk>/edit/',
        categories.CategoryUpdateView.as_view(),
        name='category-edit'
    ),
    path(
        'category/<int:pk>/delete/',
        categories.CategoryDeleteView.as_view(),
        name='category-delete'
    ),

    # Quiz
    path(
        'article/<int:article_pk>/quiz/manage/',
        quiz.article_quiz_manage_view,
        name='article-quiz-manage'
    ),
    path(
        'article/<int:article_pk>/quiz/submit/',
        quiz.submit_quiz_view,
        name='submit-quiz'
    ),

    # Files
    path('upload-files/', files.upload_file_view, name='upload-files'),

    # Voting
    path('article/<int:pk>/vote/', voting.vote_article, name='article-vote'),
    path('comment/<int:pk>/vote/', voting.vote_comment, name='comment-vote'),
    path('user/<str:username>/vote/', voting.vote_user, name='user-vote'),

    # Users
    path('users/', users.UserListView.as_view(), name='user-list'),
    path('profile/', users.profile_view, name='profile'),
    path('profile/edit/', users.profile_edit_view, name='profile-edit'),
    path('u/<str:username>/', users.public_profile_view, name='public-profile'),

    # Auth
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            redirect_authenticated_user=True
        ),
        name='login'
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
