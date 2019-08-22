# Generated by Django 2.2.4 on 2019-08-21 15:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0031_data_20190821_1501'),
    ]

    operations = [
        migrations.AlterField(
            model_name='learningspace',
            name='description',
            field=models.TextField(blank=True, help_text='How to style text read <a href="/commenting-the-right-way/" target="_blank">here</a>. Partially HTML is enabled too.', verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='learningspace',
            name='location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='learning_spaces', to='core.Location', verbose_name='Location|Name'),
        ),
        migrations.AlterField(
            model_name='learningspace',
            name='name',
            field=models.CharField(blank=True, help_text='Overrides location name', max_length=140, verbose_name='Name'),
        ),
    ]