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
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI

def print_endpoint_test(api_client, endpoint_name, endpoint_path):
    """Test and print an endpoint's full URL"""
    # Calculate the full URL 
    url = f"{api_client.api_url}{endpoint_path}"
    
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
    url = f"{api_client.api_url}{endpoint}"
    
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

def test_new_api_client():
    """Test the new API client from trendyol_api_new.py"""
    print("\n\nTesting new TrendyolAPI client:")
    print("===============================")
    
    api_client = get_api_client_from_config()
    
    if not api_client:
        print("Failed to get new API client")
        return
    
    # Test basic GET request with detailed logging
    print("\nTesting category attributes endpoint:")
    try:
        # Test category attributes endpoint
        category_id = 2356  # Test ID
        print(f"Making GET request to product/product-categories/{category_id}/attributes")
        response = api_client.get(f"product/product-categories/{category_id}/attributes")
        print(f"Response received: {type(response)}")
        print(f"Response contains {len(response.get('categoryAttributes', []))} category attributes")
    except Exception as e:
        print(f"Error in new API client test: {str(e)}")

def main():
    """Test and fix Trendyol API endpoints"""
    # Get active API configuration
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    
    if not config:
        print("No active Trendyol API configuration found")
        return
    
    print(f"Testing API configuration: {config.name}")
    print(f"Base URL: {config.base_url}")
    print(f"Supplier ID: {config.supplier_id or config.seller_id}")
    print()
    
    # Initialize API client directly
    api_client = TrendyolApi(
        api_key=config.api_key,
        api_secret=config.api_secret,
        supplier_id=config.supplier_id or config.seller_id,
        api_url=config.base_url,
        user_agent=config.user_agent or f"{config.supplier_id or config.seller_id} - SelfIntegration"
    )
    
    # Also test the new API client
    test_new_api_client()
    
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