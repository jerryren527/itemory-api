from django.db import migrations

from app.services.username_helpers import generate_unique_username


def backfill_usernames(apps, schema_editor):
    CustomUser = apps.get_model('app', 'CustomUser')
    for user in CustomUser.objects.filter(username__isnull=True):
        base = user.email.split('@')[0] if user.email else 'user'
        user.username = generate_unique_username(base)
        user.save(update_fields=['username'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_customuser_username'),
    ]

    operations = [
        migrations.RunPython(backfill_usernames, noop_reverse),
    ]
