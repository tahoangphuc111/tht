"""Code execution helpers for the coding exercise feature."""

from __future__ import annotations

import subprocess
import threading
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ..models import CodingSubmission, CodingSubmissionResult

RUNNER_LOCK = threading.BoundedSemaphore(
    value=max(1, getattr(settings, "CODE_EXECUTION_MAX_CONCURRENT_JOBS", 2))
)


class CodeRunnerError(Exception):
    """Raised when the code runner cannot complete the request."""


def get_language_config(language):
    """Return the configured language entry."""
    return getattr(settings, "CODE_EXECUTION_LANGUAGE_CONFIGS", {}).get(language, {})


def get_enabled_language_choices():
    """Return enabled language metadata for templates."""
    configs = getattr(settings, "CODE_EXECUTION_LANGUAGE_CONFIGS", {})
    return [
        {
            "key": key,
            "label": cfg.get("label", key),
            "monaco_language": cfg.get("monaco_language", "plaintext"),
        }
        for key, cfg in configs.items()
        if cfg.get("enabled")
    ]


def compare_output(expected_output, actual_output, compare_mode):
    """Compare outputs according to the configured mode."""
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


def _truncate_text(value):
    """Trim text to the configured preview/output limit."""
    if not value:
        return ""
    max_bytes = getattr(settings, "CODE_EXECUTION_MAX_OUTPUT_BYTES", 512 * 1024)
    encoded = value.encode("utf-8", errors="ignore")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _ensure_language_is_available(exercise, language):
    """Validate that the requested language is allowed and enabled."""
    allowed_languages = exercise.allowed_languages or []
    if language not in allowed_languages:
        raise CodeRunnerError("Ngôn ngữ này không được bật cho bài tập.")

    language_config = get_language_config(language)
    if not language_config or not language_config.get("enabled"):
        raise CodeRunnerError("Ngôn ngữ này chưa được cấu hình trên máy chủ.")
    return language_config


def _render_command(command, replacements):
    """Render placeholder arguments in a command list."""
    rendered = []
    for part in command:
        if not part:
            raise CodeRunnerError("Thiếu đường dẫn compiler/runtime trong cấu hình.")
        rendered.append(str(part).format(**replacements))
    return rendered


def _create_job_directory():
    """Create a new isolated working directory for one execution job."""
    root = Path(getattr(settings, "CODE_EXECUTION_TMP_ROOT"))
    root.mkdir(parents=True, exist_ok=True)
    job_dir = root / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def _prepare_csharp_project(job_dir):
    """Create the minimal csproj needed for dotnet builds."""
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
    """Write source code to disk using the configured filename."""
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
    """Run a process using files to keep memory usage low."""
    timeout_seconds = (timeout_ms or getattr(settings, "CODE_EXECUTION_DEFAULT_TIME_LIMIT_MS", 2000)) / 1000
    stdin_path = workdir / "stdin.txt"
    stdout_path = workdir / "stdout.txt"
    stderr_path = workdir / "stderr.txt"
    stdin_path.write_text(input_data or "", encoding="utf-8")
    
    import os
    run_env = os.environ.copy()
    run_env["PYTHONIOENCODING"] = "utf-8"
    run_env["PYTHONUTF8"] = "1"
    run_env["LANG"] = "en_US.UTF-8"
    run_env["LC_ALL"] = "en_US.UTF-8"
    
    started_at = time.perf_counter()
    with open(stdin_path, "rb") as stdin_handle, open(stdout_path, "wb") as stdout_handle, open(stderr_path, "wb") as stderr_handle:
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
    """Compile the source if the language requires a build step."""
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


def _run_testcase(job_dir, language_config, replacements, input_data, expected_output, compare_mode, case_name):
    """Execute a compiled/interpreted program against one testcase."""
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
    elif expected_output is None:
        status = "accepted"
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
    """Compile and run a coding submission, then persist the results."""
    language_config = _ensure_language_is_available(exercise, language)

    max_input_bytes = getattr(settings, "CODE_EXECUTION_MAX_SOURCE_BYTES", 128 * 1024)
    if custom_input and len(custom_input.encode("utf-8")) > max_input_bytes:
        raise CodeRunnerError("Input tùy chỉnh vượt quá giới hạn cho phép.")

    if not RUNNER_LOCK.acquire(timeout=1):
        raise CodeRunnerError("Máy chấm đang bận, vui lòng thử lại sau.")

    submission = CodingSubmission.objects.create(
        exercise=exercise,
        user=user,
        language=language,
        source_code=source_code,
        status="running",
        custom_input=custom_input,
        is_sample_run=sample_only,
    )
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
                )
            )
        else:
            queryset = exercise.testcases.all()
            if sample_only:
                queryset = queryset.filter(is_sample=True)
            queryset = queryset[: getattr(settings, "CODE_EXECUTION_MAX_TESTCASES", 30)]
            total_tests = len(queryset)
            for testcase in queryset:
                testcase_results.append(
                    _run_testcase(
                        job_dir,
                        language_config,
                        replacements,
                        testcase.get_input_data(),
                        testcase.get_expected_output_data(),
                        exercise.compare_mode,
                        testcase.name,
                    )
                )
                if testcase_results[-1]["status"] != "accepted" and not sample_only:
                    break

        passed_tests = sum(1 for item in testcase_results if item["status"] == "accepted")
        final_status = "accepted"
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
    """Turn a submission into a JSON-friendly payload for the frontend."""
    return {
        "success": True,
        "submission_id": submission.pk,
        "status": submission.status,
        "compile_output": submission.compile_output,
        "stdout_preview": submission.stdout_preview,
        "stderr_preview": submission.stderr_preview,
        "passed_tests": submission.passed_tests,
        "total_tests": submission.total_tests,
        "results": [
            {
                "case_name": result.case_name,
                "status": result.status,
                "runtime_ms": result.runtime_ms,
                "stdout_preview": result.stdout_preview,
                "stderr_preview": result.stderr_preview,
                "expected_preview": result.expected_preview,
                "actual_preview": result.actual_preview,
            }
            for result in submission.results.all()
        ],
    }
