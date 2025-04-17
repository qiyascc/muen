"""
Script to test and fix the Trendyol API endpoints.

This script tests creating a product with the updated endpoint format
and also verifies that the API configuration is correct.

Run this script with: python manage.py shell < fix_api_endpoints.py
"""

import os
import sys
import django
import logging
import json
import requests
from urllib.parse import urljoin

# Django ortamını yükle
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Modelleri içe aktar
from trendyol_app.models import TrendyolAPIConfig

# Logging ayarları
# Force root logger to show logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix_endpoints")
logger.setLevel(logging.DEBUG)
# Add console handler
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

def print_endpoint_test(api_client, endpoint_name, endpoint_path):
    """Test and print an endpoint's full URL"""
    base_url = api_client.base_url
    full_url = urljoin(base_url, endpoint_path.format(sellerId=api_client.supplier_id))
    logger.info(f"Testing {endpoint_name} endpoint: {full_url}")
    return full_url

def test_create_product_endpoint(api_client):
    """Test the create product endpoint specifically"""
    # Eski URL formatı: /supplier/product-service/v2/products
    # Yeni URL formatı: /product/sellers/{sellerId}/products
    
    old_endpoint = "supplier/product-service/v2/products"
    new_endpoint = "product/sellers/{sellerId}/products"
    
    old_url = urljoin(api_client.base_url, old_endpoint)
    new_url = urljoin(api_client.base_url, new_endpoint.format(sellerId=api_client.supplier_id))
    
    logger.info(f"Old product creation endpoint: {old_url}")
    logger.info(f"New product creation endpoint: {new_url}")
    
    # Test new endpoint with a simple request
    headers = api_client.get_auth_headers()
    test_data = {"items": [{"barcode": "TEST123", "title": "Test Product"}]}
    
    try:
        # Don't actually send the request, just prepare it
        req = requests.Request('POST', new_url, headers=headers, json=test_data)
        prepped = req.prepare()
        
        logger.info(f"Request would be sent to: {prepped.url}")
        logger.info(f"With headers: {json.dumps(dict(prepped.headers), indent=2)}")
        logger.info(f"With body: {prepped.body.decode('utf-8')}")
        
        return new_endpoint
    except Exception as e:
        logger.error(f"Error preparing test request: {str(e)}")
        return None

def main():
    """Test and fix Trendyol API endpoints"""
    # Aktif API yapılandırmasını kontrol et
    api_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not api_config:
        logger.error("No active Trendyol API configuration found.")
        return
    
    logger.info(f"Found active API config (ID: {api_config.id})")
    logger.info(f"Current base_url: {api_config.base_url}")
    logger.info(f"Current supplier_id: {api_config.supplier_id}")
    
    # The old products endpoint was api_config.products_endpoint
    logger.info(f"Current products_endpoint: {api_config.products_endpoint}")
    
    # Create a simple API client with the configuration
    class SimpleAPIClient:
        def __init__(self, config):
            self.base_url = config.base_url
            self.supplier_id = config.supplier_id
            self.api_key = config.api_key
            self.api_secret = config.api_secret
        
        def get_auth_headers(self):
            import base64
            auth_token = base64.b64encode(
                f"{self.api_key}:{self.api_secret}".encode()
            ).decode()
            
            return {
                "Authorization": f"Basic {auth_token}",
                "User-Agent": "Trendyol API Client",
                "Content-Type": "application/json"
            }
    
    api_client = SimpleAPIClient(api_config)
    
    # Check current endpoints
    logger.info("Checking current API endpoints...")
    
    # Test old and new product creation endpoints
    new_endpoint = test_create_product_endpoint(api_client)
    
    if new_endpoint:
        logger.info(f"Updating products_endpoint to: {new_endpoint}")
        
        # Update the API configuration
        api_config.products_endpoint = new_endpoint
        api_config.save()
        
        logger.info("API configuration updated successfully.")
    else:
        logger.error("Could not determine the correct products endpoint.")

if __name__ == "__main__":
    main()