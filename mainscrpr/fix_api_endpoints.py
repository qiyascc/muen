"""
Script to test and fix the Trendyol API endpoints.

This script tests creating a product with the updated endpoint format
and also verifies that the API configuration is correct.

Run this script with: python manage.py shell < fix_api_endpoints.py
"""

import django
import os
import sys
import requests
import json
import base64
from loguru import logger

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig
from trendyol.api_client import get_api_client, TrendyolApi

def print_endpoint_test(api_client, endpoint_name, endpoint_path):
    """Test and print an endpoint's full URL"""
    # Calculate the full URL 
    url = f"{api_client.base_url}{endpoint_path}"
    
    print(f"Testing endpoint: {endpoint_name}")
    print(f"  Path: {endpoint_path}")
    print(f"  Full URL: {url}")
    print()

def test_create_product_endpoint(api_client):
    """Test the create product endpoint specifically"""
    if not api_client:
        print("No API client available")
        return
    
    endpoint = api_client.products._get_products_endpoint()
    url = f"{api_client.base_url}{endpoint}"
    
    print("\nCreating product test:")
    print(f"  Endpoint path: {endpoint}")
    print(f"  Full URL: {url}")
    
    # Create a minimal test product data to test logging (won't actually send)
    test_data = {
        "items": [{
            "barcode": "TEST_BARCODE_12345",
            "title": "Test Product",
            "productMainId": "TEST_MAIN_123",
            "brandId": 1,
            "categoryId": 1000,
            "listPrice": 100.0,
            "salePrice": 90.0,
            "vatRate": 18,
            "stockCode": "TEST_STOCK_123"
        }]
    }
    
    # Don't actually make the request, just log what would be sent
    print(f"  Request payload: {json.dumps(test_data, indent=2)}")
    
    # Check for duplicate /integration in the URL
    if "/integration/integration" in url:
        print("\n⚠️ Warning: Duplicate '/integration' detected in URL")
        print("  This could cause API errors")
    
    return endpoint, url

def main():
    """Test and fix Trendyol API endpoints"""
    # Get active API configuration
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    
    if not config:
        print("No active Trendyol API configuration found")
        config_count = TrendyolAPIConfig.objects.count()
        if config_count > 0:
            print(f"Found {config_count} inactive configurations")
            for cfg in TrendyolAPIConfig.objects.all():
                print(f"  - {cfg.name} (Active: {cfg.is_active}, URL: {cfg.base_url})")
        else:
            print("No API configurations found at all")
        
        # Create a default configuration if none exists
        print("\nCreating a default active configuration...")
        config = TrendyolAPIConfig.objects.create(
            name="Default Configuration",
            seller_id="535623",
            api_key="qSohKkLKPWwDeSKjwz8R",
            api_secret="yYF3Ycl9B6Vjs77q3MhE",
            base_url="https://apigw.trendyol.com",
            user_agent="535623 - SelfIntegration",
            supplier_id="535623",
            is_active=True
        )
        print(f"Created configuration: {config.name}")
    
    print(f"Testing API configuration: {config.name}")
    print(f"Base URL: {config.base_url}")
    print(f"Supplier ID: {config.supplier_id or config.seller_id}")
    print()
    
    # Initialize API client directly
    api_client = TrendyolApi(
        api_key=config.api_key,
        api_secret=config.api_secret,
        supplier_id=config.supplier_id or config.seller_id,
        base_url=config.base_url,
        user_agent=config.user_agent or f"{config.supplier_id or config.seller_id} - SelfIntegration"
    )
    
    # Test all the endpoints
    print("Testing all endpoints:")
    print("=====================")
    
    # Test Brands API endpoints
    print_endpoint_test(api_client, "Brands List", api_client.brands._get_brands_endpoint())
    
    # Test Categories API endpoints
    print_endpoint_test(api_client, "Categories List", api_client.categories._get_categories_endpoint())
    
    # Test for specific category attributes
    cat_attr_endpoint = api_client.categories._get_category_attributes_endpoint(1000)
    print_endpoint_test(api_client, "Category Attributes", cat_attr_endpoint)
    
    # Test Products API endpoints
    print_endpoint_test(api_client, "Products List", api_client.products._get_products_endpoint())
    batch_endpoint = api_client.products._get_batch_request_endpoint("test-batch-id")
    print_endpoint_test(api_client, "Batch Request Status", batch_endpoint)
    
    # Test Inventory API endpoints
    print_endpoint_test(api_client, "Price & Inventory Update", api_client.inventory._get_price_inventory_endpoint())
    
    # Test create product specifically
    test_create_product_endpoint(api_client)

if __name__ == "__main__":
    main()