# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-07-09 10:59
from __future__ import unicode_literals

from django.db import migrations


def forward(apps, schema_editor):
    EmailTemplate = apps.get_model("post_office", "EmailTemplate")
    template_name = "admission-interview-invitation-n-streams"
    if not EmailTemplate.objects.filter(name=template_name).exists():
        template = EmailTemplate(name=template_name)
        template.save()


class Migration(migrations.Migration):

    dependencies = [
        ('admission', '0002_auto_20181019_1339'),
        ('post_office', '0006_attachment_mimetype'),
    ]

    operations = [
        migrations.RunPython(forward)
    ]