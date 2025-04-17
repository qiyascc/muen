"""
Check Trendyol API config with simple print statements.
"""

import os
import sys
import django
import json
from urllib.parse import urljoin

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol_app.models import TrendyolAPIConfig

# Main function
print("=== Trendyol API Configuration Checker ===")

# Find all API configs
all_configs = TrendyolAPIConfig.objects.all()
print(f"Found {all_configs.count()} API configurations")

# Check active config
active_config = TrendyolAPIConfig.objects.filter(is_active=True).first()

if active_config:
    print("\nActive API Configuration:")
    print(f"ID: {active_config.id}")
    print(f"Name: {active_config.name}")
    print(f"Base URL: {active_config.base_url}")
    print(f"Supplier ID: {active_config.supplier_id}")
    print(f"API Key length: {len(active_config.api_key)}")
    print(f"API Secret length: {len(active_config.api_secret)}")
    
    # Check endpoints
    print("\nEndpoints:")
    print(f"Products: {active_config.products_endpoint}")
    print(f"Product Detail: {active_config.product_detail_endpoint}")
    print(f"Brands: {active_config.brands_endpoint}")
    print(f"Categories: {active_config.categories_endpoint}")
    print(f"Category Attributes: {active_config.category_attributes_endpoint}")
    print(f"Batch Status: {active_config.batch_status_endpoint}")
    
    # Print full URLs
    print("\nFull API URLs:")
    supplier_id = active_config.supplier_id
    base_url = active_config.base_url
    
    # Products URL
    products_url = urljoin(base_url, active_config.products_endpoint.format(sellerId=supplier_id))
    print(f"Products URL: {products_url}")
    
    # Brands URL
    brands_url = urljoin(base_url, active_config.brands_endpoint)
    print(f"Brands URL: {brands_url}")
    
    # Categories URL
    categories_url = urljoin(base_url, active_config.categories_endpoint)
    print(f"Categories URL: {categories_url}")
    
    # Generate authentication header
    import base64
    auth_token = base64.b64encode(
        f"{active_config.api_key}:{active_config.api_secret}".encode()
    ).decode()
    
    print("\nAuthentication:")
    print(f"Auth Header: Basic {auth_token[:10]}...")
else:
    print("\nWARNING: No active API configuration found!")