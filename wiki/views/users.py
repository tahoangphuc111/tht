from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render, redirect
from django.views.generic import ListView

from ..forms import UserUpdateForm, ProfileForm
from ..utils import build_profile_stats

@login_required
def profile_view(request):
    return render(request, 'wiki/profile.html', build_profile_stats(request.user, viewer=request.user))

def public_profile_view(request, username):
    try:
        u = User.objects.get(pk=int(username))
    except (ValueError, User.DoesNotExist):
        u = get_object_or_404(User, username=username)
    return render(request, 'wiki/profile.html', build_profile_stats(u, viewer=request.user))

@login_required
def profile_edit_view(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save(); p_form.save()
            messages.success(request, 'Đã cập nhật profile.')
            return redirect('wiki:profile')
    return render(request, 'wiki/profile_edit.html', {
        'user_form': UserUpdateForm(instance=request.user),
        'profile_form': ProfileForm(instance=request.user.profile)
    })

class UserListView(ListView):
    model = User
    template_name = 'wiki/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        q = self.request.GET.get('q', '').strip()
        qs = User.objects.select_related('profile').annotate(
            article_count=Count('articles', distinct=True),
            vote_score=Count('user_votes', filter=Q(user_votes__value=1)) - Count('user_votes', filter=Q(user_votes__value=-1))
        ).order_by('-vote_score')
        if q: qs = qs.filter(Q(username__icontains=q) | Q(profile__display_name__icontains=q))
        return qs
