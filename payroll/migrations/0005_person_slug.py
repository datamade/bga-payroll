# Generated by Django 2.0.2 on 2018-02-23 17:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0004_person_search_vector'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='slug',
            field=models.SlugField(max_length=255, null=True, unique=True),
        ),
    ]