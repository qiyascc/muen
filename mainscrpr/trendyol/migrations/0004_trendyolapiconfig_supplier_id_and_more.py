# Generated by Django 5.2 on 2025-04-11 20:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trendyol', '0003_trendyolproduct_pim_category_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='trendyolapiconfig',
            name='supplier_id',
            field=models.CharField(blank=True, help_text='Trendyol Supplier ID (usually same as Seller ID)', max_length=100),
        ),
        migrations.AddField(
            model_name='trendyolapiconfig',
            name='user_agent',
            field=models.CharField(blank=True, help_text="User-Agent header for API requests. Format: 'SellerID - SelfIntegration'", max_length=150),
        ),
    ]
