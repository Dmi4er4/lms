# Generated by Django 2.2.4 on 2019-08-06 15:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0021_auto_20190730_1601'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='branch',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='learning.Branch', to_field='code', verbose_name='Branch'),
            preserve_default=False,
        ),
    ]