# Generated by Django 5.2 on 2025-04-17 15:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trendyol_app', '0002_trendyolapiconfig_api_secret_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trendyolapiconfig',
            name='batch_status_endpoint',
            field=models.CharField(default='product/sellers/{sellerId}/products/batch-requests/{batchRequestId}', max_length=255, verbose_name='Batch Durum Endpoint'),
        ),
    ]
