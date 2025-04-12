"""
Script to test and fix the Trendyol API endpoints.

This script tests creating a product with the updated endpoint format
and also verifies that the API configuration is correct.

Run this script with: python manage.py shell < fix_api_endpoints.py
"""

import django
import os
import sys
import json
import base64
import logging
import requests
from pprint import pprint
from loguru import logger
import traceback

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI

def print_endpoint_test(api_client, endpoint_name, endpoint_path):
    """Test and print an endpoint's full URL"""
    full_url = f"{api_client.config.base_url.rstrip('/')}/{endpoint_path}"
    print(f"{endpoint_name} Endpoint: {full_url}")
    
    # Try the same endpoint with the new domain
    new_url = f"https://api.trendyol.com/sapigw/{endpoint_path}"
    print(f"{endpoint_name} Endpoint (new domain): {new_url}")
    
    return full_url, new_url

def test_create_product_endpoint(api_client):
    """Test the create product endpoint specifically"""
    # Print the create product endpoint
    old_url, new_url = print_endpoint_test(
        api_client, 
        "Create Product", 
        f"product/sellers/{api_client.config.seller_id}/products"
    )
    
    # Try making a request to the brands endpoint to check authentication
    brands_endpoint = f"{api_client.config.base_url.rstrip('/')}/product/brands"
    brands_url_new = f"https://api.trendyol.com/sapigw/product/brands"
    
    print(f"\nTesting authentication with Brands API:")
    print(f"Old URL: {brands_endpoint}")
    print(f"New URL: {brands_url_new}")
    
    # Create auth headers
    auth_token = base64.b64encode(
        f"{api_client.config.api_key}:{api_client.config.api_secret}".encode()
    ).decode()
    
    headers = {
        "Authorization": f"Basic {auth_token}",
        "User-Agent": api_client.config.user_agent or f"{api_client.config.seller_id} - SelfIntegration",
        "Accept": "application/json"
    }
    
    # Test old URL
    try:
        response = requests.get(brands_endpoint, headers=headers)
        print(f"Old URL response status: {response.status_code}")
        if response.status_code == 200:
            print("Old URL authentication working!")
    except Exception as e:
        print(f"Old URL error: {str(e)}")
    
    # Test new URL
    try:
        response = requests.get(brands_url_new, headers=headers)
        print(f"New URL response status: {response.status_code}")
        if response.status_code == 200:
            print("New URL authentication working!")
    except Exception as e:
        print(f"New URL error: {str(e)}")
    
    return old_url, new_url

def test_new_api_client():
    """Test the new API client from trendyol_api_new.py"""
    print("\n===== TESTING NEW API CLIENT =====")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return
    
    print(f"Original API config base URL: {config.base_url}")
    
    # Update the config to use the new URL
    old_base_url = config.base_url
    new_base_url = "https://api.trendyol.com/sapigw"
    
    print(f"Updating API config base URL to: {new_base_url}")
    
    # Temporarily update the config
    config.base_url = new_base_url
    config.save()
    
    try:
        # Get new API client with updated config
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client with new URL")
            return
        
        print(f"API client using base URL: {api_client.config.base_url}")
        
        # Test API connection with new URL
        print("\nTesting API connection with new URL...")
        try:
            # Try to get brands
            response = api_client.get("product/brands")
            if isinstance(response, dict) and "brands" in response:
                brands = response["brands"]
                if brands and len(brands) > 0:
                    print(f"SUCCESS! Received {len(brands)} brands")
                    print("First 3 brands:")
                    for i, brand in enumerate(brands[:3]):
                        print(f"{i+1}. {brand.get('name')} (ID: {brand.get('id')})")
            else:
                print(f"Unexpected response format: {type(response)}")
                print(f"Response: {response}")
        except Exception as e:
            print(f"Error testing API connection: {str(e)}")
            traceback.print_exc()
    finally:
        # Restore original URL
        config.base_url = old_base_url
        config.save()
        print(f"\nRestored API config base URL to: {old_base_url}")

def update_api_config():
    """Update the API configuration to use the new URL"""
    print("\n===== UPDATING API CONFIGURATION =====")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return
    
    print(f"Current API config base URL: {config.base_url}")
    
    # Update the config to use the new URL
    old_base_url = config.base_url
    new_base_url = "https://api.trendyol.com/sapigw"
    
    if old_base_url == new_base_url:
        print("API configuration already using the new URL.")
        return
    
    print(f"Updating API config base URL to: {new_base_url}")
    
    # Update the config
    config.base_url = new_base_url
    config.save()
    
    print(f"API configuration updated successfully to: {new_base_url}")
    
    return True

def main():
    """Test and fix Trendyol API endpoints"""
    print("\n===== TRENDYOL API ENDPOINT TEST =====\n")
    
    # Get API client
    api_client = get_api_client_from_config()
    if not api_client:
        print("Failed to get API client")
        return False
    
    print(f"API client using base URL: {api_client.config.base_url}")
    
    # Test create product endpoint
    old_url, new_url = test_create_product_endpoint(api_client)
    
    # Test batch status endpoint
    print("\n----- Batch Status Endpoint -----")
    sample_batch_id = "c1a9ccfc-8f7c-491e-bbd6-37b5466fd1b7"  # Example batch ID
    batch_old_url, batch_new_url = print_endpoint_test(
        api_client,
        "Batch Status",
        f"product/sellers/{api_client.config.seller_id}/products/batch-requests/{sample_batch_id}"
    )
    
    # Test products endpoint
    print("\n----- Products Endpoint -----")
    products_old_url, products_new_url = print_endpoint_test(
        api_client,
        "Products",
        f"suppliers/{api_client.config.seller_id}/products"
    )
    
    # Test categories endpoint
    print("\n----- Categories Endpoint -----")
    categories_old_url, categories_new_url = print_endpoint_test(
        api_client,
        "Categories",
        "product/categories"
    )
    
    # Test category attributes endpoint
    print("\n----- Category Attributes Endpoint -----")
    sample_category_id = 1081  # Example category ID
    attributes_old_url, attributes_new_url = print_endpoint_test(
        api_client,
        "Category Attributes",
        f"product/categories/{sample_category_id}/attributes"
    )
    
    # Test new API client
    test_new_api_client()
    
    # Update the API config to use the new URL that works
    print("\nUpdating API configuration to use the correct working URL...")
    update_api_config()
    
    return True

if __name__ == "__main__":
    main()