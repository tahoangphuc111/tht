from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from config.asgi import broadcast_vote_update
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group, User
from django.db.models import Count, Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
import random
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
import json
import docx
from PyPDF2 import PdfReader
from io import BytesIO
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.http import HttpResponse, JsonResponse
from .forms import ArticleForm, CategoryForm, CommentForm, ProfileForm, SignUpForm, UserUpdateForm, UploadFileForm, QuestionForm, ChoiceFormSet
from .models import Article, Category, Comment, UploadedFile, ArticleVote, CommentVote, UserVote, Question, Choice, UserAnswer, ArticleRevision

PUBLISHER_ROLES = ['admin', 'editor', 'contributor']


def save_article_revision(article, user, change_summary):
    ArticleRevision.objects.create(
        article=article,
        title=article.title,
        content=article.content,
        author=user,
        change_summary=change_summary
    )


def can_publish_articles(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.groups.filter(name__in=PUBLISHER_ROLES).exists()
        or user.has_perm('wiki.add_article')
    )


def get_profile_name(user):
    return user.profile.display_name or user.get_full_name() or user.username


def can_view_profile(viewer, target_user):
    if not hasattr(target_user, 'profile'):
        return False
    if viewer.is_authenticated and (viewer == target_user or viewer.is_superuser):
        return True
    return not target_user.profile.is_profile_private


def build_profile_stats(user):
    articles = list(user.articles.select_related('category').order_by('-updated_at'))
    comments = list(user.comments.select_related('article').order_by('-created_at'))
    now = timezone.localdate()
    start_date = now - timedelta(days=83)
    contribution_map = defaultdict(int)

    for article in articles:
        created_day = timezone.localtime(article.created_at).date()
        if created_day >= start_date:
            contribution_map[created_day] += 1

        updated_day = timezone.localtime(article.updated_at).date()
        if updated_day >= start_date and updated_day != created_day:
            contribution_map[updated_day] += 1

    contribution_days = []
    current_day = start_date
    max_count = 0
    while current_day <= now:
        count = contribution_map[current_day]
        max_count = max(max_count, count)
        contribution_days.append({
            'date': current_day,
            'count': count,
        })
        current_day += timedelta(days=1)

    for day in contribution_days:
        count = day['count']
        if count == 0:
            level = 0
        elif count == 1:
            level = 1
        elif count == 2:
            level = 2
        elif count == 3:
            level = 3
        else:
            level = 4
        day['level'] = level
        day['label'] = f"{day['date'].strftime('%d/%m/%Y')}: {count} contribution"

    month_labels = []
    post_series = []
    edit_series = []
    for offset in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=offset * 30)).replace(day=1)
        label = month_start.strftime('%m/%Y')
        month_labels.append(label)
        post_count = 0
        edit_count = 0
        for article in articles:
            created_day = timezone.localtime(article.created_at).date()
            updated_day = timezone.localtime(article.updated_at).date()
            if created_day.month == month_start.month and created_day.year == month_start.year:
                post_count += 1
            if updated_day != created_day and updated_day.month == month_start.month and updated_day.year == month_start.year:
                edit_count += 1
        post_series.append(post_count)
        edit_series.append(edit_count)

    edited_articles = sum(
        1
        for article in articles
        if timezone.localtime(article.updated_at).date() != timezone.localtime(article.created_at).date()
    )

    return {
        'articles': articles,
        'comments': comments,
        'article_count': len(articles),
        'comment_count': len(comments),
        'edited_articles_count': edited_articles,
        'recent_articles': articles[:5],
        'recent_comments': comments[:5],
        'contribution_days': contribution_days,
        'chart_labels': month_labels,
        'chart_posts': post_series,
        'chart_edits': edit_series,
        'total_contributions': sum(item['count'] for item in contribution_days),
        'user_vote_score': user.profile.vote_score if hasattr(user, 'profile') else 0,
    }


def build_profile_context(target_user, viewer):
    profile = target_user.profile
    profile_name = get_profile_name(target_user)
    is_own_profile = viewer.is_authenticated and viewer == target_user
    can_view_full_profile = can_view_profile(viewer, target_user)
    public_email = ''

    if target_user.email and (is_own_profile or viewer.is_superuser or (can_view_full_profile and profile.show_email_publicly)):
        public_email = target_user.email

    context = {
        'profile_user': target_user,
        'profile': profile,
        'profile_name': profile_name,
        'role_names': list(target_user.groups.order_by('name').values_list('name', flat=True)),
        'total_users': User.objects.count(),
        'is_own_profile': is_own_profile,
        'can_view_profile': can_view_full_profile,
        'public_email': public_email,
        'profile_link': reverse('wiki:public-profile', kwargs={'username': target_user.username}),
        'joined_date': timezone.localtime(target_user.date_joined),
        'recent_uploads': list(target_user.uploaded_files.order_by('-created_at')[:5]),
        'upload_count': target_user.uploaded_files.count(),
        'author_articles_url': reverse('wiki:article-list') + f'?author={target_user.username}',
    }

    if can_view_full_profile:
        context.update(build_profile_stats(target_user))
    return context


class HomeRedirectView(TemplateView):
    template_name = 'wiki/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        featured_article = (
            Article.objects.select_related('author', 'category')
            .annotate(comment_count=Count('comments'))
            .order_by('-updated_at')
            .first()
        )
        latest_articles = (
            Article.objects.select_related('author', 'category')
            .annotate(comment_count=Count('comments'))
            .order_by('-created_at')[:4]
        )
        recent_comments = (
            Comment.objects.select_related('author', 'article')
            .filter(is_approved=True)
            .order_by('-created_at')[:5]
        )
        top_categories = (
            Category.objects.annotate(article_total=Count('articles'))
            .order_by('-article_total', 'name')[:6]
        )
        stats = Article.objects.aggregate(
            total_articles=Count('id'),
            open_comments=Count('id', filter=Q(allow_comments=True)),
        )
        context.update({
            'featured_article': featured_article,
            'latest_articles': latest_articles,
            'recent_comments': recent_comments,
            'top_categories': top_categories,
            'total_articles': stats['total_articles'] or 0,
            'open_comment_articles': stats['open_comments'] or 0,
            'total_categories': Category.objects.count(),
            'total_comments': Comment.objects.filter(is_approved=True).count(),
            'can_publish': can_publish_articles(self.request.user),
        })
        return context


class ArticleListView(ListView):
    model = Article
    template_name = 'wiki/article_list.html'
    context_object_name = 'articles'
    paginate_by = 10

    def get_queryset(self):
        queryset = Article.objects.select_related('author', 'category').annotate(
            comment_count=Count('comments', distinct=True),
            vote_balance=Count('article_votes', filter=Q(article_votes__value=1), distinct=True)
            - Count('article_votes', filter=Q(article_votes__value=-1), distinct=True),
        ).order_by('-created_at')
        query = self.request.GET.get('q', '').strip()
        author_query = self.request.GET.get('author', '').strip()
        category_slug = self.request.GET.get('category', '').strip()
        sort = self.request.GET.get('sort', 'newest').strip()
        discussion = self.request.GET.get('discussion', '').strip()

        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(content__icontains=query))
        if author_query:
            queryset = queryset.filter(author__username__icontains=author_query)
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        if discussion == 'open':
            queryset = queryset.filter(allow_comments=True)
        elif discussion == 'locked':
            queryset = queryset.filter(allow_comments=False)

        if sort == 'updated':
            queryset = queryset.order_by('-updated_at', '-created_at')
        elif sort == 'commented':
            queryset = queryset.order_by('-comment_count', '-created_at')
        elif sort == 'top':
            queryset = queryset.order_by('-vote_balance', '-comment_count', '-updated_at')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '').strip()
        context['selected_author'] = self.request.GET.get('author', '').strip()
        context['selected_category'] = self.request.GET.get('category', '').strip()
        context['selected_sort'] = self.request.GET.get('sort', 'newest').strip()
        context['selected_discussion'] = self.request.GET.get('discussion', '').strip()
        context['categories'] = Category.objects.all()
        context['can_publish'] = can_publish_articles(self.request.user)
        return context


class ArticleDetailView(DetailView):
    model = Article
    template_name = 'wiki/article_detail.html'
    context_object_name = 'article'
    query_pk_and_slug = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        user = self.request.user
        can_manage_any = user.is_authenticated and (
            user.is_superuser or user.has_perm('wiki.manage_all_articles')
        )

        context['comments'] = article.comments.select_related('author').filter(is_approved=True)
        context['related_articles'] = (
            Article.objects.select_related('author', 'category')
            .annotate(comment_count=Count('comments'))
            .filter(category=article.category)
            .exclude(pk=article.pk)
            .order_by('-updated_at')[:3]
        )
        context['comment_form'] = CommentForm()
        context['can_publish'] = can_publish_articles(user)
        context['can_comment'] = (
            article.allow_comments
            and user.is_authenticated
            and user.has_perm('wiki.add_comment')
        )
        context['commenting_locked'] = not article.allow_comments
        context['can_edit_article'] = can_manage_any or (
            user.is_authenticated and article.author == user and user.has_perm('wiki.change_article')
        )
        context['can_delete_article'] = can_manage_any or (
            user.is_authenticated and article.author == user and user.has_perm('wiki.delete_article')
        )

        # captcha for non-Google robot check
        a = random.randint(1, 8)
        b = random.randint(1, 8)
        self.request.session['captcha_answer'] = a + b
        context['captcha_question'] = f'{a} + {b} = ?'

        # vote summaries
        context['article_vote_score'] = article.vote_score
        context['article_upvotes'] = article.upvotes
        context['article_downvotes'] = article.downvotes
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.allow_comments:
            messages.error(request, 'Bài viết này hiện đã tắt bình luận.')
            return redirect(self.object.get_absolute_url())
        if not request.user.is_authenticated or not request.user.has_perm('wiki.add_comment'):
            messages.error(request, 'Bạn cần đăng nhập để bình luận.')
            return redirect('wiki:login')

        captcha_input = request.POST.get('captcha_answer')
        expected = request.session.get('captcha_answer')
        if expected is None or str(expected) != str(captcha_input):
            messages.error(request, 'Xác thực không phải robot thất bại. Vui lòng thử lại.')
            context = self.get_context_data()
            context['comment_form'] = CommentForm(request.POST)
            return self.render_to_response(context)

        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = self.object
            comment.author = request.user
            comment.save()
            messages.success(request, 'Đã thêm bình luận.')
            return redirect(self.object.get_absolute_url())

        context = self.get_context_data()
        context['comment_form'] = form
        return self.render_to_response(context)


class ArticlePermissionMixin(UserPassesTestMixin):
    required_permission = ''

    def test_func(self):
        article = self.get_object()
        user = self.request.user
        return (
            user.is_superuser
            or user.has_perm('wiki.manage_all_articles')
            or (user.has_perm(self.required_permission) and article.author == user)
        )

    def handle_no_permission(self):
        messages.error(self.request, 'Bạn không có quyền chỉnh sửa bài viết này.')
        article = self.get_object()
        return redirect('wiki:article-detail', pk=article.pk, slug=article.slug)


class ArticleCreateView(LoginRequiredMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = 'wiki/article_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not can_publish_articles(request.user):
            messages.error(
                request,
                'Chỉ admin, editor hoặc contributor mới có quyền đăng bài. Người dùng thường chỉ có thể bình luận.',
            )
            return redirect('wiki:article-list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)
        save_article_revision(self.object, self.request.user, form.cleaned_data.get('change_summary', 'Initial revision'))
        files = self.request.FILES.getlist('attachments')
        for f in files[:5]:
            UploadedFile.objects.create(user=self.request.user, article=self.object, file=f)
        messages.success(self.request, 'Đã tạo bài viết mới.')
        return response


class ArticleUpdateView(LoginRequiredMixin, ArticlePermissionMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'wiki/article_form.html'
    required_permission = 'wiki.change_article'

    def form_valid(self, form):
        response = super().form_valid(form)
        save_article_revision(self.object, self.request.user, form.cleaned_data.get('change_summary', ''))
        files = self.request.FILES.getlist('attachments')
        for f in files[:5]:
            UploadedFile.objects.create(user=self.request.user, article=self.object, file=f)
        messages.success(self.request, 'Đã cập nhật bài viết.')
        return response


class ArticleHistoryView(DetailView):
    model = Article
    template_name = 'wiki/article_history.html'
    context_object_name = 'article'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['revisions'] = self.object.revisions.select_related('author').all()
        return context


class ArticleRevisionDetailView(DetailView):
    model = ArticleRevision
    template_name = 'wiki/article_revision_detail.html'
    context_object_name = 'revision'


class ArticleDeleteView(LoginRequiredMixin, ArticlePermissionMixin, DeleteView):
    model = Article
    template_name = 'wiki/article_confirm_delete.html'
    success_url = reverse_lazy('wiki:article-list')
    required_permission = 'wiki.delete_article'

    def form_valid(self, form):
        messages.success(self.request, 'Đã xóa bài viết.')
        return super().form_valid(form)


class CategoryManagePermissionMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name='admin').exists()

    def handle_no_permission(self):
        messages.error(self.request, 'Chỉ admin mới có thể quản lý danh mục.')
        return redirect('wiki:article-list')


class CategoryListView(LoginRequiredMixin, CategoryManagePermissionMixin, ListView):
    model = Category
    template_name = 'wiki/category_list.html'
    context_object_name = 'categories'


class CategoryCreateView(LoginRequiredMixin, CategoryManagePermissionMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'wiki/category_form.html'
    success_url = reverse_lazy('wiki:category-list')

    def form_valid(self, form):
        messages.success(self.request, 'Đã tạo danh mục.')
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, CategoryManagePermissionMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'wiki/category_form.html'
    success_url = reverse_lazy('wiki:category-list')

    def form_valid(self, form):
        messages.success(self.request, 'Đã cập nhật danh mục.')
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, CategoryManagePermissionMixin, DeleteView):
    model = Category
    template_name = 'wiki/category_confirm_delete.html'
    success_url = reverse_lazy('wiki:category-list')

    def form_valid(self, form):
        messages.success(self.request, 'Đã xóa danh mục.')
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                'Không thể xóa danh mục này vì vẫn còn bài viết đang sử dụng.',
            )
            return redirect('wiki:category-list')


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('wiki:article-list')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            default_group = Group.objects.filter(name='user').first()
            if default_group:
                user.groups.add(default_group)
            login(request, user)
            messages.success(request, 'Tạo tài khoản thành công. Chào mừng bạn đến với wiki!')
            return redirect('wiki:getting-started')
    else:
        form = SignUpForm()
    return render(request, 'wiki/signup.html', {'form': form})


@login_required
def profile_view(request):
    if request.method == 'POST':
        return redirect('wiki:profile-edit')
    return render(request, 'wiki/profile.html', build_profile_context(request.user, request.user))


def public_profile_view(request, username):
    target_user = get_object_or_404(User.objects.select_related('profile'), username=username)
    context = build_profile_context(target_user, request.user)
    if not context['can_view_profile']:
        messages.info(request, 'Người dùng này đã đặt hồ sơ ở chế độ riêng tư.')
    return render(request, 'wiki/profile.html', context)


@login_required
def upload_file_view(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.user = request.user
            upload.save()
            messages.success(request, 'Upload file thành công.')
            return redirect('wiki:upload-files')
    else:
        form = UploadFileForm()

    uploads = UploadedFile.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'wiki/upload_files.html', {'form': form, 'uploads': uploads})


class UserListView(ListView):
    model = User
    template_name = 'wiki/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            User.objects.select_related('profile').annotate(
                article_count=Count('articles', distinct=True),
                comment_count=Count('comments', distinct=True),
                vote_score=Count('user_votes', filter=Q(user_votes__value=1)) - Count('user_votes', filter=Q(user_votes__value=-1)),
            )
            .order_by('-vote_score', '-article_count', 'username')
        )
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(profile__display_name__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['query'] = self.request.GET.get('q', '').strip()
        return context



def _handle_vote(request, model, target_field, target_obj, vote_attr):
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Bạn cần đăng nhập.'}, status=401)
        return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))

    try:
        val = int(request.POST.get('vote', 0))
        if val not in (1, -1): raise ValueError
    except ValueError:
        return redirect(target_obj.get_absolute_url()) if hasattr(target_obj, 'get_absolute_url') else redirect('wiki:home')

    model.objects.update_or_create(
        **{'user' if target_field != 'target' else 'voter': request.user, target_field: target_obj},
        defaults={'value': val}
    )
    
    # Refresh object to get updated properties
    target_obj.refresh_from_db()
    payload = {
        f'{vote_attr}_score': target_obj.vote_score,
        f'{vote_attr}_upvotes': target_obj.upvotes,
        f'{vote_attr}_downvotes': target_obj.downvotes,
        f'{vote_attr}_pk': target_obj.pk
    }
    
    try: broadcast_vote_update(payload)
    except: pass

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Cập nhật thành công.', **payload})
    return redirect(target_obj.get_absolute_url())

def vote_article(request, pk):
    return _handle_vote(request, ArticleVote, 'article', get_object_or_404(Article, pk=pk), 'article')

def vote_comment(request, pk):
    return _handle_vote(request, CommentVote, 'comment', get_object_or_404(Comment, pk=pk), 'comment')

def vote_user(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse({'success': False, 'message': 'Không thể vote chính mình.'}, status=400)
    return _handle_vote(request, UserVote, 'target', target, 'target_user')



@login_required
def profile_edit_view(request):
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Đã cập nhật thông tin tài khoản.')
            return redirect('wiki:profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.profile)
    return render(
        request,
        'wiki/profile_edit.html',
        {
            'user_form': user_form,
            'profile_form': profile_form,
        },
    )


def getting_started_view(request):
    return render(request, 'wiki/getting_started.html')


@login_required
def dismiss_guide_view(request):
    profile = request.user.profile
    profile.guide_seen = True
    profile.save(update_fields=['guide_seen'])
    messages.success(request, 'Đã ẩn hướng dẫn dành cho người dùng mới.')
    next_url = request.POST.get('next') or reverse_lazy('wiki:article-list')
    return HttpResponseRedirect(next_url)


class QuizPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        if 'article_pk' in self.kwargs:
            article = get_object_or_404(Article, pk=self.kwargs['article_pk'])
        elif hasattr(self, 'get_object'):
            obj = self.get_object()
            if isinstance(obj, Question):
                article = obj.article
            else:
                article = obj
        else:
            return False
            
        user = self.request.user
        return (
            user.is_superuser
            or user.has_perm('wiki.manage_all_articles')
            or (user.has_perm('wiki.change_article') and article.author == user)
        )

    def handle_no_permission(self):
        messages.error(self.request, 'Bạn không có quyền quản lý nội dung này.')
        return redirect('wiki:article-list')


class ArticleQuizManageView(LoginRequiredMixin, QuizPermissionMixin, ListView):
    model = Question
    template_name = 'wiki/quiz_manage.html'
    context_object_name = 'questions'

    def get_queryset(self):
        self.article = get_object_or_404(Article, pk=self.kwargs['article_pk'])
        return Question.objects.filter(article=self.article).prefetch_related('choices')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['article'] = self.article
        return context


class QuestionCreateView(LoginRequiredMixin, QuizPermissionMixin, CreateView):
    model = Question
    form_class = QuestionForm
    template_name = 'wiki/question_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.article = get_object_or_404(Article, pk=self.kwargs['article_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['choice_formset'] = ChoiceFormSet(self.request.POST)
        else:
            context['choice_formset'] = ChoiceFormSet()
        context['article'] = self.article
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        choice_formset = context['choice_formset']
        if form.is_valid() and choice_formset.is_valid():
            form.instance.article = self.article
            self.object = form.save()
            choice_formset.instance = self.object
            choice_formset.save()
            messages.success(self.request, 'Đã thêm câu hỏi.')
            return redirect('wiki:article-quiz-manage', article_pk=self.article.pk)
        return self.render_to_response(self.get_context_data(form=form))


class QuestionUpdateView(LoginRequiredMixin, QuizPermissionMixin, UpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'wiki/question_form.html'
    pk_url_kwarg = 'pk'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['choice_formset'] = ChoiceFormSet(self.request.POST, instance=self.object)
        else:
            context['choice_formset'] = ChoiceFormSet(instance=self.object)
        context['article'] = self.object.article
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        choice_formset = context['choice_formset']
        if form.is_valid() and choice_formset.is_valid():
            self.object = form.save()
            choice_formset.instance = self.object
            choice_formset.save()
            messages.success(self.request, 'Đã cập nhật câu hỏi.')
            return redirect('wiki:article-quiz-manage', article_pk=self.object.article.pk)
        return self.render_to_response(self.get_context_data(form=form))


class QuestionDeleteView(LoginRequiredMixin, QuizPermissionMixin, DeleteView):
    model = Question
    template_name = 'wiki/question_confirm_delete.html'
    pk_url_kwarg = 'pk'

    def get_success_url(self):
        messages.success(self.request, 'Đã xóa câu hỏi.')
        return reverse_lazy('wiki:article-quiz-manage', kwargs={'article_pk': self.object.article.pk})


class SubmitQuizView(View):
    def post(self, request, article_pk):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'message': 'Vui lòng đăng nhập để nộp bài.'}, status=401)
        
        try:
            data = json.loads(request.body)
            answers = data.get('answers', {})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Dữ liệu không hợp lệ.'}, status=400)

        article = get_object_or_404(Article, pk=article_pk)
        questions = article.questions.prefetch_related('choices')
        
        results = {}
        correct_count = 0
        total_questions = questions.count()

        for q in questions:
            choice_id = answers.get(str(q.pk))
            correct_choice = q.choices.filter(is_correct=True).first()

            is_correct = False
            selected_choice = None
            if choice_id:
                selected_choice = q.choices.filter(pk=choice_id).first()
                if selected_choice and selected_choice.is_correct:
                    is_correct = True
                    correct_count += 1
                
                if selected_choice:
                    UserAnswer.objects.update_or_create(
                        user=request.user,
                        question=q,
                        defaults={'selected_choice': selected_choice}
                    )

            results[q.pk] = {
                'is_correct': is_correct,
                'correct_choice_id': correct_choice.pk if correct_choice else None,
                'explanation': q.explanation
            }

        return JsonResponse({
            'success': True,
            'correct_count': correct_count,
            'total_questions': total_questions,
            'results': results
        })

@login_required
def export_article_pdf(request, pk):
    article = get_object_or_404(Article, pk=pk)
    html_content = render_to_string('wiki/article_pdf.html', {'article': article, 'request': request})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{article.slug}.pdf"'
    pisa_status = pisa.CreatePDF(html_content, dest=response)
    if pisa_status.err:
        return HttpResponse('Lỗi khi xuất PDF', status=500)
    return response

@login_required
def upload_quiz_file(request, article_pk):
    article = get_object_or_404(Article, pk=article_pk)
    if request.method == 'POST':
        file = request.FILES.get('quiz_file')
        if not file:
            messages.error(request, "Vui lòng chọn file.")
            return redirect('wiki:article-quiz-manage', article_pk=article.pk)
        text = ""
        try:
            if file.name.endswith('.docx'):
                doc = docx.Document(file)
                text = "\n".join([para.text for para in doc.paragraphs])
            elif file.name.endswith('.pdf'):
                reader = PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            else:
                text = file.read().decode('utf-8', errors='ignore')
        except Exception as e:
            messages.error(request, f"Lỗi đọc file: {str(e)}")
            return redirect('wiki:article-quiz-manage', article_pk=article.pk)

        lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 10]
        count = 0
        for line in lines:
            q = Question.objects.create(article=article, content=line)
            Choice.objects.create(question=q, content="Lựa chọn 1", is_correct=True)
            Choice.objects.create(question=q, content="Lựa chọn 2", is_correct=False)
            count += 1
        messages.success(request, f"Đã trích xuất {count} câu hỏi. Hãy chỉnh sửa để hoàn thiện.")
        return redirect('wiki:article-quiz-manage', article_pk=article.pk)
    return render(request, 'wiki/quiz_upload.html', {'article': article})
