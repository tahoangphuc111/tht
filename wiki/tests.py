"""
Tests for the wiki application.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Article, ArticleVote, Category, Comment

User = get_user_model()


class WikiFlowTests(TestCase):
    """Integration and flow tests for wiki functionality."""

    def setUp(self):
        """Set up test data before each test."""
        self.user_group, _ = Group.objects.get_or_create(name="user")
        self.contributor_group, _ = Group.objects.get_or_create(name="contributor")
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
        self.assertContains(response, "Home Dashboard")

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

    def test_article_list_can_sort_by_vote_score(self):
        """Test sorting articles by their net vote score."""
        other_article = Article.objects.create(
            title="Fenwick Tree",
            content="Cap nhat va truy van prefix sum.",
            category=self.category,
            author=self.author,
        )
        ArticleVote.objects.create(user=self.other_user, article=other_article, value=1)

        response = self.client.get(reverse("wiki:article-list"), {"sort": "top"})
        articles = list(response.context["articles"])
        self.assertEqual(articles[0], other_article)

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
