"""
Context processors for the wiki application.
"""

from .models import Notification


def notifications_count(request):
    """Return the count of unread notifications for the current user."""
    if request.user.is_authenticated:
        return {
            'unread_notifications_count': Notification.objects.filter(recipient=request.user, is_read=False).count(),
            'latest_notifications': Notification.objects.filter(recipient=request.user).order_by('-created_at')[:5]
        }
    return {
        'unread_notifications_count': 0,
        'latest_notifications': []
    }
