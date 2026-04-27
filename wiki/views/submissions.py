from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import CodingSubmission

class SubmissionHistoryView(LoginRequiredMixin, ListView):
    model = CodingSubmission
    template_name = "wiki/coding/submissions_history.html"
    context_object_name = "submissions"
    paginate_by = 20
    
    def get_queryset(self):
        qs = CodingSubmission.objects.filter(user=self.request.user).select_related('exercise__article')
        exercise_id = self.request.GET.get('exercise')
        if exercise_id:
            qs = qs.filter(exercise_id=exercise_id)
        return qs
