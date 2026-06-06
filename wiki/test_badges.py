"""
Tests for the new badge awarding and quiz answer persistence features.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import (
    Article,
    Category,
    CodingExercise,
    CodingSubmission,
    Question,
    Choice,
    UserAnswer,
    Badge,
    UserBadge,
)

User = get_user_model()


class BadgeSystemTests(TestCase):
    """Test cases for the badge milestone awarding logic."""

    def setUp(self):
        self.category = Category.objects.create(name="Algorithms", slug="algorithms")

        # Create user
        self.user = User.objects.create_user(
            username="codewarrior",
            password="StrongPassword123"
        )
        self.client.login(username="codewarrior", password="StrongPassword123")

        # Create multiple articles with exercises
        self.articles = []
        self.exercises = []
        for i in range(1, 4):
            art = Article.objects.create(
                title=f"Exercise Article {i}",
                slug=f"exercise-article-{i}",
                content="Content description",
                category=self.category,
                author=self.user,
                status="published"
            )
            self.articles.append(art)

            ex = CodingExercise.objects.create(
                article=art,
                title=f"Exercise {i}",
                is_enabled=True,
                allowed_languages=["python"],
                default_language="python"
            )
            self.exercises.append(ex)

    def test_first_accepted_badge_awarded(self):
        """User gets first-accepted badge on their first accepted coding submission."""
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge__slug="first-accepted").exists())

        # Create accepted coding submission
        CodingSubmission.objects.create(
            exercise=self.exercises[0],
            user=self.user,
            language="python",
            source_code="print(1)",
            status="accepted",
            is_sample_run=False
        )

        # Check if first-accepted badge was awarded automatically via signal
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__slug="first-accepted").exists())
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge__slug="code-warrior").exists())

    def test_code_warrior_badge_awarded(self):
        """User gets code-warrior badge when solving 3 different coding exercises."""
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge__slug="code-warrior").exists())

        # Solve 1st exercise
        CodingSubmission.objects.create(
            exercise=self.exercises[0],
            user=self.user,
            language="python",
            source_code="print(1)",
            status="accepted",
            is_sample_run=False
        )
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge__slug="code-warrior").exists())

        # Solve 2nd exercise
        CodingSubmission.objects.create(
            exercise=self.exercises[1],
            user=self.user,
            language="python",
            source_code="print(2)",
            status="accepted",
            is_sample_run=False
        )
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge__slug="code-warrior").exists())

        # Solve 3rd exercise
        CodingSubmission.objects.create(
            exercise=self.exercises[2],
            user=self.user,
            language="python",
            source_code="print(3)",
            status="accepted",
            is_sample_run=False
        )

        # Should now have code-warrior badge
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__slug="code-warrior").exists())

    def test_quiz_persistence_and_badges(self):
        """Test that submitting a quiz persists answers and awards quiz-related badges."""
        # Create questions and choices for 3 articles to support quiz-enthusiast (3 quizzes)
        for idx, art in enumerate(self.articles):
            q = Question.objects.create(
                article=art,
                content=f"Question for quiz {idx}",
                order=1,
                explanation="Explanation text"
            )
            Choice.objects.create(question=q, content="Correct", is_correct=True)
            Choice.objects.create(question=q, content="Incorrect", is_correct=False)

        # Check initial state
        self.assertEqual(UserAnswer.objects.filter(user=self.user).count(), 0)
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge__slug="quiz-master").exists())
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge__slug="quiz-enthusiast").exists())

        # Submit quiz 1 (100% correct)
        q1 = self.articles[0].questions.first()
        c1_correct = q1.choices.filter(is_correct=True).first()

        url1 = reverse("wiki:submit-quiz", args=[self.articles[0].pk])
        response = self.client.post(
            url1,
            data={"answers": {str(q1.pk): str(c1_correct.pk)}},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserAnswer.objects.filter(user=self.user).count(), 1)

        # Should get quiz-master since score is 100% (1/1 correct)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__slug="quiz-master").exists())
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge__slug="quiz-enthusiast").exists())

        # Submit quiz 2 (incorrect choice to check persistence but not master)
        q2 = self.articles[1].questions.first()
        c2_incorrect = q2.choices.filter(is_correct=False).first()

        url2 = reverse("wiki:submit-quiz", args=[self.articles[1].pk])
        response = self.client.post(
            url2,
            data={"answers": {str(q2.pk): str(c2_incorrect.pk)}},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserAnswer.objects.filter(user=self.user).count(), 2)

        # Submit quiz 3 (correct choice)
        q3 = self.articles[2].questions.first()
        c3_correct = q3.choices.filter(is_correct=True).first()

        url3 = reverse("wiki:submit-quiz", args=[self.articles[2].pk])
        response = self.client.post(
            url3,
            data={"answers": {str(q3.pk): str(c3_correct.pk)}},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Since user has attempted 3 quizzes (1, 2, and 3), they should get quiz-enthusiast
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__slug="quiz-enthusiast").exists())
