# Generated by Django 2.0.2 on 2019-02-13 19:32
#
# In February 2019, the Education taxonomy was renamed to Higher Education.
# Since the import refers to this taxonomy by name, ensure that this change
# is captured in other instances, e.g., staging and test environments.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0024_userzipcode'),
    ]

    operations = [
        migrations.RunSQL('''
            UPDATE payroll_employertaxonomy
            SET entity_type = 'Higher Education'
            WHERE entity_type = 'Education'
        ''', reverse_sql='''
            UPDATE payroll_employertaxonomy
            SET entity_type = 'Education'
            WHERE entity_type = 'Higher Education'
        ''')
    ]