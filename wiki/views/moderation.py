"""
Views for handling moderation tasks like reporting content.
"""

import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from ..models import Article, Comment, Report


@login_required
@require_POST
def report_content_view(request):
    """Handle reporting of articles or comments."""
    try:
        data = json.loads(request.body)
        reason = data.get("reason")
        description = data.get("description", "")
        article_id = data.get("article_id")
        comment_id = data.get("comment_id")

        if not reason:
            return JsonResponse({"success": False, "message": "Vui lòng chọn lý do báo cáo."}, status=400)

        report = Report(
            reporter=request.user,
            reason=reason,
            description=description
        )

        if article_id:
            report.article = get_object_or_404(Article, pk=article_id)
        elif comment_id:
            report.comment = get_object_or_404(Comment, pk=comment_id)
        else:
            return JsonResponse({"success": False, "message": "Thiếu thông tin đối tượng báo cáo."}, status=400)

        report.save()
        return JsonResponse({"success": True, "message": "Cảm ơn bạn! Báo cáo đã được gửi tới quản trị viên."})
    except Exception as error:  # pylint: disable=broad-exception-caught
        return JsonResponse({"success": False, "message": str(error)}, status=400)
