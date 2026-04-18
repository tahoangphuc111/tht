"""
Views for handling file uploads.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import UploadedFile
from ..forms import UploadFileForm


@login_required
def upload_file_view(request):
    """View to handle file uploads by the user."""
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.save(commit=False)
            uploaded_file.user = request.user
            uploaded_file.save()
            messages.success(request, "Upload thành công.")
            return redirect("wiki:upload-files")
    else:
        form = UploadFileForm()

    uploads = UploadedFile.objects.filter(user=request.user).order_by("-created_at")

    return render(request, "wiki/upload_files.html", {"form": form, "uploads": uploads})
