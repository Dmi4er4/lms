# Generated by Django 3.1.7 on 2021-02-20 15:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admission', '0019_auto_20210218_1033'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicant',
            name='meta',
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
        migrations.AlterField(
            model_name='applicant',
            name='has_job',
            field=models.BooleanField(help_text='Applicant|has_job', null=True, verbose_name='Do you work?'),
        ),
        migrations.AlterField(
            model_name='applicant',
            name='is_studying',
            field=models.BooleanField(null=True, verbose_name='Are you studying?'),
        ),
        migrations.AlterField(
            model_name='applicant',
            name='level_of_education',
            field=models.CharField(blank=True, choices=[('1', '1 course bachelor, speciality'), ('2', '2 course bachelor, speciality'), ('3', '3 course bachelor, speciality'), ('4', '4 course bachelor, speciality'), ('5', '5 course speciality'), ('6', '6 course speciality'), ('6', '1 course magistracy'), ('7', '2 course magistracy'), ('8', 'postgraduate'), ('9', 'graduate'), ('other', 'Other')], help_text='Applicant|course', max_length=12, null=True, verbose_name='Course'),
        ),
    ]