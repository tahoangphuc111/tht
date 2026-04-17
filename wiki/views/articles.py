from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
import random

from ..models import Article, Category, Comment, ArticleRevision, UploadedFile
from ..forms import ArticleForm, CommentForm
from ..utils import save_article_revision, can_publish_articles

class ArticleListView(ListView):
    model = Article
    template_name = 'wiki/article_list.html'
    context_object_name = 'articles'
    paginate_by = 10
    def get_queryset(self):
        qs = Article.objects.select_related('author', 'category').annotate(
            comment_count=Count('comments', distinct=True),
            vote_balance=Count('article_votes', filter=Q(article_votes__value=1), distinct=True) - Count('article_votes', filter=Q(article_votes__value=-1), distinct=True),
        )
        q, auth, cat, sort = self.request.GET.get('q', ''), self.request.GET.get('author', ''), self.request.GET.get('category', ''), self.request.GET.get('sort', 'newest')
        if q: qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
        if auth: qs = qs.filter(author__username__icontains=auth)
        if cat: qs = qs.filter(category__slug=cat)
        if sort == 'updated': qs = qs.order_by('-updated_at', '-created_at')
        elif sort == 'commented': qs = qs.order_by('-comment_count', '-created_at')
        elif sort == 'top': qs = qs.order_by('-vote_balance', '-comment_count', '-updated_at')
        else: qs = qs.order_by('-created_at')
        return qs
    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c.update({'query': self.request.GET.get('q', ''), 'categories': Category.objects.all(), 'can_publish': can_publish_articles(self.request.user)})
        return c

class ArticleDetailView(DetailView):
    model = Article
    template_name = 'wiki/article_detail.html'
    context_object_name = 'article'
    query_pk_and_slug = True
    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        a, u = self.object, self.request.user
        can_manage = u.is_authenticated and (u.is_superuser or u.has_perm('wiki.manage_all_articles'))
        c.update({
            'comments': a.comments.select_related('author').filter(is_approved=True),
            'related_articles': Article.objects.filter(category=a.category).exclude(pk=a.pk)[:3],
            'comment_form': CommentForm(),
            'can_comment': a.allow_comments and u.is_authenticated and u.has_perm('wiki.add_comment'),
            'can_edit_article': can_manage or (u.is_authenticated and a.author == u and u.has_perm('wiki.change_article')),
            'can_delete_article': can_manage or (u.is_authenticated and a.author == u and u.has_perm('wiki.delete_article')),
            'captcha_question': f'{random.randint(1,8)} + {random.randint(1,8)} = ?',
            'article_vote_score': a.vote_score,
        })
        return c
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.allow_comments or not request.user.is_authenticated: return redirect(self.object.get_absolute_url())
        f = CommentForm(request.POST)
        if f.is_valid():
            comment = f.save(commit=False)
            comment.article, comment.author = self.object, request.user
            comment.save()
            return redirect(self.object.get_absolute_url())
        return self.render_to_response(self.get_context_data(comment_form=f))

class ArticleCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = 'wiki/article_form.html'
    def test_func(self): return can_publish_articles(self.request.user)
    def handle_no_permission(self):
        if self.request.user.is_authenticated: return redirect('wiki:article-list')
        return super().handle_no_permission()
    def form_valid(self, form):
        form.instance.author = self.request.user
        r = super().form_valid(form)
        save_article_revision(self.object, self.request.user, form.cleaned_data.get('change_summary', 'Initial'))
        return r

class ArticleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'wiki/article_form.html'
    def get_object(self, queryset=None): return get_object_or_404(Article, pk=self.kwargs.get('pk'))
    def test_func(self):
        a = self.get_object()
        u = self.request.user
        return u.is_superuser or u.has_perm('wiki.manage_all_articles') or (a.author == u and u.has_perm('wiki.change_article'))
    def handle_no_permission(self): return redirect('wiki:article-list')
    def form_valid(self, form):
        r = super().form_valid(form)
        save_article_revision(self.object, self.request.user, form.cleaned_data.get('change_summary', ''))
        return r

class ArticleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Article
    template_name = 'wiki/article_confirm_delete.html'
    success_url = reverse_lazy('wiki:article-list')
    def get_object(self, queryset=None): return get_object_or_404(Article, pk=self.kwargs.get('pk'))
    def test_func(self):
        a = self.get_object()
        u = self.request.user
        return u.is_superuser or u.has_perm('wiki.manage_all_articles') or (a.author == u and u.has_perm('wiki.delete_article'))
    def handle_no_permission(self): return redirect('wiki:article-list')

class ArticleHistoryView(DetailView):
    model = Article
    template_name = 'wiki/article_history.html'
    context_object_name = 'article'
    def get_object(self, queryset=None): return get_object_or_404(Article, pk=self.kwargs.get('pk'))
    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c['revisions'] = self.object.revisions.select_related('author').all()
        return c

class ArticleRevisionDetailView(DetailView):
    model = ArticleRevision
    template_name = 'wiki/article_revision_detail.html'
    context_object_name = 'revision'
    def get_object(self, queryset=None): return get_object_or_404(ArticleRevision, pk=self.kwargs.get('pk'))

from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa

@login_required
def export_article_pdf(request, pk):
    article = get_object_or_404(Article, pk=pk)
    html = render_to_string('wiki/article_pdf.html', {'article': article, 'request': request})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{article.slug}.pdf"'
    if pisa.CreatePDF(html, dest=response).err: return HttpResponse('Lỗi PDF', status=500)
    return response
