# Generated by Django 2.2.3 on 2019-07-19 11:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0009_auto_20190701_1242'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='learners_count',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
    ]