# Generated by Django 3.2.18 on 2024-05-26 18:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0046_alter_course_default_grade'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='ends_on',
            field=models.DateField(blank=True, help_text='If left blank the closing date of the semester is used', null=True, verbose_name='Closing Day'),
        ),
        migrations.AddField(
            model_name='course',
            name='starts_on',
            field=models.DateField(blank=True, help_text='If left blank the start date of the semester is used', null=True, verbose_name='Starts on'),
        ),
        migrations.AlterField(
            model_name='course',
            name='default_grade',
            field=models.CharField(choices=[('not_graded', 'Not graded'), ('without_grade', 'Without Grade')], default='not_graded', max_length=100, verbose_name='Enrollment|default_grade'),
        ),
    ]
