from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import Article, ArticleRevision, Category


class ArticleHistoryTests(TestCase):
    def setUp(self):
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
        # Give author permissions if necessary (though groups might handle it)
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(Article)
        permissions = Permission.objects.filter(content_type=content_type)
        for perm in permissions:
            self.author.user_permissions.add(perm)

    def test_article_creation_creates_initial_revision(self):
        self.client.login(username='author', password='StrongPass123')
        response = self.client.post(
            reverse('wiki:article-create'),
            {
                'title': 'Initial Article',
                'content': 'This is the first version of the article.',
                'category': self.category.pk,
                'change_summary': 'Initial creation'
            }
        )
        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(title='Initial Article')
        revisions = ArticleRevision.objects.filter(article=article)
        self.assertEqual(revisions.count(), 1)
        self.assertEqual(revisions.first().change_summary, 'Initial creation')
        self.assertEqual(revisions.first().content, 'This is the first version of the article.')

    def test_article_update_creates_new_revision(self):
        article = Article.objects.create(
            title='Updatable Article',
            slug='updatable-article',
            content='Original content.',
            category=self.category,
            author=self.author,
        )
        # Create initial revision manually since we didn't use the view
        ArticleRevision.objects.create(
            article=article,
            title=article.title,
            content=article.content,
            author=self.author,
            change_summary='Initial'
        )

        self.client.login(username='author', password='StrongPass123')
        response = self.client.post(
            reverse('wiki:article-edit', args=[article.pk]),
            {
                'title': 'Updated Article',
                'content': 'Updated content.',
                'category': self.category.pk,
                'change_summary': 'Updated it with more info'
            }
        )
        self.assertEqual(response.status_code, 302)
        
        article.refresh_from_db()
        revisions = ArticleRevision.objects.filter(article=article).order_by('-created_at')
        self.assertEqual(revisions.count(), 2)
        self.assertEqual(revisions[0].change_summary, 'Updated it with more info')
        self.assertEqual(revisions[0].content, 'Updated content.')
        self.assertEqual(revisions[1].change_summary, 'Initial')

    def test_article_history_view_shows_revisions(self):
        article = Article.objects.create(
            title='History Article',
            slug='history-article',
            content='Content v1',
            category=self.category,
            author=self.author,
        )
        ArticleRevision.objects.create(
            article=article, title=article.title, content='Content v1', author=self.author, change_summary='Rev 1'
        )
        ArticleRevision.objects.create(
            article=article, title=article.title, content='Content v2', author=self.author, change_summary='Rev 2'
        )

        response = self.client.get(reverse('wiki:article-history', args=[article.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rev 1')
        self.assertContains(response, 'Rev 2')

    def test_article_revision_detail_view(self):
        article = Article.objects.create(
            title='Detail Article',
            slug='detail-article',
            content='Latest content',
            category=self.category,
            author=self.author,
        )
        rev = ArticleRevision.objects.create(
            article=article, title=article.title, content='Old content', author=self.author, change_summary='Old revision'
        )

        response = self.client.get(reverse('wiki:article-revision-detail', args=[rev.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Old content')
        self.assertContains(response, 'Old revision')
