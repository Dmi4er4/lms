# Generated by Django 3.2.18 on 2025-01-22 10:36

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0049_auto_20241128_1230'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserConsent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('type', models.CharField(choices=[('lms', 'Yandex School of Data Analysis LMS terms of use'), ('offer', 'Offer for the provision of additional professional education services'), ('tickets', 'Buying tickets, making reservations, obtaining permits to visit the countries of arrival')], max_length=100, verbose_name='Consent type')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consents', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'User Consent',
                'verbose_name_plural': 'User Consents',
                'unique_together': {('user', 'type')},
            },
        ),
    ]