"""
Script to debug Trendyol API request payload.

This script focuses on examining what data is sent to the Trendyol API for creating products.

Run this script with: python manage.py shell < debug_payload.py
"""

import django
import os
import sys
import json
import logging
from pprint import pprint

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI, TrendyolCategoryFinder, TrendyolProductManager

def debug_product_payload(product_id):
    """Debug the product payload for a specific product"""
    print(f"Debugging product payload for product ID: {product_id}")
    
    try:
        # Get product from database
        product = TrendyolProduct.objects.get(id=product_id)
        if not product:
            print(f"Product with ID {product_id} not found")
            return
        
        print(f"Found product: {product.title}")
        
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return
        
        # Prepare payload
        print("Preparing product payload...")
        # Create a product manager
        product_manager = TrendyolProductManager(api_client)
        
        # Find category ID
        category_id = product_manager.category_finder.find_best_category(product.category_name)
        print(f"Found category ID: {category_id}")
        
        # Find brand ID
        brand_id = product_manager.get_brand_id(product.brand_name)
        print(f"Found brand ID: {brand_id}")
        
        # Get attributes
        attributes = product_manager.category_finder._get_sample_attributes(category_id)
        print(f"Found {len(attributes)} attributes for category")
        
        # Build payload
        payload = product_manager._build_product_payload(product, category_id, brand_id, attributes)
        
        # Print formatted payload
        print("\n=== PAYLOAD TO BE SENT TO TRENDYOL API ===")
        pprint(payload)
        print("=========================================\n")
        
        # Analyze attributes specifically
        if 'items' in payload and payload['items'] and isinstance(payload['items'], list):
            item = payload['items'][0]
            
            print("\n=== ATTRIBUTE ANALYSIS ===")
            if 'attributes' in item:
                attributes = item['attributes']
                print(f"Number of attributes: {len(attributes)}")
                
                # Check attribute format
                for i, attr in enumerate(attributes):
                    print(f"\nAttribute {i+1}:")
                    attr_id = attr.get('attributeId')
                    attr_value_id = attr.get('attributeValueId')
                    
                    print(f"  attributeId: {attr_id} (type: {type(attr_id).__name__})")
                    print(f"  attributeValueId: {attr_value_id} (type: {type(attr_value_id).__name__})")
                    
                    # Check for numeric IDs
                    if not isinstance(attr_id, int):
                        print(f"  WARNING: attributeId should be numeric (int), but it's {type(attr_id).__name__}")
                    
                    if not isinstance(attr_value_id, int):
                        print(f"  WARNING: attributeValueId should be numeric (int), but it's {type(attr_value_id).__name__}")
            else:
                print("No attributes found in the payload")
            
            # Check for 'color' outside of attributes
            if 'color' in item:
                print("\nWARNING: 'color' field found outside attributes array. This is incorrect!")
                print(f"color value: {item['color']}")
                
            print("===========================\n")
            
        # Get category attributes for reference
        if 'items' in payload and payload['items'] and isinstance(payload['items'], list):
            item = payload['items'][0]
            if 'categoryId' in item:
                category_id = item['categoryId']
                
                print(f"\nFetching attributes for category ID {category_id} for reference...")
                try:
                    # Get category attributes
                    endpoint = f"product/product-categories/{category_id}/attributes"
                    response = api_client.get(endpoint)
                    
                    if response and 'categoryAttributes' in response:
                        attributes = response.get('categoryAttributes', [])
                        print(f"Found {len(attributes)} attributes for category {category_id}")
                        
                        print("\n=== SAMPLE CORRECT ATTRIBUTE FORMAT ===")
                        sample_attributes = []
                        
                        # Get a few required attributes for demonstration
                        for attr in attributes[:5]:
                            attr_info = attr.get('attribute', {})
                            attr_id = attr_info.get('id')
                            attr_name = attr_info.get('name')
                            
                            if attr.get('attributeValues', []):
                                # For attributes with values, use the first value as an example
                                value = attr.get('attributeValues', [])[0]
                                value_id = value.get('id')
                                value_name = value.get('name')
                                
                                sample_attributes.append({
                                    "attributeId": attr_id,  # This should be a number
                                    "attributeValueId": value_id  # This should be a number
                                })
                        
                        print("Sample attributes using numeric IDs (correct format):")
                        pprint(sample_attributes)
                    else:
                        print(f"No valid category attributes found for category {category_id}")
                
                except Exception as e:
                    print(f"Error fetching category attributes: {str(e)}")
            
    except Exception as e:
        print(f"Error debugging product payload: {str(e)}")

if __name__ == "__main__":
    # Get all products or a specific one
    products = TrendyolProduct.objects.filter(batch_status='failed').order_by('-id')[:5]
    
    if not products:
        print("No failed products found, trying to get any product...")
        products = TrendyolProduct.objects.all().order_by('-id')[:5]
    
    if not products:
        print("No products found to debug")
        sys.exit(1)
    
    for product in products:
        print(f"\n\n----------------------------------------")
        print(f"DEBUGGING PRODUCT: {product.title} (ID: {product.id})")
        print(f"----------------------------------------\n")
        debug_product_payload(product.id)