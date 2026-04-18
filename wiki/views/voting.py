"""
Views for handling voting in the wiki app.
"""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.contrib.auth import get_user_model
from config.asgi import broadcast_vote_update
from ..models import Article, Comment, ArticleVote, CommentVote, UserVote

User = get_user_model()


def _handle_vote(request, model, target_field, target_obj, vote_attr):
    """General helper function to handle voting logic for any model."""
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'message': 'Bạn cần đăng nhập.'},
                status=401
            )
        return redirect(f'{settings.LOGIN_URL}?next={request.path}')

    try:
        val = int(request.POST.get('vote', 0))
        if val not in (1, -1):
            raise ValueError
    except ValueError:
        if hasattr(target_obj, 'get_absolute_url'):
            return redirect(target_obj.get_absolute_url())
        return redirect('wiki:home')

    model.objects.update_or_create(
        **{
            'user' if target_field != 'target' else 'voter': request.user,
            target_field: target_obj
        },
        defaults={'value': val}
    )

    target_obj.refresh_from_db()

    if hasattr(target_obj, 'profile'):
        score = target_obj.profile.vote_score
        upvotes = target_obj.profile.upvotes
        downvotes = target_obj.profile.downvotes
    else:
        score = target_obj.vote_score
        upvotes = target_obj.upvotes
        downvotes = target_obj.downvotes

    payload = {
        f'{vote_attr}_score': score,
        f'{vote_attr}_upvotes': upvotes,
        f'{vote_attr}_downvotes': downvotes,
        f'{vote_attr}_pk': target_obj.pk
    }

    try:
        broadcast_vote_update(payload)
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Cập nhật thành công.',
            **payload
        })

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)

    if hasattr(target_obj, 'get_absolute_url'):
        return redirect(target_obj.get_absolute_url())
    return redirect('wiki:home')


def vote_article(request, pk):
    """Handle voting for an article."""
    return _handle_vote(
        request, ArticleVote, 'article',
        get_object_or_404(Article, pk=pk), 'article'
    )


def vote_comment(request, pk):
    """Handle voting for a comment."""
    return _handle_vote(
        request, CommentVote, 'comment',
        get_object_or_404(Comment, pk=pk), 'comment'
    )


def vote_user(request, username):
    """Handle voting for a user (reputation)."""
    try:
        target = User.objects.get(pk=int(username))
    except (ValueError, User.DoesNotExist):
        target = get_object_or_404(User, username=username)

    if target == request.user:
        return JsonResponse(
            {'success': False, 'message': 'Không thể vote chính mình.'},
            status=400
        )
    return _handle_vote(request, UserVote, 'target', target, 'target_user')
