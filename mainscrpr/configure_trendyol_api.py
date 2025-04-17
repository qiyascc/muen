"""
Configure Trendyol API with correct values.

This script updates the API configuration with correct values,
including endpoints and required fields.

Run this script with: python manage.py shell < configure_trendyol_api.py
"""

import os
import sys
import django
import json

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol_app.models import TrendyolAPIConfig

def update_api_config():
    """Update API configuration with correct values"""
    try:
        # Get active config
        config = TrendyolAPIConfig.objects.first()  # Get the first config
        if not config:
            print("No API configuration found!")
            return
        
        print(f"Found API Config (ID: {config.id})")
        print(f"Current Seller ID: {config.seller_id}")
        
        # Update basic info 
        config.supplier_id = config.seller_id  # Set supplier_id = seller_id
        
        # Update API endpoints
        config.products_endpoint = "product/sellers/{sellerId}/products"
        config.product_detail_endpoint = "product/sellers/{sellerId}/products"
        config.brands_endpoint = "brands"
        config.categories_endpoint = "product-categories"
        config.category_attributes_endpoint = "product-categories/{categoryId}/attributes"
        config.batch_status_endpoint = "suppliers/{supplierId}/products/batch-requests/{batchId}"
        
        # API secret ile ilgili bilgi
        print("\nNOT: API Secret değeri için Trendyol Satıcı Paneli'nden API ayarlarınızı kontrol edin.")
        print("Bu betik API Secret değerini otomatik olarak ayarlamaz.")
        print("API Secret değerini admin panelinden güncelleyebilirsiniz.")
        
        # Save changes
        config.save()
        
        print("API configuration updated successfully!")
        print(f"API Config ID: {config.id}")
        print(f"Supplier ID: {config.supplier_id}")
        print(f"Base URL: {config.base_url}")
        print("\nAPI Endpoints:")
        print(f"Products: {config.products_endpoint}")
        print(f"Product Detail: {config.product_detail_endpoint}")
        print(f"Brands: {config.brands_endpoint}")
        print(f"Categories: {config.categories_endpoint}")
        print(f"Category Attributes: {config.category_attributes_endpoint}")
        print(f"Batch Status: {config.batch_status_endpoint}")
        
    except Exception as e:
        print(f"Error updating API configuration: {str(e)}")

if __name__ == "__main__":
    print("=== Configuring Trendyol API ===")
    update_api_config()
    print("=== Configuration Complete ===")