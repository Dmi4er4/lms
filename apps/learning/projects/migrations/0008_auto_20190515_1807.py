# Generated by Django 2.2.1 on 2019-05-15 18:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0009_auto_20190515_1758'),
        ('projects', '0007_auto_20190426_1339'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='branch',
            field=models.ForeignKey(default='spb', on_delete=django.db.models.deletion.CASCADE, related_name='+', to='learning.Branch', to_field='code', verbose_name='Branch'),
        ),
        migrations.AlterField(
            model_name='reportingperiod',
            name='score_excellent',
            field=models.SmallIntegerField(blank=True, help_text='Projects with final score >= this value will be graded as Excellent', null=True, verbose_name='Min score for EXCELLENT'),
        ),
        migrations.AlterField(
            model_name='reportingperiod',
            name='score_good',
            field=models.SmallIntegerField(blank=True, help_text='Projects with final score in [GOOD; EXCELLENT) will be graded as Good.', null=True, verbose_name='Min score for GOOD'),
        ),
        migrations.AlterField(
            model_name='reportingperiod',
            name='score_pass',
            field=models.SmallIntegerField(blank=True, help_text='Projects with final score in [PASS; GOOD) will be graded as Pass, with score < PASS as Unsatisfactory.', null=True, verbose_name='Min score for PASS'),
        ),
    ]