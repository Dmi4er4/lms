# Generated by Django 3.1.7 on 2021-03-02 07:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0027_auto_20210301_1724'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='calendar_key',
            field=models.CharField(blank=True, max_length=128, unique=True),
        ),
    ]