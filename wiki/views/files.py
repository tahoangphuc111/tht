from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import UploadedFile
from ..forms import UploadFileForm

@login_required
def upload_file_view(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            u = form.save(commit=False)
            u.user = request.user
            u.save()
            messages.success(request, 'Upload thành công.')
            return redirect('wiki:upload-files')
    return render(request, 'wiki/upload_files.html', {
        'form': UploadFileForm(),
        'uploads': UploadedFile.objects.filter(user=request.user).order_by('-created_at')
    })
