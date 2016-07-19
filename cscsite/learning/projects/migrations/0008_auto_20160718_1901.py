# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-18 16:01
from __future__ import unicode_literals

from django.db import migrations, models


def update_forward(apps, schema_editor):
    """Copy grade from Project model to each ProjectStudent model"""
    Project = apps.get_model('projects', 'Project')
    ProjectStudent = apps.get_model('projects', 'ProjectStudent')
    for p in Project.objects.all():
        for ps in p.projectstudent_set.all():
            ps.final_grade = p.final_grade
            ps.save()


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_auto_20160718_1817'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectstudent',
            name='final_grade',
            field=models.CharField(choices=[('not_graded', 'Not graded'), ('unsatisfactory', 'Enrollment|Unsatisfactory'), ('pass', 'Enrollment|Pass'), ('good', 'Good'), ('excellent', 'Excellent')], default='not_graded', max_length=15, verbose_name='Final grade'),
        ),
        migrations.AddField(
            model_name='projectstudent',
            name='supervisor_review',
            field=models.TextField(blank=True, verbose_name='Review from supervisor'),
        ),
        migrations.RunPython(update_forward),
    ]
