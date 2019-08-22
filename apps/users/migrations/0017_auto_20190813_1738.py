# Generated by Django 2.2.4 on 2019-08-13 17:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_auto_20190727_1814'),
        ('core', '0006_branch'),
        ('learning', '0023_auto_20190813_1727'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='core.Branch', to_field='code', verbose_name='Branch'),
        ),
    ]