import logging
from celery import shared_task
from .models import CodingSubmission
from .services import code_runner

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=1)
def execute_code_task(self, submission_id):
    try:
        submission = CodingSubmission.objects.get(pk=submission_id)
        # Bỏ qua nếu không phải trạng thái running (đã xử lý)
        if submission.status != "running":
            return
            
        # Gọi hàm execute_code trong code_runner.py
        # Chúng ta sẽ refactor lại execute_code để nhận tham số hợp lý hơn 
        # Vì nó đã lưu trong DB rồi, ta có thể chạy lại
        code_runner._execute_submission(submission)
        
    except CodingSubmission.DoesNotExist:
        logger.error(f"Submission {submission_id} not found.")
    except Exception as e:
        logger.error(f"Error executing submission {submission_id}: {e}")
        try:
            sub = CodingSubmission.objects.get(pk=submission_id)
            sub.status = "internal_error"
            sub.compile_output = str(e)
            sub.save(update_fields=["status", "compile_output"])
        except Exception:
            pass
