# Generated by Django 3.2.7 on 2021-10-20 11:08

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import social_django.storage


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConnectedAuthService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified_at', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('provider', models.CharField(max_length=32)),
                ('uid', models.CharField(db_index=True, max_length=255)),
                ('extra_data', models.JSONField(blank=True, default=dict)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_auth', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'auth_connected_service_providers',
            },
            bases=(models.Model, social_django.storage.DjangoUserMixin),
        ),
        migrations.AddConstraint(
            model_name='connectedauthservice',
            constraint=models.UniqueConstraint(fields=('provider', 'uid'), name='unique_uid_per_provider'),
        ),
    ]