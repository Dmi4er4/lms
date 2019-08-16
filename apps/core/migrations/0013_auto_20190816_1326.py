# Generated by Django 2.2.4 on 2019-08-16 13:26
from django.conf import settings
from django.db import migrations


def create_branches(apps, schema_editor):
    City = apps.get_model('core', 'City')
    Site = apps.get_model('sites', 'Site')
    # For tests only. Trying to create site_id = 1 and site_id = 2
    Site.objects.get_or_create(domain='compscicenter.ru', name='compscicenter.ru')
    Site.objects.get_or_create(domain='compsciclub.ru', name='compsciclub.ru')
    Branch = apps.get_model('core', 'Branch')
    City.objects.get_or_create(code='nsk', name='Новосибирск', abbr='nsk')
    City.objects.get_or_create(code='kzn', name='Казань', abbr='kzn')
    City.objects.get_or_create(code='spb', name='Санкт-Петербург', abbr='spb')
    Branch.objects.get_or_create(code='nsk', site_id=settings.CLUB_SITE_ID,
                                 name='Новосибирск', city_id='nsk', time_zone='Asia/Novosibirsk')
    Branch.objects.get_or_create(code='kzn', site_id=settings.CLUB_SITE_ID,
                                 name='Казань', city_id='kzn', time_zone='Europe/Moscow')
    Branch.objects.get_or_create(code='spb', site_id=settings.CLUB_SITE_ID,
                                 name='Санкт-Петербург', city_id='spb', time_zone='Europe/Moscow')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_auto_20190814_1538'),
    ]

    operations = [
        migrations.RunPython(create_branches)
    ]
