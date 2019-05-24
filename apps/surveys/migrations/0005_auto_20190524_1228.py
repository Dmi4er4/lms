# Generated by Django 2.2.1 on 2019-05-24 12:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0004_remove_coursesurvey_publish_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coursesurvey',
            name='expire_at',
            field=models.DateTimeField(help_text="With published selected, won't be shown after this time.", verbose_name='Expires on'),
        ),
    ]