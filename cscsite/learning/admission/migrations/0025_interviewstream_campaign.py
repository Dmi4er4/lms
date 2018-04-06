# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-04-02 16:31
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admission', '0024_auto_20180330_1115'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewstream',
            name='campaign',
            field=models.ForeignKey(default=7, editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='interview_streams', to='admission.Campaign'),
            preserve_default=False,
        ),
    ]