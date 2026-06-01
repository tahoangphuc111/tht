from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0017_profile_is_suspended"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="difficulty",
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, "Dịu"), (2, "Cay nhẹ"), (3, "Cay vừa"), (4, "Cay mạnh"), (5, "Siêu cay")], db_index=True, null=True),
        ),
    ]
