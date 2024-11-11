# Generated by Django 3.2.18 on 2024-10-28 08:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0054_enrollment_is_grade_recredited'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enrollment',
            name='is_grade_recredited',
            field=models.BooleanField(default=False, help_text='This flag is used to represent that set grade is recredited. Use it with satisfactory grades.', verbose_name='Grade re-credited'),
        ),
    ]