"""
Update TrendyolAPIConfig with correct endpoints.

This script updates the TrendyolAPIConfig model with the correct API endpoints
to ensure proper communication with the Trendyol API.

Run this script with: python manage.py shell < update_api_config.py
"""

import os
import sys
import django

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol_app.models import TrendyolAPIConfig

def update_api_config():
    """Update API configuration with correct endpoints"""
    # Get active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("ERROR: No active API configuration found!")
        return False
    
    print(f"Updating API Config (ID: {config.id})...")
    
    # Update endpoints
    # Product operations
    config.products_endpoint = "product/sellers/{sellerId}/products"
    config.product_detail_endpoint = "product/sellers/{sellerId}/products"
    
    # Brand operations
    config.brands_endpoint = "brands"
    
    # Category operations
    config.categories_endpoint = "product-categories"
    config.category_attributes_endpoint = "product-categories/{categoryId}/attributes"
    
    # Batch operations
    config.batch_status_endpoint = "suppliers/{supplierId}/products/batch-requests/{batchId}"
    
    # Update supplier_id field if needed (corrected naming)
    config.supplier_id = config.seller_id
    
    # Save changes
    config.save()
    
    print("API configuration updated successfully!")
    
    return True

def print_config_details():
    """Print configuration details after update"""
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("ERROR: No active API configuration found!")
        return
    
    print("\nUpdated API Configuration:")
    print(f"ID: {config.id}")
    print(f"Supplier ID: {config.supplier_id}")
    print(f"Base URL: {config.base_url}")
    
    # Print endpoints
    print("\nEndpoints:")
    print(f"Products: {config.products_endpoint}")
    print(f"Product Detail: {config.product_detail_endpoint}")
    print(f"Brands: {config.brands_endpoint}")
    print(f"Categories: {config.categories_endpoint}")
    print(f"Category Attributes: {config.category_attributes_endpoint}")
    print(f"Batch Status: {config.batch_status_endpoint}")
    
    # Print full URLs
    from urllib.parse import urljoin
    print("\nFull API URLs:")
    
    base_url = config.base_url
    supplier_id = config.supplier_id
    
    print(f"Products URL: {urljoin(base_url, config.products_endpoint.format(sellerId=supplier_id))}")
    print(f"Brands URL: {urljoin(base_url, config.brands_endpoint)}")
    print(f"Categories URL: {urljoin(base_url, config.categories_endpoint)}")

if __name__ == "__main__":
    print("=== Updating Trendyol API Configuration ===\n")
    
    if update_api_config():
        print_config_details()
    
    print("\n=== Update Complete ===")