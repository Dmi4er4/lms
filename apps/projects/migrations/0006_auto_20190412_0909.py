# Generated by Django 2.1.8 on 2019-04-12 09:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0005_auto_20190410_1407'),
    ]

    operations = [
        migrations.CreateModel(
            name='Supervisor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255, verbose_name='Full Name')),
                ('workplace', models.CharField(blank=True, max_length=200, verbose_name='Workplace')),
                ('gender', models.CharField(choices=[('M', 'Male'), ('F', 'Female')], max_length=1, verbose_name='Gender')),
            ],
        ),
        migrations.AddField(
            model_name='project',
            name='supervisors',
            field=models.ManyToManyField(related_name='projects', to='projects.Supervisor', verbose_name='Supervisors'),
        ),
    ]