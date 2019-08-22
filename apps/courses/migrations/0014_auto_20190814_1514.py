# Generated by Django 2.2.4 on 2019-08-14 15:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0013_auto_20190814_1513'),
        ('core', '0011_venue'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courseclass',
            name='venue',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.Venue', verbose_name='CourseClass|Venue'),
        ),
    ]
