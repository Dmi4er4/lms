# Generated by Django 3.2.18 on 2024-10-28 09:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0047_auto_20240830_0818'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='snils',
            field=models.CharField(blank=True, help_text='Individual insurance account number', max_length=64, verbose_name='Student SNILS'),
        ),
    ]