# Generated by Django 2.0.2 on 2018-05-30 16:53

from django.core.management import call_command
from django.db import connection, migrations, models
import django.db.models.deletion


def insert_raw_taxonomy(*args):
    call_command('import_metadata', endpoints='taxonomy')


def delete_raw_taxonomy(*args):
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE raw_taxonomy')


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0011_unique_index_redux'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployerTaxonomy',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_type', models.CharField(max_length=255)),
                ('chicago', models.BooleanField()),
                ('cook_or_collar', models.BooleanField()),
            ],
        ),
        migrations.AddField(
            model_name='employer',
            name='taxonomy',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employers', to='payroll.EmployerTaxonomy'),
        ),
        migrations.RunPython(insert_raw_taxonomy, delete_raw_taxonomy),
        migrations.RunSQL('''
            INSERT INTO payroll_employertaxonomy (entity_type, chicago, cook_or_collar)
              SELECT DISTINCT ON (entity_type, chicago, cook_or_collar)
                entity_type,
                chicago,
                cook_or_collar
              FROM raw_taxonomy
              /* Add a school district taxonomy. */
              UNION
              SELECT
                'School District' AS entity_type,
                FALSE AS chicago,
                FALSE AS cook_or_collar
        ''', reverse_sql='DELETE FROM payroll_employertaxonomy'),
    ]
