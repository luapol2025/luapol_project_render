# Generated by Django 5.1.4 on 2025-01-14 09:06

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('luapol_app', '0003_alter_userattemptsbyday_unique_together_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='userattemptsbyday',
            unique_together={('user_fk', 'date_attempted')},
        ),
        migrations.AlterModelTable(
            name='userattemptsbyday',
            table=None,
        ),
    ]
