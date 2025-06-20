# Generated by Django 5.1.6 on 2025-06-09 13:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stockreport', '0003_alter_itemparamdet_options_alter_master1_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='APIConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(help_text='API endpoint URL')),
                ('username', models.CharField(help_text='API username', max_length=100)),
                ('password', models.CharField(help_text='API password', max_length=100)),
                ('is_active', models.BooleanField(default=True, help_text='Only one configuration can be active at a time')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'API Configuration',
                'verbose_name_plural': 'API Configurations',
            },
        ),
    ]
