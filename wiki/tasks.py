import logging

from celery import shared_task

from .models import CodingSubmission
from .services import code_runner

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1)
def execute_code_task(self, submission_id):
    try:
        submission = CodingSubmission.objects.get(pk=submission_id)
        # bỏ qua nếu không phải trạng thái running (tức là đã xử lý)
        if submission.status != "running":
            return

        # gọi hàm execute_code trong code_runner.py
        # chúng ta sẽ refactor lại execute_code để nhận tham số hợp lý hơn
        # vì nó đã lưu trong database rồi, ta có thể chạy lại
        code_runner._execute_submission(submission)

    except CodingSubmission.DoesNotExist:
        logger.error("Submission %s not found.", submission_id)
    except Exception as e:
        logger.error("Error executing submission %s: %s", submission_id, e)
        try:
            sub = CodingSubmission.objects.get(pk=submission_id)
            sub.status = "internal_error"
            sub.compile_output = str(e)
            sub.save(update_fields=["status", "compile_output"])
        except Exception:
            pass
