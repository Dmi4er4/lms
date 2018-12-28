# Generated by Django 2.1.3 on 2018-12-27 16:10

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sites', '0002_alter_domain_unique'),
        ('learning', '0004_auto_20181227_1603'),
    ]

    state_operations = [
        migrations.CreateModel(
            name='Internship',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('question', models.CharField(max_length=255, verbose_name='Question')),
                ('answer', models.TextField(verbose_name='Answer')),
                ('sort', models.SmallIntegerField(blank=True, null=True, verbose_name='Sort order')),
            ],
            options={
                'verbose_name': 'Internship',
                'verbose_name_plural': 'Internships',
                'db_table': 'internships',
                'ordering': ['sort'],
            },
        ),
        migrations.CreateModel(
            name='InternshipCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Category name')),
                ('sort', models.SmallIntegerField(blank=True, null=True, verbose_name='Sort order')),
                ('site', models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='sites.Site', verbose_name='Site')),
            ],
            options={
                'verbose_name': 'Internship Сategory',
                'verbose_name_plural': 'Internship Сategories',
                'db_table': 'internships_categories',
                'ordering': ['sort'],
            },
        ),
        migrations.AddField(
            model_name='internship',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='internships.InternshipCategory', verbose_name='Internship category'),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]