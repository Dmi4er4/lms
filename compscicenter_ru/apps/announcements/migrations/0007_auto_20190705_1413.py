# Generated by Django 2.2.3 on 2019-07-05 14:13

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0006_auto_20190701_1309'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='announcementeventdetails',
            options={'verbose_name': 'Announcement Details', 'verbose_name_plural': 'Announcement Details'},
        ),
        migrations.AddField(
            model_name='announcement',
            name='slug',
            field=models.SlugField(default=django.utils.timezone.now, verbose_name='Slug'),
            preserve_default=False,
        ),
    ]
