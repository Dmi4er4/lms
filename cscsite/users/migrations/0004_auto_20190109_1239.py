# Generated by Django 2.1.5 on 2019-01-09 12:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_auto_20190109_1238'),
        ('study_programs', '0001_initial'),
    ]

    state_operations = [
        migrations.AddField('User', 'areas_of_study',
                            models.ManyToManyField(blank=True,
                                                   to='study_programs.AreaOfStudy',
                                                   verbose_name='StudentInfo|Areas of study')),
    ]

    operations = [
      migrations.SeparateDatabaseAndState(
        state_operations=state_operations)
    ]
