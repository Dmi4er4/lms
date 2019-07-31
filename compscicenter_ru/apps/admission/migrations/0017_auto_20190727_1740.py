# Generated by Django 2.2.3 on 2019-07-27 17:40

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0019_remove_enrollmentinvitation_expire_at'),
        ('admission', '0016_campaign_template_interview_reminder'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='branch_new',
            field=models.ForeignKey(default='spb', on_delete=django.db.models.deletion.PROTECT, related_name='campaigns_new', to='learning.Branch', to_field='code', verbose_name='Branch'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='applicant',
            name='status',
            field=models.CharField(blank=True, choices=[('rejected_test', 'Rejected by test'), ('permit_to_exam', 'Permitted to the exam'), ('rejected_exam', 'Rejected by exam'), ('rejected_cheating', 'Cheating'), ('pending', 'Pending'), ('interview_phase', 'Can be interviewed'), ('interview_assigned', 'Interview assigned'), ('interview_completed', 'Interview completed'), ('rejected_interview', 'Rejected by interview'), ('accept_paid', 'Accept on paid'), ('waiting_for_payment', 'Waiting for Payment'), ('accept', 'Accept'), ('accept_if', 'Accept with condition'), ('volunteer', 'Applicant|Volunteer'), ('they_refused', 'He or she refused')], max_length=20, null=True, verbose_name='Applicant|Status'),
        ),
        migrations.AlterField(
            model_name='interview',
            name='interviewers',
            field=models.ManyToManyField(limit_choices_to={'group__role': 7}, to=settings.AUTH_USER_MODEL, verbose_name='Interview|Interviewers'),
        ),
        migrations.AlterField(
            model_name='interviewstream',
            name='interviewers',
            field=models.ManyToManyField(limit_choices_to={'group__role': 7}, to=settings.AUTH_USER_MODEL, verbose_name='Interview|Interviewers'),
        ),
    ]