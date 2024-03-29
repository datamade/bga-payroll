# Generated by Django 2.0.2 on 2019-04-09 20:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0025_rename_education_taxonomy'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='person',
            name='search_vector',
        ),
        migrations.AddField(
            model_name='person',
            name='noindex',
            field=models.BooleanField(default=False),
        ),
        # The migration adding the search_vector field also defines a
        # trigger to populate it from the first and last name. Remove that
        # trigger.
        migrations.RunSQL('''
            DROP TRIGGER IF EXISTS person_tsvectorupdate ON payroll_person
        ''')
    ]
