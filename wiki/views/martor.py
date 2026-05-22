"""
Local upload endpoint for Martor editor images.
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.utils import timezone


def _upload_error(message, status=400):
    return JsonResponse({"status": status, "error": message})


@login_required
def markdown_upload_view(request):
    """Store Martor editor uploads locally and return the shape Martor expects."""
    if request.method != "POST":
        return _upload_error("Invalid request method.", 405)

    upload = request.FILES.get("markdown-image-upload")
    if not upload:
        return _upload_error("No file was uploaded.")

    max_size = getattr(settings, "MARTOR_UPLOAD_MAX_SIZE", 15 * 1024 * 1024)
    if upload.size > max_size:
        return _upload_error("File qua lon. Vui long upload toi da 15MB.")

    allowed_types = set(getattr(settings, "MARTOR_ALLOWED_UPLOADS", []))
    if allowed_types and upload.content_type not in allowed_types:
        return _upload_error("Chi ho tro upload file pdf, docx, png, jpg.")

    allowed_extensions = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}
    if Path(upload.name).suffix.lower() not in allowed_extensions:
        return _upload_error("Chi ho tro upload file pdf, docx, png, jpg.")

    today = timezone.localdate()
    saved_path = default_storage.save(
        f"martor/{today:%Y/%m/%d}/{Path(upload.name).name}",
        upload,
    )

    return JsonResponse(
        {
            "status": 200,
            "name": Path(upload.name).name,
            "link": request.build_absolute_uri(default_storage.url(saved_path)),
        }
    )
