# Generated by Django 2.2.9 on 2020-03-04 16:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0029_auto_20200205_2051'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployerAlias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('preferred', models.BooleanField(default=False)),
                ('employer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aliases', to='payroll.Employer')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
