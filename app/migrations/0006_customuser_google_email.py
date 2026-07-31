from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_alter_customuser_apple_sub'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='google_email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]
