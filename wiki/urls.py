from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import LoginForm

app_name = 'wiki'

urlpatterns = [
    path('', views.HomeRedirectView.as_view(), name='home'),
    path('articles/', views.ArticleListView.as_view(), name='article-list'),
    path('articles/create/', views.ArticleCreateView.as_view(), name='article-create'),
    path('articles/<int:pk>/edit/', views.ArticleUpdateView.as_view(), name='article-edit'),
    path('articles/<int:pk>/delete/', views.ArticleDeleteView.as_view(), name='article-delete'),
    path('articles/<int:article_pk>/quiz/', views.ArticleQuizManageView.as_view(), name='article-quiz-manage'),
    path('articles/<int:article_pk>/quiz/add/', views.QuestionCreateView.as_view(), name='question-create'),
    path('questions/<int:pk>/edit/', views.QuestionUpdateView.as_view(), name='question-edit'),
    path('questions/<int:pk>/delete/', views.QuestionDeleteView.as_view(), name='question-delete'),
    path('articles/<int:article_pk>/quiz/submit/', views.SubmitQuizView.as_view(), name='submit-quiz'),
    path('articles/<int:pk>/vote/', views.vote_article, name='article-vote'),
    path('articles/<int:pk>/<slug:slug>/', views.ArticleDetailView.as_view(), name='article-detail'),
    path('comments/<int:pk>/vote/', views.vote_comment, name='comment-vote'),
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category-edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),
    path('signup/', views.signup_view, name='signup'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path(
        'password-change/',
        auth_views.PasswordChangeView.as_view(
            template_name='registration/password_change_form.html',
            success_url=reverse_lazy('wiki:password-change-done'),
        ),
        name='password-change',
    ),
    path(
        'password-change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='registration/password_change_done.html'
        ),
        name='password-change-done',
    ),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/vote/', views.vote_user, name='user-vote'),
    path('users/<int:pk>/', views.public_profile_view, name='public-profile'),
    path('files/upload/', views.upload_file_view, name='upload-files'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile-edit'),
    path('getting-started/', views.getting_started_view, name='getting-started'),
    path('dismiss-guide/', views.dismiss_guide_view, name='dismiss-guide'),
]
