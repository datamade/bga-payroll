# Generated by Django 2.0.2 on 2018-04-09 20:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0008_add_vintage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='salary',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
    ]
