from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import Article, ArticleVote, Category, Comment


class WikiFlowTests(TestCase):
    def setUp(self):
        self.user_group, _ = Group.objects.get_or_create(name='user')
        self.contributor_group, _ = Group.objects.get_or_create(name='contributor')
        self.category = Category.objects.create(
            name='Thuật toán',
            slug='thuat-toan',
            description='Ghi chú về thuật toán',
        )
        self.author = User.objects.create_user(
            username='author',
            password='StrongPass123',
        )
        self.author.groups.add(self.contributor_group)
        self.other_user = User.objects.create_user(
            username='other',
            password='StrongPass123',
        )
        self.other_user.groups.add(self.user_group)
        self.article = Article.objects.create(
            title='Segment Tree',
            slug='segment-tree',
            content='Cau truc du lieu ho tro truy van nhanh.',
            category=self.category,
            author=self.author,
        )
        self.author.profile.display_name = 'Author Display'
        self.author.profile.save(update_fields=['display_name'])

    def test_signup_adds_default_group(self):
        response = self.client.post(
            reverse('wiki:signup'),
            {
                'username': 'newuser',
                'first_name': 'New',
                'last_name': 'User',
                'email': 'new@example.com',
                'password1': 'ComplexPass123',
                'password2': 'ComplexPass123',
            },
        )
        self.assertRedirects(response, reverse('wiki:getting-started'))
        new_user = User.objects.get(username='newuser')
        self.assertTrue(new_user.groups.filter(name='user').exists())

    def test_home_page_is_available_at_root(self):
        response = self.client.get(reverse('wiki:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Home Dashboard')

    def test_search_matches_article_content(self):
        response = self.client.get(reverse('wiki:article-list'), {'q': 'truy van'})
        self.assertContains(response, 'Segment Tree')

    def test_non_author_cannot_edit_article(self):
        self.client.login(username='other', password='StrongPass123')
        response = self.client.get(reverse('wiki:article-edit', args=[self.article.pk]))
        self.assertEqual(response.status_code, 302)

    def test_login_redirects_authenticated_user(self):
        self.client.login(username='other', password='StrongPass123')
        response = self.client.get(reverse('wiki:login'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('wiki:article-list'))

    def test_regular_user_cannot_open_article_create_page(self):
        self.client.login(username='other', password='StrongPass123')
        response = self.client.get(reverse('wiki:article-create'))
        self.assertEqual(response.status_code, 302)

    def test_regular_user_can_comment_on_article(self):
        self.client.login(username='other', password='StrongPass123')
        # post to get captcha value from session first
        get_resp = self.client.get(reverse('wiki:article-detail', args=[self.article.pk, self.article.slug]))
        captcha_answer = get_resp.wsgi_request.session.get('captcha_answer', 1)

        response = self.client.post(
            reverse('wiki:article-detail', args=[self.article.pk, self.article.slug]),
            {'content': 'Hay qua, minh da hieu y tuong.', 'captcha_answer': captcha_answer},
        )
        self.assertRedirects(
            response,
            reverse('wiki:article-detail', args=[self.article.pk, self.article.slug]),
        )
        self.assertTrue(
            Comment.objects.filter(article=self.article, author=self.other_user).exists()
        )

    def test_article_without_category_uses_uncategorized(self):
        article = Article.objects.create(
            title='Binary Search',
            content='Noi dung',
            author=self.author,
        )
        self.assertEqual(article.category.slug, 'chua-phan-loai')

    def test_cannot_comment_when_article_disables_comments(self):
        self.article.allow_comments = False
        self.article.save(update_fields=['allow_comments'])
        self.client.login(username='other', password='StrongPass123')
        get_resp = self.client.get(reverse('wiki:article-detail', args=[self.article.pk, self.article.slug]))
        captcha_answer = get_resp.wsgi_request.session.get('captcha_answer', 1)

        response = self.client.post(
            reverse('wiki:article-detail', args=[self.article.pk, self.article.slug]),
            {'content': 'Thu comment bi khoa.', 'captcha_answer': captcha_answer},
        )
        self.assertRedirects(
            response,
            reverse('wiki:article-detail', args=[self.article.pk, self.article.slug]),
        )
        self.assertFalse(
            Comment.objects.filter(article=self.article, content='Thu comment bi khoa.').exists()
        )

    def test_article_slug_uniqueness_is_enforced_for_duplicate_titles(self):
        article2 = Article.objects.create(
            title='Segment Tree',
            content='Nội dung bài viết trùng tên nhưng slug phải khác.',
            category=self.category,
            author=self.author,
        )
        self.assertNotEqual(article2.slug, self.article.slug)
        self.assertTrue(article2.slug.startswith('segment-tree'))

    def test_setting_duplicate_manual_slug_will_autofix(self):
        article3 = Article(
            title='New Article',
            slug=self.article.slug,
            content='Bài viết thử với slug trùng',
            category=self.category,
            author=self.author,
        )
        article3.save()
        self.assertNotEqual(article3.slug, self.article.slug)
        self.assertEqual(article3.slug, 'new-article')

        # If manual slug duplicates existing one, title-based fallback should create unique slug
        article4 = Article(
            title='Segment Tree',
            slug=self.article.slug,
            content='Nội dung test khác',
            category=self.category,
            author=self.author,
        )
        article4.save()
        self.assertNotEqual(article4.slug, self.article.slug)
        self.assertTrue(article4.slug.startswith('segment-tree'))

    def test_article_list_can_filter_by_author_username(self):
        response = self.client.get(reverse('wiki:article-list'), {'author': 'auth'})
        self.assertContains(response, 'Segment Tree')

        response = self.client.get(reverse('wiki:article-list'), {'author': 'other'})
        self.assertNotContains(response, 'Segment Tree')

    def test_article_list_can_sort_by_vote_score(self):
        other_article = Article.objects.create(
            title='Fenwick Tree',
            content='Cap nhat va truy van prefix sum.',
            category=self.category,
            author=self.author,
        )
        ArticleVote.objects.create(user=self.other_user, article=other_article, value=1)

        response = self.client.get(reverse('wiki:article-list'), {'sort': 'top'})
        articles = list(response.context['articles'])
        self.assertEqual(articles[0], other_article)

    def test_public_profile_is_available_when_user_is_public(self):
        response = self.client.get(reverse('wiki:public-profile', args=[self.author.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Author Display')
        self.assertContains(response, 'Segment Tree')

    def test_private_profile_hides_details_from_other_users(self):
        self.author.profile.is_profile_private = True
        self.author.profile.save(update_fields=['is_profile_private'])

        self.client.login(username='other', password='StrongPass123')
        response = self.client.get(reverse('wiki:public-profile', args=[self.author.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hồ sơ này hiện ở chế độ riêng tư')
        self.assertNotContains(response, 'Segment Tree')

    def test_owner_can_still_view_their_private_profile(self):
        self.author.profile.is_profile_private = True
        self.author.profile.save(update_fields=['is_profile_private'])

        self.client.login(username='author', password='StrongPass123')
        response = self.client.get(reverse('wiki:public-profile', args=[self.author.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Segment Tree')

    def test_vote_user_redirects_back_to_next_url(self):
        self.client.login(username='other', password='StrongPass123')
        response = self.client.post(
            reverse('wiki:user-vote', args=[self.author.pk]),
            {'vote': '1', 'next': reverse('wiki:public-profile', args=[self.author.pk])},
        )
        self.assertRedirects(response, reverse('wiki:public-profile', args=[self.author.pk]))
