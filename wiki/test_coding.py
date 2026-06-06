"""Tests for the coding exercise feature."""

import json
import sys
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Article, Category, CodingExercise, CodingTestCase

User = get_user_model()


TEST_LANGUAGE_CONFIG = {
    "python": {
        "label": "Python 3",
        "monaco_language": "python",
        "source_name": "main.py",
        "compile": [],
        "run": [sys.executable, "{source_path}"],
        "starter_code": "print(input())\n",
        "enabled": True,
    }
}


@override_settings(
    CODE_EXECUTION_LANGUAGE_CONFIGS=TEST_LANGUAGE_CONFIG,
    CODE_EXECUTION_TMP_ROOT=Path(tempfile.gettempdir()) / "cpwiki_judge_tests",
    CODE_EXECUTION_MAX_TESTCASES=10,
    CELERY_TASK_ALWAYS_EAGER=True,
    CODE_EXECUTION_USE_DOCKER=False,
    TESTING=True,
)
class CodingExerciseTests(TestCase):
    """Exercise management and judging tests."""

    def setUp(self):
        """Create baseline users, article, and exercise."""
        self.category = Category.objects.create(name="Code", slug="code")
        self.author = User.objects.create_user(
            username="author",
            password="StrongPass123",
        )
        self.other_user = User.objects.create_user(
            username="other",
            password="StrongPass123",
        )
        contributor_group, _ = Group.objects.get_or_create(name="contributor")
        self.author.groups.add(contributor_group)

        content_type = ContentType.objects.get_for_model(Article)
        for perm in Permission.objects.filter(content_type=content_type):
            self.author.user_permissions.add(perm)

        self.article = Article.objects.create(
            title="A + B",
            slug="a-plus-b",
            content="Tinh tong hai so.",
            category=self.category,
            author=self.author,
            status="published",
        )
        self.exercise = CodingExercise.objects.create(
            article=self.article,
            title="A + B",
            description="Doc hai so va in tong.",
            is_enabled=True,
            allowed_languages=["python"],
            default_language="python",
            starter_code_map={"python": "a, b = map(int, input().split())\nprint(a + b)\n"},
        )
        CodingTestCase.objects.create(
            exercise=self.exercise,
            name="sample-1",
            input_text="1 2\n",
            expected_output_text="3\n",
            is_sample=True,
            order=1,
        )
        CodingTestCase.objects.create(
            exercise=self.exercise,
            name="hidden-1",
            input_text="4 5\n",
            expected_output_text="9\n",
            is_sample=False,
            order=2,
        )

    def test_author_can_open_coding_manage_page(self):
        """The article author should be able to manage the coding exercise."""
        self.client.login(username="author", password="StrongPass123")
        response = self.client.get(
            reverse("wiki:article-coding-manage", args=[self.article.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mini OJ")

    def test_non_author_cannot_open_testcase_create_page(self):
        """Only the author can open testcase management routes."""
        self.client.login(username="other", password="StrongPass123")
        response = self.client.get(
            reverse("wiki:coding-testcase-create", args=[self.exercise.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("wiki:article-detail", args=[self.article.pk, self.article.slug]),
        )

    def test_submit_code_accepts_correct_solution(self):
        """Submit endpoint should judge the code against all testcases."""
        self.client.login(username="other", password="StrongPass123")
        response = self.client.post(
            reverse("wiki:submit-code", args=[self.article.pk]),
            data=json.dumps(
                {
                    "language": "python",
                    "source_code": "a, b = map(int, input().split())\nprint(a + b)\n",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(data["passed_tests"], 2)

    def test_run_code_returns_stdout_for_custom_input(self):
        """Run endpoint should execute one custom input without testcase comparison."""
        self.client.login(username="other", password="StrongPass123")
        response = self.client.post(
            reverse("wiki:run-code", args=[self.article.pk]),
            data=json.dumps(
                {
                    "language": "python",
                    "source_code": "print(input()[::-1])\n",
                    "custom_input": "abc\n",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "accepted")
        self.assertIn("cba", data["stdout_preview"])

    def test_custom_checker_python_accepted(self):
        """Submit code with a custom python checker that validates actual output is double the input."""
        self.exercise.compare_mode = "custom_checker"
        self.exercise.checker_language = "python"
        self.exercise.checker_code = (
            "import sys\n"
            "with open(sys.argv[1]) as f: inp = f.read().strip()\n"
            "with open(sys.argv[2]) as f: act = f.read().strip()\n"
            "try:\n"
            "    if int(act) == int(inp) * 2: sys.exit(0)\n"
            "    else: sys.exit(1)\n"
            "except Exception:\n"
            "    sys.exit(1)\n"
        )
        self.exercise.save()

        # Update testcase outputs to something else just to verify custom checker is called
        self.exercise.testcases.all().delete()
        CodingTestCase.objects.create(
            exercise=self.exercise,
            name="custom-test",
            input_text="5\n",
            expected_output_text="10\n",
            is_sample=True,
            order=1,
        )

        self.client.login(username="other", password="StrongPass123")
        response = self.client.post(
            reverse("wiki:submit-code", args=[self.article.pk]),
            data=json.dumps(
                {
                    "language": "python",
                    "source_code": "x = int(input())\nprint(x * 2)\n",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "accepted")

    def test_run_code_does_not_count_as_submission(self):
        """Verify that running code (either sample tests or custom input) does not record a real submission or affect leaderboard."""
        from .models import CodingSubmission

        self.client.login(username="other", password="StrongPass123")

        # 1. Run code with custom input
        response = self.client.post(
            reverse("wiki:run-code", args=[self.article.pk]),
            data=json.dumps(
                {
                    "language": "python",
                    "source_code": "print(input())\n",
                    "custom_input": "hello\n",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Verify it created a trial run
        latest_run = CodingSubmission.objects.filter(user=self.other_user).latest("id")
        self.assertTrue(latest_run.is_sample_run)

        # 2. Check Submission History View - should be empty
        response = self.client.get(reverse("wiki:submissions-history"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["submissions"]), 0)

        # 3. Check Leaderboard View - should not count toward scores
        response = self.client.get(reverse("wiki:leaderboard"))
        self.assertEqual(response.status_code, 200)
        other_user_data = None
        for u in response.context["users"]:
            if u.username == self.other_user.username:
                other_user_data = u
                break
        self.assertIsNotNone(other_user_data)
        self.assertEqual(other_user_data.accepted_count, 0)
        self.assertEqual(other_user_data.total_score, 0)
