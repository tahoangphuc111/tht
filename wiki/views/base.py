from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.db.models import Count, Q

from django.contrib.auth.models import Group
from ..models import Article, Category, Comment
from ..forms import SignUpForm
from ..utils import can_publish_articles

def home_view(request):
    featured = Article.objects.select_related('author', 'category').annotate(comment_count=Count('comments')).order_by('-updated_at').first()
    context = {
        'featured_article': featured,
        'latest_articles': Article.objects.select_related('author', 'category').order_by('-created_at')[:4],
        'recent_comments': Comment.objects.select_related('author', 'article').filter(is_approved=True).order_by('-created_at')[:5],
        'top_categories': Category.objects.annotate(article_total=Count('articles')).order_by('-article_total')[:6],
        'total_articles': Article.objects.count(),
        'total_comments': Comment.objects.filter(is_approved=True).count(),
        'can_publish': can_publish_articles(request.user),
    }
    return render(request, 'wiki/home.html', context)

def signup_view(request):
    if request.user.is_authenticated: return redirect('wiki:home')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            group = Group.objects.filter(name='user').first()
            if group: user.groups.add(group)
            login(request, user)
            messages.success(request, 'Tạo tài khoản thành công!')
            return redirect('wiki:getting-started')
    return render(request, 'wiki/signup.html', {'form': SignUpForm()})

def getting_started_view(request):
    return render(request, 'wiki/getting_started.html')

@login_required
def dismiss_guide_view(request):
    profile = request.user.profile
    profile.guide_seen = True
    profile.save(update_fields=['guide_seen'])
    return HttpResponseRedirect(request.POST.get('next') or reverse_lazy('wiki:article-list'))
