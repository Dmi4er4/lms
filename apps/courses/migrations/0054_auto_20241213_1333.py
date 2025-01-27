# Generated by Django 3.2.18 on 2024-12-13 13:33

from django.db import migrations

def undraft_existing_courses(apps, schema_editor):
    apps.get_model('courses', 'Course').objects.update(is_draft=False)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0053_course_draft'),
    ]

    operations = [
        migrations.RunPython(undraft_existing_courses)
    ]