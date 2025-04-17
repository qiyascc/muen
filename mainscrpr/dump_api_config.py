"""
Dump all fields from TrendyolAPIConfig to diagnose the issue.
"""

import os
import sys
import django

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol_app.models import TrendyolAPIConfig

# Get active config
config = TrendyolAPIConfig.objects.filter(is_active=True).first()
if not config:
    print("No active config found!")
    sys.exit(1)

# Print all fields
print(f"API Config ID: {config.id}")
print(f"API Config fields:")

# Print all fields
for field in config._meta.get_fields():
    field_name = field.name
    try:
        value = getattr(config, field_name)
        print(f"  - {field_name}: {value}")
    except Exception as e:
        print(f"  - {field_name}: [Error: {str(e)}]")

# Print endpoint fields specifically
print("\nEndpoint Fields:")
if hasattr(config, 'products_endpoint'):
    print(f"  - products_endpoint: {config.products_endpoint}")
if hasattr(config, 'product_detail_endpoint'):
    print(f"  - product_detail_endpoint: {config.product_detail_endpoint}")
if hasattr(config, 'brands_endpoint'):
    print(f"  - brands_endpoint: {config.brands_endpoint}")
if hasattr(config, 'categories_endpoint'):
    print(f"  - categories_endpoint: {config.categories_endpoint}")
if hasattr(config, 'category_attributes_endpoint'):
    print(f"  - category_attributes_endpoint: {config.category_attributes_endpoint}")
if hasattr(config, 'batch_status_endpoint'):
    print(f"  - batch_status_endpoint: {config.batch_status_endpoint}")

# Print directly to test if it's been updated
from urllib.parse import urljoin
if hasattr(config, 'base_url') and hasattr(config, 'products_endpoint'):
    try:
        print("\nFull products URL:")
        base_url = config.base_url
        supplier_id = config.supplier_id
        products_endpoint = config.products_endpoint
        full_url = urljoin(base_url, products_endpoint.format(sellerId=supplier_id))
        print(f"  - {full_url}")
    except Exception as e:
        print(f"  - Error constructing URL: {str(e)}")