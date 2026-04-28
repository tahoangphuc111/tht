from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from ..models import CodingSubmission

class SubmissionHistoryView(LoginRequiredMixin, ListView):
    model = CodingSubmission
    template_name = "wiki/coding/submissions_history.html"
    context_object_name = "submissions"
    paginate_by = 20
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = CodingSubmission.objects.all()
        else:
            qs = CodingSubmission.objects.filter(user=self.request.user)
            
        qs = qs.select_related('exercise__article', 'user').order_by('-created_at')
        
        exercise_id = self.request.GET.get('exercise')
        if exercise_id:
            qs = qs.filter(exercise_id=exercise_id)
        return qs

class SubmissionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = CodingSubmission
    template_name = "wiki/coding/submission_detail.html"
    context_object_name = "submission"

    def test_func(self):
        submission = self.get_object()
        return self.request.user.is_superuser or submission.user == self.request.user

