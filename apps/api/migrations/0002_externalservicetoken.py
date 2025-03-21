# Generated by Django 3.2.18 on 2024-12-10 13:55

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalServiceToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('service_tag', models.CharField(max_length=100, verbose_name='External service tag')),
                ('access_key', models.CharField(db_index=True, help_text='Plain external service token', max_length=100, verbose_name='External token')),
            ],
            options={
                'verbose_name': 'External token',
                'verbose_name_plural': 'External tokens',
            },
        ),
    ]
