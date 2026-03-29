from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0008_alter_article_created_at_alter_article_updated_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='is_profile_private',
            field=models.BooleanField(default=False, help_text='Bật để chỉ bạn và admin có thể xem đầy đủ hồ sơ này.'),
        ),
        migrations.AddField(
            model_name='profile',
            name='show_email_publicly',
            field=models.BooleanField(default=False, help_text='Cho phép hiển thị email trên hồ sơ công khai.'),
        ),
    ]
