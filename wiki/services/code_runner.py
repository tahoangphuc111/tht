import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ..models import CodingSubmission, CodingSubmissionResult, LanguageRuntime

RUNNER_LOCK = threading.BoundedSemaphore(
    value=max(1, getattr(settings, "CODE_EXECUTION_MAX_CONCURRENT_JOBS", 2))
)


class CodeRunnerError(Exception):
    pass


def _merged_configs():
    base = dict(getattr(settings, "CODE_EXECUTION_LANGUAGE_CONFIGS", {}))
    try:
        for rt in LanguageRuntime.objects.filter(enabled=True):
            base[rt.key] = rt.to_config()
    except Exception:
        pass
    return base


def get_language_config(language):
    return _merged_configs().get(language, {})


def get_enabled_language_choices():
    return [
        {
            "key": key,
            "label": cfg.get("label", key),
            "monaco_language": cfg.get("monaco_language", "plaintext"),
        }
        for key, cfg in _merged_configs().items()
        if cfg.get("enabled")
    ]


def _load_binary_map():
    json_path = settings.BASE_DIR / "config" / "languages.json"
    if not json_path.exists():
        return {}
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return {k: v.get("binaries", []) for k, v in raw.items()}
    except Exception:
        return {}


def get_all_language_status():
    configs = _merged_configs()
    binmap = _load_binary_map()
    results = []
    for key, cfg in configs.items():
        bins = binmap.get(key, [])
        found = None
        for b in bins:
            found = shutil.which(b)
            if found:
                break
        results.append({
            "key": key,
            "label": cfg.get("label", key),
            "monaco_language": cfg.get("monaco_language", "plaintext"),
            "enabled": bool(cfg.get("enabled")),
            "detected": bool(found),
            "binary_path": found,
            "source": "db" if key not in getattr(settings, "CODE_EXECUTION_LANGUAGE_CONFIGS", {}) else "json",
        })
    return results


def compare_output(expected_output, actual_output, compare_mode):
    expected_output = expected_output or ""
    actual_output = actual_output or ""
    if compare_mode == "exact":
        return expected_output == actual_output
    if compare_mode == "trim_lines":
        expected_lines = [line.strip() for line in expected_output.strip().splitlines()]
        actual_lines = [line.strip() for line in actual_output.strip().splitlines()]
        return expected_lines == actual_lines

    expected_tokens = expected_output.split()
    actual_tokens = actual_output.split()
    return expected_tokens == actual_tokens


def _run_custom_checker(job_dir, exercise, input_data, expected_output, actual_output):
    actual_path = job_dir / "actual_out.txt"
    actual_path.write_text(actual_output or "", encoding="utf-8")
    expected_path = job_dir / "expected_out.txt"
    expected_path.write_text(expected_output or "", encoding="utf-8")
    
    checker_lang = exercise.checker_language or "python"
    checker_ext = "py" if checker_lang == "python" else "cpp"
    checker_path = job_dir / f"checker.{checker_ext}"
    checker_path.write_text(exercise.checker_code or "", encoding="utf-8")
    
    if checker_lang == "python":
        command = ["python", "checker.py", "stdin.txt", "actual_out.txt", "expected_out.txt"]
        # Use python:3.10-slim docker image implicitly via _run_process
        process_result = _run_process(command, job_dir, input_data=input_data, timeout_ms=5000)
        completed = process_result["completed"]
        if completed and completed.returncode == 0:
            return "accepted"
        return "wrong_answer"
    return "internal_error"


def _truncate_text(value):
    if not value:
        return ""
    max_bytes = getattr(settings, "CODE_EXECUTION_MAX_OUTPUT_BYTES", 512 * 1024)
    encoded = value.encode("utf-8", errors="ignore")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _ensure_language_is_available(exercise, language):
    allowed_languages = exercise.allowed_languages or []
    if language not in allowed_languages:
        raise CodeRunnerError("Ngôn ngữ này không được bật cho bài tập.")

    language_config = get_language_config(language)
    if not language_config or not language_config.get("enabled"):
        raise CodeRunnerError("Ngôn ngữ này chưa được cấu hình trên máy chủ.")
    return language_config


def _render_command(command, replacements):
    rendered = []
    for part in command:
        if not part:
            raise CodeRunnerError("Thiếu đường dẫn compiler/runtime trong cấu hình.")
        rendered.append(str(part).format(**replacements))
    return rendered


def _create_job_directory():
    root = Path(getattr(settings, "CODE_EXECUTION_TMP_ROOT"))
    root.mkdir(parents=True, exist_ok=True)
    job_dir = root / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def _prepare_csharp_project(job_dir):
    project_path = job_dir / "Runner.csproj"
    project_path.write_text(
        (
            "<Project Sdk=\"Microsoft.NET.Sdk\">"
            "<PropertyGroup>"
            "<OutputType>Exe</OutputType>"
            "<TargetFramework>net8.0</TargetFramework>"
            "<ImplicitUsings>enable</ImplicitUsings>"
            "<Nullable>enable</Nullable>"
            "</PropertyGroup>"
            "</Project>"
        ),
        encoding="utf-8",
    )
    return project_path


def _write_source(job_dir, language, source_code, language_config):
    max_source_bytes = getattr(settings, "CODE_EXECUTION_MAX_SOURCE_BYTES", 128 * 1024)
    if len(source_code.encode("utf-8")) > max_source_bytes:
        raise CodeRunnerError("Source code vượt quá giới hạn cho phép.")

    source_path = job_dir / language_config.get("source_name", f"main.{language}")
    source_path.write_text(source_code, encoding="utf-8")
    project_path = None
    dll_path = None
    build_dir = job_dir / "build"
    if language == "csharp":
        project_path = _prepare_csharp_project(job_dir)
        dll_path = build_dir / "Runner.dll"
    executable_path = job_dir / ("main.exe" if language != "java" else "Main.class")
    return {
        "source_path": source_path,
        "source_name": source_path.name,
        "workdir": job_dir,
        "executable_path": executable_path,
        "project_path": project_path or "",
        "build_dir": build_dir,
        "dll_path": dll_path or "",
    }


def _run_process(command, workdir, input_data="", timeout_ms=None):
    timeout_seconds = (timeout_ms or getattr(settings, "CODE_EXECUTION_DEFAULT_TIME_LIMIT_MS", 2000)) / 1000
    stdin_path = workdir / "stdin.txt"
    stdout_path = workdir / "stdout.txt"
    stderr_path = workdir / "stderr.txt"
    stdin_path.write_text(input_data or "", encoding="utf-8")
    run_env = os.environ.copy()
    run_env["PYTHONIOENCODING"] = "utf-8"
    run_env["PYTHONUTF8"] = "1"
    run_env["LANG"] = "en_US.UTF-8"
    run_env["LC_ALL"] = "en_US.UTF-8"

    started_at = time.perf_counter()
    with open(stdin_path, "rb") as stdin_handle, \
         open(stdout_path, "wb") as stdout_handle, \
         open(stderr_path, "wb") as stderr_handle:
        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                stdin=stdin_handle,
                stdout=stdout_handle,
                stderr=stderr_handle,
                timeout=timeout_seconds,
                check=False,
                shell=False,
                env=run_env,
            )
            timed_out = False
        except subprocess.TimeoutExpired:
            completed = None
            timed_out = True
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)

    stdout_value = stdout_path.read_text(encoding="utf-8", errors="ignore") if stdout_path.exists() else ""
    stderr_value = stderr_path.read_text(encoding="utf-8", errors="ignore") if stderr_path.exists() else ""
    return {
        "completed": completed,
        "timed_out": timed_out,
        "elapsed_ms": elapsed_ms,
        "stdout": _truncate_text(stdout_value),
        "stderr": _truncate_text(stderr_value),
    }


def _compile_source(job_dir, language, language_config, replacements):
    compile_command = language_config.get("compile") or []
    if not compile_command:
        return {"ok": True, "stdout": "", "stderr": ""}

    process_result = _run_process(
        _render_command(compile_command, replacements),
        job_dir,
        input_data="",
        timeout_ms=max(
            1000, getattr(settings, "CODE_EXECUTION_DEFAULT_TIME_LIMIT_MS", 2000)
        ),
    )
    if process_result["timed_out"]:
        return {"ok": False, "status": "compile_error", "stdout": "", "stderr": "Compile timeout."}

    completed = process_result["completed"]
    if completed is None or completed.returncode != 0:
        return {
            "ok": False,
            "status": "compile_error",
            "stdout": process_result["stdout"],
            "stderr": process_result["stderr"],
        }
    return {
        "ok": True,
        "stdout": process_result["stdout"],
        "stderr": process_result["stderr"],
    }


def _run_testcase(job_dir, language_config, replacements, input_data, expected_output, compare_mode, case_name, exercise=None):
    process_result = _run_process(
        _render_command(language_config.get("run") or [], replacements),
        job_dir,
        input_data=input_data,
        timeout_ms=replacements["time_limit_ms"],
    )
    if process_result["timed_out"]:
        return {
            "case_name": case_name,
            "status": "time_limit_exceeded",
            "runtime_ms": process_result["elapsed_ms"],
            "stdout_preview": process_result["stdout"],
            "stderr_preview": process_result["stderr"],
            "expected_preview": _truncate_text(expected_output),
            "actual_preview": process_result["stdout"],
        }

    completed = process_result["completed"]
    if completed is None:
        status = "internal_error"
    elif completed.returncode != 0:
        status = "runtime_error"
    elif expected_output is None and compare_mode != "custom_checker":
        status = "accepted"
    else:
        if compare_mode == "custom_checker" and exercise and exercise.checker_code:
            status = _run_custom_checker(job_dir, exercise, input_data, expected_output, process_result["stdout"])
        else:
            status = (
                "accepted"
                if compare_output(expected_output, process_result["stdout"], compare_mode)
                else "wrong_answer"
            )

    return {
        "case_name": case_name,
        "status": status,
        "runtime_ms": process_result["elapsed_ms"],
        "stdout_preview": process_result["stdout"],
        "stderr_preview": process_result["stderr"],
        "expected_preview": _truncate_text(expected_output) if expected_output is not None else "",
        "actual_preview": process_result["stdout"],
    }


def execute_code(exercise, user, language, source_code, *, custom_input="", sample_only=False):
    language_config = _ensure_language_is_available(exercise, language)
    max_input_bytes = getattr(settings, "CODE_EXECUTION_MAX_SOURCE_BYTES", 128 * 1024)
    if custom_input and len(custom_input.encode("utf-8")) > max_input_bytes:
        raise CodeRunnerError("Input tùy chỉnh vượt quá giới hạn cho phép.")

    submission = CodingSubmission.objects.create(
        exercise=exercise,
        user=user,
        language=language,
        source_code=source_code,
        status="running",
        custom_input=custom_input,
        is_sample_run=sample_only,
    )
    
    # Import ở đây để tránh circular import
    from ..tasks import execute_code_task
    execute_code_task.delay(submission.pk)
    
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        submission.refresh_from_db()

    return submission

def _execute_submission(submission):
    exercise = submission.exercise
    language = submission.language
    source_code = submission.source_code
    custom_input = submission.custom_input
    sample_only = submission.is_sample_run
    
    language_config = get_language_config(language)

    if not RUNNER_LOCK.acquire(timeout=1):
        submission.status = "internal_error"
        submission.compile_output = "Máy chấm đang quá tải, vui lòng thử lại sau."
        submission.save(update_fields=["status", "compile_output"])
        return

    job_dir = None
    try:
        job_dir = _create_job_directory()
        replacements = _write_source(job_dir, language, source_code, language_config)
        replacements["time_limit_ms"] = exercise.time_limit_ms

        compile_result = _compile_source(job_dir, language, language_config, replacements)
        if not compile_result["ok"]:
            submission.status = "compile_error"
            submission.compile_output = compile_result["stderr"] or compile_result["stdout"]
            submission.stderr_preview = compile_result["stderr"]
            submission.finished_at = timezone.now()
            submission.save(
                update_fields=[
                    "status",
                    "compile_output",
                    "stderr_preview",
                    "finished_at",
                ]
            )
            return submission

        testcase_results = []
        total_tests = 1
        subtask_scores = {}
        subtask_max_scores = {}
        
        if custom_input:
            testcase_results.append(
                _run_testcase(
                    job_dir,
                    language_config,
                    replacements,
                    custom_input,
                    None,
                    exercise.compare_mode,
                    "custom input",
                    exercise=exercise,
                )
            )
        else:
            queryset = list(exercise.testcases.all()[: getattr(settings, "CODE_EXECUTION_MAX_TESTCASES", 30)])
            if sample_only:
                queryset = [tc for tc in queryset if tc.is_sample]
            total_tests = len(queryset)
            
            # Tính điểm tối đa từng subtask
            for tc in queryset:
                sid = str(tc.subtask_id)
                if sid not in subtask_max_scores:
                    subtask_max_scores[sid] = tc.score
                else:
                    subtask_max_scores[sid] = max(subtask_max_scores[sid], tc.score)
                if sid not in subtask_scores:
                    subtask_scores[sid] = subtask_max_scores[sid] # Assume max initially

            for testcase in queryset:
                res = _run_testcase(
                    job_dir,
                    language_config,
                    replacements,
                    testcase.get_input_data(),
                    testcase.get_expected_output_data(),
                    exercise.compare_mode,
                    testcase.name,
                    exercise=exercise,
                )
                res["subtask_id"] = str(testcase.subtask_id)
                testcase_results.append(res)
                if res["status"] != "accepted":
                    subtask_scores[str(testcase.subtask_id)] = 0
                    if not sample_only:
                        pass

        passed_tests = sum(1 for item in testcase_results if item["status"] == "accepted")
        
        total_score = 0
        if not custom_input and not sample_only:
            total_score = sum(subtask_scores.values())
            
        final_status = "accepted"
        if not custom_input and passed_tests < total_tests:
            final_status = "wrong_answer"
        for item in testcase_results:
            if item["status"] != "accepted":
                final_status = item["status"]
                break

        submission.status = final_status
        submission.compile_output = compile_result["stderr"] or compile_result["stdout"]
        preview_item = next(
            (item for item in testcase_results if item["status"] != "accepted"),
            testcase_results[0] if testcase_results else None,
        )
        submission.stdout_preview = preview_item["stdout_preview"] if preview_item else ""
        submission.stderr_preview = preview_item["stderr_preview"] if preview_item else ""
        submission.total_tests = total_tests
        submission.passed_tests = passed_tests
        submission.score = total_score
        submission.subtask_results = subtask_scores
        submission.runtime_ms = max(
            [item["runtime_ms"] for item in testcase_results],
            default=0,
        )
        submission.finished_at = timezone.now()
        submission.save(
            update_fields=[
                "status",
                "compile_output",
                "stdout_preview",
                "stderr_preview",
                "total_tests",
                "passed_tests",
                "score",
                "subtask_results",
                "runtime_ms",
                "finished_at",
            ]
        )

        testcase_lookup = {
            testcase.name: testcase
            for testcase in exercise.testcases.all()[: getattr(settings, "CODE_EXECUTION_MAX_TESTCASES", 30)]
        }
        for item in testcase_results:
            CodingSubmissionResult.objects.create(
                submission=submission,
                test_case=testcase_lookup.get(item["case_name"]),
                case_name=item["case_name"],
                status=item["status"],
                runtime_ms=item["runtime_ms"],
                stdout_preview=item["stdout_preview"],
                stderr_preview=item["stderr_preview"],
                expected_preview=item["expected_preview"],
                actual_preview=item["actual_preview"],
            )
        return submission
    except Exception as error:
        submission.status = "internal_error"
        submission.compile_output = (
            str(error)
            if isinstance(error, CodeRunnerError)
            else "Lỗi hệ thống trong quá trình chấm."
        )
        submission.finished_at = timezone.now()
        submission.save(
            update_fields=["status", "compile_output", "finished_at"]
        )
        raise
    finally:
        if job_dir and job_dir.exists():
            for path in sorted(job_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink(missing_ok=True)
                else:
                    path.rmdir()
            job_dir.rmdir()
        RUNNER_LOCK.release()


def serialize_submission(submission):
    status_map = {
        "accepted": "Accepted",
        "wrong_answer": "Wrong Answer",
        "time_limit_exceeded": "Time Limit Exceeded",
        "runtime_error": "Runtime Error",
        "compile_error": "Compile Error",
        "internal_error": "Internal Error",
        "running": "Running",
    }
    status_label = status_map.get(submission.status, submission.status.replace("_", " ").title())
    if submission.status == "accepted":
        if submission.is_sample_run:
            message = f"Tất cả sample tests đã vượt qua ({submission.runtime_ms}ms)."
        else:
            message = f"Chấp nhận! Vượt qua {submission.passed_tests}/{submission.total_tests} test cases trong {submission.runtime_ms}ms."
    elif submission.status == "compile_error":
        message = "Lỗi biên dịch. Vui lòng kiểm tra lại cú pháp."
    elif submission.status == "wrong_answer":
        message = f"Sai kết quả tại test case thứ {submission.passed_tests + 1}."
    elif submission.status == "time_limit_exceeded":
        message = f"Vượt quá giới hạn thời gian ({submission.runtime_ms}ms)."
    else:
        message = status_label
    return {
        "success": True,
        "submission_id": submission.pk,
        "status": submission.status,
        "status_label": status_label,
        "message": message,
        "compile_output": submission.compile_output,
        "stdout_preview": submission.stdout_preview,
        "stderr_preview": submission.stderr_preview,
        "passed_tests": submission.passed_tests,
        "total_tests": submission.total_tests,
        "runtime_ms": submission.runtime_ms,
        "results": [
            {
                "case_name": result.case_name,
                "status": result.status,
                "status_label": status_map.get(result.status, result.status.replace("_", " ").title()),
                "runtime_ms": result.runtime_ms,
                "stdout_preview": result.stdout_preview,
                "stderr_preview": result.stderr_preview,
                "expected_preview": result.expected_preview,
                "actual_preview": result.actual_preview,
            }
            for result in submission.results.all()
        ],
    }
