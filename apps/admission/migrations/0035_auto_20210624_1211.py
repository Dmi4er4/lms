# Generated by Django 3.1.12 on 2021-06-24 12:11

import core.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admission', '0034_auto_20210609_1403'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exam',
            name='score',
            field=core.db.fields.ScoreField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='Score'),
        ),
        migrations.AlterField(
            model_name='interview',
            name='section',
            field=models.CharField(choices=[('all_in_1', 'Common Section'), ('math', 'Math'), ('code', 'Code'), ('mv', 'Motivation')], max_length=15, verbose_name='Interview|Section'),
        ),
        migrations.AlterField(
            model_name='interviewstream',
            name='section',
            field=models.CharField(choices=[('all_in_1', 'Common Section'), ('math', 'Math'), ('code', 'Code'), ('mv', 'Motivation')], max_length=15, verbose_name='Interview|Section'),
        ),
    ]
