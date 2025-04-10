# Generated by Django 5.2 on 2025-04-10 09:47

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lcwaikiki', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductAvailableUrl',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_id', models.CharField(help_text='Page identifier', max_length=255)),
                ('product_id_in_page', models.CharField(help_text='Product identifier within the page', max_length=255)),
                ('url', models.URLField(help_text='URL to the product', max_length=1000)),
                ('last_checking', models.DateTimeField(default=django.utils.timezone.now, help_text='Date of last check')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Available Product URL',
                'verbose_name_plural': 'Available Product URLs',
                'indexes': [models.Index(fields=['page_id'], name='lcwaikiki_p_page_id_31c1e3_idx'), models.Index(fields=['product_id_in_page'], name='lcwaikiki_p_product_802e4e_idx'), models.Index(fields=['last_checking'], name='lcwaikiki_p_last_ch_0d1a5f_idx'), models.Index(fields=['url'], name='lcwaikiki_p_url_505757_idx')],
            },
        ),
        migrations.CreateModel(
            name='ProductDeletedUrl',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(help_text='URL to the deleted product', max_length=1000)),
                ('last_checking', models.DateTimeField(default=django.utils.timezone.now, help_text='Date of last check')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Deleted Product URL',
                'verbose_name_plural': 'Deleted Product URLs',
                'indexes': [models.Index(fields=['last_checking'], name='lcwaikiki_p_last_ch_1f66b4_idx'), models.Index(fields=['url'], name='lcwaikiki_p_url_e087a3_idx')],
            },
        ),
        migrations.CreateModel(
            name='ProductNewUrl',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(help_text='URL to the new product', max_length=1000)),
                ('last_checking', models.DateTimeField(default=django.utils.timezone.now, help_text='Date of last check')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'New Product URL',
                'verbose_name_plural': 'New Product URLs',
                'indexes': [models.Index(fields=['last_checking'], name='lcwaikiki_p_last_ch_00ebe6_idx'), models.Index(fields=['url'], name='lcwaikiki_p_url_c90706_idx')],
            },
        ),
    ]
