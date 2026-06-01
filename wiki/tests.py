"""
Tests for the wiki application.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
import tempfile
import shutil
from django.urls import reverse

from .models import Article, ArticleVote, Category, Comment, Question, UploadedFile

User = get_user_model()


class WikiFlowTests(TestCase):
    """Integration and flow tests for wiki functionality."""

    def setUp(self):
        """Set up test data before each test."""
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth.models import Permission
        self.user_group, _ = Group.objects.get_or_create(name="user")
        self.contributor_group, _ = Group.objects.get_or_create(name="contributor")
        # Ensure user group has permission to comment
        comment_ct = ContentType.objects.get_for_model(Comment)
        add_comment_perm = Permission.objects.get(codename="add_comment", content_type=comment_ct)
        self.user_group.permissions.add(add_comment_perm)

        self.category = Category.objects.create(
            name="Thuật toán",
            slug="thuat-toan",
            description="Ghi chú về thuật toán",
        )
        self.author = User.objects.create_user(
            username="author",
            password="StrongPass123",
        )
        self.author.groups.add(self.contributor_group)
        self.other_user = User.objects.create_user(
            username="other",
            password="StrongPass123",
        )
        self.other_user.groups.add(self.user_group)
        self.article = Article.objects.create(
            title="Segment Tree",
            slug="segment-tree",
            content="Cau truc du lieu ho tro truy van nhanh.",
            category=self.category,
            author=self.author,
            status="published",
        )
        self.author.profile.display_name = "Author Display"
        self.author.profile.save(update_fields=["display_name"])

    def test_signup_adds_default_group(self):
        """Test that user registration assigns the default group."""
        response = self.client.post(
            reverse("wiki:signup"),
            {
                "username": "newuser",
                "first_name": "New",
                "last_name": "User",
                "email": "new@example.com",
                "password1": "ComplexPass123",
                "password2": "ComplexPass123",
            },
        )
        self.assertRedirects(response, reverse("wiki:getting-started"))
        new_user = User.objects.get(username="newuser")
        self.assertTrue(new_user.groups.filter(name="user").exists())

    def test_home_page_is_available_at_root(self):
        """Test that the home page is accessible."""
        response = self.client.get(reverse("wiki:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CP Wiki")

    def test_home_page_does_not_show_article_content_preview(self):
        response = self.client.get(reverse("wiki:home"))
        self.assertContains(response, "Segment Tree")
        self.assertNotContains(response, "Cau truc du lieu ho tro truy van nhanh.")

    def test_search_matches_article_content(self):
        """Test that searching finds articles by content."""
        response = self.client.get(reverse("wiki:article-list"), {"q": "truy van"})
        self.assertContains(response, "Segment Tree")

    def test_non_author_cannot_edit_article(self):
        """Test that users cannot edit articles they didn't write."""
        self.client.login(username="other", password="StrongPass123")
        response = self.client.get(reverse("wiki:article-edit", args=[self.article.pk]))
        self.assertEqual(response.status_code, 302)

    def test_login_redirects_authenticated_user(self):
        """Test that logged-in users are redirected from the login page."""
        self.client.login(username="other", password="StrongPass123")
        response = self.client.get(reverse("wiki:login"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wiki:article-list"))

    def test_regular_user_cannot_open_article_create_page(self):
        """Test that regular users cannot create articles."""
        self.client.login(username="other", password="StrongPass123")
        response = self.client.get(reverse("wiki:article-create"))
        self.assertEqual(response.status_code, 302)

    def test_regular_user_can_comment_on_article(self):
        """Test that users can post comments on articles."""
        self.client.login(username="other", password="StrongPass123")
        # post to get captcha value from session first
        get_resp = self.client.get(
            reverse("wiki:article-detail", args=[self.article.pk, self.article.slug])
        )
        captcha_answer = get_resp.wsgi_request.session.get("captcha_answer", 1)

        response = self.client.post(
            reverse("wiki:article-detail", args=[self.article.pk, self.article.slug]),
            {
                "content": "Hay qua, minh da hieu y tuong.",
                "captcha_answer": captcha_answer,
            },
        )
        self.assertRedirects(
            response,
            reverse("wiki:article-detail", args=[self.article.pk, self.article.slug]),
        )
        self.assertTrue(
            Comment.objects.filter(
                article=self.article, author=self.other_user
            ).exists()
        )

    def test_article_without_category_uses_uncategorized(self):
        """Test that articles default to 'Uncategorized' if none provided."""
        article = Article.objects.create(
            title="Binary Search",
            content="Noi dung",
            author=self.author,
        )
        self.assertEqual(article.category.slug, "chua-phan-loai")

    def test_cannot_comment_when_article_disables_comments(self):
        """Test that comments are blocked if disabled for an article."""
        self.article.allow_comments = False
        self.article.save(update_fields=["allow_comments"])
        self.client.login(username="other", password="StrongPass123")
        get_resp = self.client.get(
            reverse("wiki:article-detail", args=[self.article.pk, self.article.slug])
        )
        captcha_answer = get_resp.wsgi_request.session.get("captcha_answer", 1)

        response = self.client.post(
            reverse("wiki:article-detail", args=[self.article.pk, self.article.slug]),
            {"content": "Thu comment bi khoa.", "captcha_answer": captcha_answer},
        )
        self.assertRedirects(
            response,
            reverse("wiki:article-detail", args=[self.article.pk, self.article.slug]),
        )
        self.assertFalse(
            Comment.objects.filter(
                article=self.article, content="Thu comment bi khoa."
            ).exists()
        )

    def test_article_slug_uniqueness_is_enforced(self):
        """Test that duplicate titles result in unique slugs."""
        article2 = Article.objects.create(
            title="Segment Tree",
            content="Nội dung bài viết trùng tên nhưng slug phải khác.",
            category=self.category,
            author=self.author,
        )
        self.assertNotEqual(article2.slug, self.article.slug)
        self.assertTrue(article2.slug.startswith("segment-tree"))

    def test_setting_duplicate_manual_slug_will_autofix(self):
        """Test that manually set duplicate slugs are automatically fixed."""
        article3 = Article(
            title="New Article",
            slug=self.article.slug,
            content="Bài viết thử với slug trùng",
            category=self.category,
            author=self.author,
        )
        article3.save()
        self.assertNotEqual(article3.slug, self.article.slug)
        self.assertEqual(article3.slug, "new-article")

        # If manual slug duplicates existing one, title fallback should work
        article4 = Article(
            title="Segment Tree",
            slug=self.article.slug,
            content="Nội dung test khác",
            category=self.category,
            author=self.author,
        )
        article4.save()
        self.assertNotEqual(article4.slug, self.article.slug)
        self.assertTrue(article4.slug.startswith("segment-tree"))

    def test_article_list_can_filter_by_author_username(self):
        """Test filtering articles by author's username."""
        response = self.client.get(reverse("wiki:article-list"), {"author": "auth"})
        self.assertContains(response, "Segment Tree")

        response = self.client.get(reverse("wiki:article-list"), {"author": "other"})
        self.assertNotContains(response, "Segment Tree")

    def test_article_list_does_not_show_content_preview(self):
        response = self.client.get(reverse("wiki:article-list"))
        self.assertContains(response, "Segment Tree")
        self.assertNotContains(response, "Cau truc du lieu ho tro truy van nhanh.")

    def test_article_list_can_sort_by_vote_score(self):
        """Test sorting articles by their net vote score."""
        other_article = Article.objects.create(
            title="Fenwick Tree",
            content="Cap nhat va truy van prefix sum.",
            category=self.category,
            author=self.author,
            status="published",
        )
        ArticleVote.objects.create(user=self.other_user, article=other_article, value=1)

        response = self.client.get(reverse("wiki:article-list"), {"sort": "top"})
        articles = list(response.context["articles"])
        self.assertEqual(articles[0], other_article)

    def test_martor_uploader_saves_file_to_media(self):
        """Test that Martor uploads use a real endpoint instead of /media/."""
        tmpdir = tempfile.mkdtemp(prefix="cpwiki_test_media_")
        try:
            with override_settings(MEDIA_ROOT=tmpdir):
                self.client.login(username="author", password="StrongPass123")
                upload = SimpleUploadedFile(
                    "note.png",
                    b"fake png data",
                    content_type="image/png",
                )

                response = self.client.post(
                    "/martor/uploader/",
                    {"markdown-image-upload": upload},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["status"], 200)
                self.assertEqual(data["name"], "note.png")
                self.assertIn("/media/martor/", data["link"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_article_create_saves_attachments(self):
        """Article attachments from the create form should be persisted."""
        tmpdir = tempfile.mkdtemp(prefix="cpwiki_test_media_")
        try:
            with override_settings(MEDIA_ROOT=tmpdir):
                self.client.login(username="author", password="StrongPass123")
                upload = SimpleUploadedFile(
                    "diagram.png",
                    b"fake png data",
                    content_type="image/png",
                )

                response = self.client.post(
                    reverse("wiki:article-create"),
                    {
                        "title": "Article With Attachment",
                        "slug": "article-with-attachment",
                        "category": self.category.pk,
                        "tags": "",
                        "allow_comments": "on",
                        "status": "pending",
                        "content": "Noi dung bai viet.",
                        "change_summary": "Initial",
                        "attachments": upload,
                    },
                )

                article = Article.objects.get(slug="article-with-attachment")
                self.assertRedirects(response, article.get_absolute_url())
                self.assertTrue(
                    UploadedFile.objects.filter(
                        article=article,
                        user=self.author,
                        file__contains="diagram",
                    ).exists()
                )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_article_attachment_validation_error_is_visible(self):
        """Invalid article attachments should show a form error."""
        self.client.login(username="author", password="StrongPass123")
        upload = SimpleUploadedFile(
            "notes.txt",
            b"plain text",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("wiki:article-create"),
            {
                "title": "Article With Bad Attachment",
                "slug": "article-with-bad-attachment",
                "category": self.category.pk,
                "tags": "",
                "allow_comments": "on",
                "status": "pending",
                "content": "Noi dung bai viet.",
                "change_summary": "Initial",
                "attachments": upload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "notes.txt")
        self.assertContains(response, "Chỉ hỗ trợ upload file pdf, docx, png, jpg.")
        self.assertFalse(
            Article.objects.filter(slug="article-with-bad-attachment").exists()
        )

    def test_public_profile_is_available(self):
        """Test that public user profiles are accessible."""
        response = self.client.get(
            reverse("wiki:public-profile", args=[self.author.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Author Display")
        self.assertContains(response, "Segment Tree")

    def test_private_profile_hides_details(self):
        """Test that private profiles are hidden from other users."""
        self.author.profile.is_profile_private = True
        self.author.profile.save(update_fields=["is_profile_private"])

        self.client.login(username="other", password="StrongPass123")
        response = self.client.get(
            reverse("wiki:public-profile", args=[self.author.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hồ sơ này hiện ở chế độ riêng tư")
        self.assertNotContains(response, "Segment Tree")

    def test_owner_can_still_view_their_private_profile(self):
        """Test that owners can see their own private profile."""
        self.author.profile.is_profile_private = True
        self.author.profile.save(update_fields=["is_profile_private"])

        self.client.login(username="author", password="StrongPass123")
        response = self.client.get(
            reverse("wiki:public-profile", args=[self.author.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Segment Tree")

    def test_vote_user_redirects_back_to_next_url(self):
        """Test that voting for a user redirects back to the original page."""
        self.client.login(username="other", password="StrongPass123")
        response = self.client.post(
            reverse("wiki:user-vote", args=[self.author.pk]),
            {
                "vote": "1",
                "next": reverse("wiki:public-profile", args=[self.author.pk]),
            },
        )
        self.assertRedirects(
            response, reverse("wiki:public-profile", args=[self.author.pk])
        )

    def test_non_author_cannot_create_quiz_question_by_direct_url(self):
        """Quiz question create must be restricted to the article owner."""
        self.client.login(username="other", password="StrongPass123")
        response = self.client.get(
            reverse("wiki:question-create", args=[self.article.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("wiki:article-detail", args=[self.article.pk, self.article.slug]),
        )

    def test_question_create_form_supports_file_uploads(self):
        """Question create form must allow uploaded files."""
        self.client.login(username="author", password="StrongPass123")
        response = self.client.get(reverse("wiki:question-create", args=[self.article.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="question_file"')

    def test_question_can_be_created_from_uploaded_text_file(self):
        """Uploaded question source files should populate question content."""
        self.client.login(username="author", password="StrongPass123")
        upload = SimpleUploadedFile(
            "question.txt",
            b"What is binary search?",
            content_type="text/plain",
        )
        response = self.client.post(
            reverse("wiki:question-create", args=[self.article.pk]),
            {
                "question_file": upload,
                "explanation": "",
                "order": "1",
                "choices-TOTAL_FORMS": "0",
                "choices-INITIAL_FORMS": "0",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertRedirects(
            response,
            reverse("wiki:article-quiz-manage", args=[self.article.pk]),
        )
        self.assertTrue(
            Question.objects.filter(
                article=self.article,
                content="What is binary search?",
            ).exists()
        )

    def test_question_can_be_created_from_uploaded_pdf_file(self):
        """PDF uploads should be accepted when creating quiz questions."""
        self.client.login(username="author", password="StrongPass123")
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n"
            b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
            b"5 0 obj<< /Length 44 >>stream\n"
            b"BT /F1 12 Tf 72 72 Td (PDF question text?) Tj ET\n"
            b"endstream\nendobj\nxref\n0 6\n0000000000 65535 f \n"
            b"0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \n0000000241 00000 n \n"
            b"0000000311 00000 n \ntrailer<< /Root 1 0 R /Size 6 >>\n"
            b"startxref\n405\n%%EOF\n"
        )
        upload = SimpleUploadedFile(
            "question.pdf",
            pdf_bytes,
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("wiki:question-create", args=[self.article.pk]),
            {
                "question_file": upload,
                "explanation": "",
                "order": "1",
                "choices-TOTAL_FORMS": "0",
                "choices-INITIAL_FORMS": "0",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertRedirects(
            response,
            reverse("wiki:article-quiz-manage", args=[self.article.pk]),
        )
        self.assertTrue(
            Question.objects.filter(
                article=self.article,
                content__contains="PDF question text?",
            ).exists()
        )

    def test_invalid_question_pdf_shows_form_error(self):
        """Invalid PDFs should not crash the question create view."""
        self.client.login(username="author", password="StrongPass123")
        upload = SimpleUploadedFile(
            "broken.pdf",
            b"not a real pdf",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("wiki:question-create", args=[self.article.pk]),
            {
                "question_file": upload,
                "explanation": "",
                "order": "1",
                "choices-TOTAL_FORMS": "0",
                "choices-INITIAL_FORMS": "0",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Không thể đọc file này")
        self.assertFalse(Question.objects.filter(article=self.article).exists())

    def test_quiz_file_upload_creates_questions(self):
        """Bulk quiz upload should import question blocks from a text file."""
        self.client.login(username="author", password="StrongPass123")
        upload = SimpleUploadedFile(
            "quiz.txt",
            b"Question number one content check?\n\nQuestion number two content check?",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("wiki:upload-quiz-file", args=[self.article.pk]),
            {"quiz_file": upload},
        )

        self.assertRedirects(
            response,
            reverse("wiki:article-quiz-manage", args=[self.article.pk]),
        )
        self.assertEqual(
            Question.objects.filter(article=self.article).count(),
            2,
        )

    def test_profile_page_has_required_context(self):
        """Profile page should receive the data its template depends on."""
        self.client.login(username="author", password="StrongPass123")
        response = self.client.get(reverse("wiki:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile", response.context)
        self.assertIn("chart_labels", response.context)
        self.assertIn("recent_comments", response.context)

    def test_guest_saved_articles_endpoint_redirects_to_login(self):
        """Saved articles endpoint should stay protected for guests."""
        response = self.client.get(reverse("wiki:saved-articles-json"))
        self.assertEqual(response.status_code, 302)

    def test_numeric_username_collision_profile_view(self):
        """Test that profile view prioritizes username over numeric ID to prevent collisions."""
        numeric_user = User.objects.create_user(
            username="999",
            password="StrongPass123",
        )
        response = self.client.get(reverse("wiki:public-profile", args=["999"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], numeric_user)

    def test_user_list_vote_score_distinct_count(self):
        """Test that UserListView's vote_score is not inflated by Cartesian product."""
        Article.objects.create(
            title="Extra Article 1",
            content="Content",
            author=self.author,
        )
        from .models import UserVote
        UserVote.objects.create(
            voter=self.other_user,
            target=self.author,
            value=1
        )
        response = self.client.get(reverse("wiki:user-list"))
        self.assertEqual(response.status_code, 200)
        users = {u.username: u.vote_score for u in response.context["users"]}
        self.assertEqual(users.get("author"), 1)

    def test_vote_update_triggers_notification(self):
        """Test that updating a vote from downvote to upvote sends a notification."""
        vote = ArticleVote.objects.create(
            user=self.other_user,
            article=self.article,
            value=-1
        )
        from .models import Notification
        Notification.objects.all().delete()

        vote.value = 1
        vote.save()

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.article.author,
                sender=self.other_user,
                message__contains="upvote"
            ).exists()
        )

    def test_upload_quiz_file_parses_choices(self):
        """Test that uploading a formatted quiz file imports choices and answers correctly."""
        self.client.login(username="author", password="StrongPass123")
        quiz_content = (
            "Cau 1: Thu do cua VN la gi?\n"
            "*A. Ha Noi\n"
            "B. HCM\n"
            "C. Da Nang\n"
            "Explanation: Ha Noi la thu do.\n"
        )
        upload = SimpleUploadedFile(
            "quiz_formatted.txt",
            quiz_content.encode("utf-8"),
            content_type="text/plain",
        )
        response = self.client.post(
            reverse("wiki:upload-quiz-file", args=[self.article.pk]),
            {"quiz_file": upload},
        )
        self.assertRedirects(
            response,
            reverse("wiki:article-quiz-manage", args=[self.article.pk]),
        )

        question = Question.objects.filter(article=self.article, content="Cau 1: Thu do cua VN la gi?").first()
        self.assertIsNotNone(question)
        self.assertEqual(question.explanation, "Ha Noi la thu do.")

        choices = list(question.choices.all())
        self.assertEqual(len(choices), 3)

        correct_choices = [c for c in choices if c.is_correct]
        self.assertEqual(len(correct_choices), 1)
        self.assertEqual(correct_choices[0].content, "Ha Noi")

    def test_leaderboard_counts_distinct_solved_exercises(self):
        """Test that the leaderboard counts only unique coding exercises solved by a user."""
        from .models import CodingExercise, CodingSubmission

        # Create a coding exercise
        exercise = CodingExercise.objects.create(
            article=self.article,
            title="Algorithm Quiz",
            is_enabled=True,
            allowed_languages=["python"],
        )

        # Submit twice for the same exercise and get accepted both times
        CodingSubmission.objects.create(
            exercise=exercise,
            user=self.other_user,
            language="python",
            status="accepted",
            score=100,
        )
        CodingSubmission.objects.create(
            exercise=exercise,
            user=self.other_user,
            language="python",
            status="accepted",
            score=100,
        )

        response = self.client.get(reverse("wiki:leaderboard"))
        self.assertEqual(response.status_code, 200)

        # The other_user is in context['users']
        other_user_data = None
        for u in response.context["users"]:
            if u.username == self.other_user.username:
                other_user_data = u
                break

        self.assertIsNotNone(other_user_data)
        # It should count only 1 solved exercise (not 2)
        self.assertEqual(other_user_data.accepted_count, 1)

        # total_score = articles (0) * 10 + solved (1) * 5 = 5
        self.assertEqual(other_user_data.total_score, 5)

    def test_choice_formset_validation_enforces_choices_count_and_correctness(self):
        """Test that ChoiceFormSet validation requires at least 2 choices and exactly 1 correct choice."""
        self.client.login(username="author", password="StrongPass123")

        # Case A: Less than 2 choices (e.g. 1 choice)
        response = self.client.post(
            reverse("wiki:question-create", args=[self.article.pk]),
            {
                "content": "Cau hoi test?",
                "explanation": "",
                "order": "1",
                "choices-TOTAL_FORMS": "1",
                "choices-INITIAL_FORMS": "0",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "1000",
                "choices-0-content": "Lựa chọn 1",
                "choices-0-is_correct": "on",
            },
        )
        self.assertEqual(response.status_code, 200)  # Form invalid, re-renders page
        formset = response.context["choice_formset"]
        self.assertIn("Một câu hỏi cần có ít nhất 2 lựa chọn.", formset.non_form_errors())

        # Case B: 2 choices but 0 correct choice
        response = self.client.post(
            reverse("wiki:question-create", args=[self.article.pk]),
            {
                "content": "Cau hoi test?",
                "explanation": "",
                "order": "1",
                "choices-TOTAL_FORMS": "2",
                "choices-INITIAL_FORMS": "0",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "1000",
                "choices-0-content": "Lựa chọn 1",
                "choices-1-content": "Lựa chọn 2",
            },
        )
        self.assertEqual(response.status_code, 200)
        formset = response.context["choice_formset"]
        self.assertIn("Cần chọn ít nhất một lựa chọn làm đáp án đúng.", formset.non_form_errors())

        # Case C: 2 choices but multiple correct choices
        response = self.client.post(
            reverse("wiki:question-create", args=[self.article.pk]),
            {
                "content": "Cau hoi test?",
                "explanation": "",
                "order": "1",
                "choices-TOTAL_FORMS": "2",
                "choices-INITIAL_FORMS": "0",
                "choices-MIN_NUM_FORMS": "0",
                "choices-MAX_NUM_FORMS": "1000",
                "choices-0-content": "Lựa chọn 1",
                "choices-0-is_correct": "on",
                "choices-1-content": "Lựa chọn 2",
                "choices-1-is_correct": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        formset = response.context["choice_formset"]
        self.assertIn("Chỉ được chọn duy nhất một đáp án đúng.", formset.non_form_errors())
