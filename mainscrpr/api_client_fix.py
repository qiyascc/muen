"""
Script to fix the Trendyol API client and debug category attributes.

This script specifically focuses on analyzing why the API client is failing
with 400 Bad Request errors and how to fix the attribute format.

Run this script with: python manage.py shell < api_client_fix.py
"""

import django
import os
import sys
import json
import logging
import inspect
from pprint import pprint
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI, TrendyolProductManager

def fix_trendyol_api_client():
    """
    Check and fix the Trendyol API client configuration
    """
    print("Checking Trendyol API client configuration...")
    
    # Get API configuration
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("ERROR: No active Trendyol API configuration found!")
        return False
    
    print(f"API Config: {config}")
    print(f"- Base URL: {config.base_url}")
    print(f"- Seller ID: {config.seller_id}")
    print(f"- API Key: {config.api_key}")
    print(f"- API Secret: {config.api_secret}")
    print(f"- User Agent: {config.user_agent}")
    
    # Check base URL format
    if not config.base_url.endswith('/'):
        print(f"Fixing base URL to include trailing slash")
        config.base_url = f"{config.base_url}/"
        config.save()
        print(f"Fixed base URL: {config.base_url}")
    
    # Try several base URL formats to determine which one works
    base_urls_to_try = [
        "https://api.trendyol.com/sapigw/",
        "https://apigw.trendyol.com/integration/",
        "https://api.trendyol.com/sapigw/suppliers/",
        "https://apigw.trendyol.com/sapigw/"
    ]
    
    working_urls = []
    
    # Test each base URL
    print("\nTesting different base URL formats...")
    for test_url in base_urls_to_try:
        test_config = TrendyolAPIConfig(
            base_url=test_url,
            seller_id=config.seller_id,
            api_key=config.api_key,
            api_secret=config.api_secret,
            user_agent=config.user_agent
        )
        
        api = TrendyolAPI(test_config)
        try:
            # Try to get brands as a simple test
            print(f"Testing {test_url} with brands API")
            brands = api.get("product/brands")
            if brands and isinstance(brands, list) and len(brands) > 0:
                print(f"✅ {test_url} - SUCCESS! Found {len(brands)} brands")
                working_urls.append(test_url)
            else:
                print(f"❌ {test_url} - Failed (empty response)")
        except Exception as e:
            print(f"❌ {test_url} - Error: {str(e)}")
    
    # If we found working URLs, update the configuration
    if working_urls:
        best_url = working_urls[0]
        if config.base_url != best_url:
            print(f"\nUpdating base URL from {config.base_url} to {best_url}")
            config.base_url = best_url
            config.save()
            print("Configuration updated successfully!")
    else:
        print("\nWARNING: No working base URL found! Please check your API credentials.")
    
    # Test sample product payload for the correct attribute format
    print("\nTesting sample product payload for attribute format...")
    
    # Use a failed product
    test_product = TrendyolProduct.objects.filter(batch_status='failed').first()
    if not test_product:
        test_product = TrendyolProduct.objects.first()
    
    if not test_product:
        print("No products found to test")
        return False
    
    try:
        # Create a product manager with the updated config
        api_client = get_api_client_from_config()
        product_manager = TrendyolProductManager(api_client)
        
        # Find category for the product
        print(f"Finding category for product: {test_product.title}")
        category_id = product_manager.category_finder.find_best_category(test_product.category_name)
        print(f"Category ID: {category_id}")
        
        # Get brand ID
        print(f"Finding brand ID for: {test_product.brand_name}")
        brand_id = product_manager.get_brand_id(test_product.brand_name)
        print(f"Brand ID: {brand_id}")
        
        # Get category attributes 
        print(f"Getting attributes for category {category_id}")
        attributes = product_manager.category_finder._get_sample_attributes(category_id)
        print(f"Retrieved {len(attributes)} attributes")
        
        # Debug attribute format
        print("\nSample attributes from category API:")
        for i, attr in enumerate(attributes[:5]):
            print(f"Attribute {i+1}:")
            for key, value in attr.items():
                print(f"  {key}: {value} (type: {type(value).__name__})")
        
        # Build payload for test product
        print("\nBuilding product payload...")
        payload = product_manager._build_product_payload(test_product, category_id, brand_id, attributes)
        
        # Check payload format
        print("\nSAMPLE PAYLOAD:")
        if 'items' in payload and payload['items'] and isinstance(payload['items'], list):
            item = payload['items'][0]
            
            # Check for 'color' field outside attributes
            if 'color' in item:
                print(f"WARNING: Found 'color' field outside attributes: {item['color']}")
                print("This is likely causing the 400 Bad Request error!")
            
            # Check attribute format
            if 'attributes' in item:
                attrs = item['attributes']
                print(f"Attributes count: {len(attrs)}")
                
                for i, attr in enumerate(attrs[:5]):
                    print(f"\nAttribute {i+1}:")
                    for key, value in attr.items():
                        print(f"  {key}: {value} (type: {type(value).__name__})")
                    
                    # Check for proper format (attributeId and attributeValueId)
                    if 'attributeId' not in attr:
                        print("  ERROR: Missing 'attributeId' field!")
                    elif not isinstance(attr['attributeId'], int):
                        print(f"  ERROR: 'attributeId' is {type(attr['attributeId']).__name__}, should be int!")
                    
                    if 'attributeValueId' not in attr and 'customAttributeValue' not in attr:
                        print("  ERROR: Missing both 'attributeValueId' and 'customAttributeValue' fields!")
                    elif 'attributeValueId' in attr and not isinstance(attr['attributeValueId'], int):
                        print(f"  ERROR: 'attributeValueId' is {type(attr['attributeValueId']).__name__}, should be int!")
            else:
                print("WARNING: No attributes found in payload!")
                
        print("\nPayload structure summary:")
        def summarize_dict(d, prefix=''):
            for key, value in d.items():
                if isinstance(value, dict):
                    print(f"{prefix}{key}: <dict>")
                    summarize_dict(value, prefix + '  ')
                elif isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        print(f"{prefix}{key}: <list of {len(value)} items>")
                        for i, item in enumerate(value[:3]):
                            print(f"{prefix}  [Item {i}]:")
                            summarize_dict(item, prefix + '    ')
                        if len(value) > 3:
                            print(f"{prefix}  ... and {len(value) - 3} more items")
                    else:
                        print(f"{prefix}{key}: {value}")
                else:
                    print(f"{prefix}{key}: {value}")
        
        summarize_dict(payload)
        
        # Test API endpoint for creating products
        print("\nTesting product creation endpoint...")
        try:
            response = api_client.post(f"product/sellers/{api_client.config.seller_id}/products", payload)
            print(f"API Response: {response}")
            print("✅ Success! API endpoint working correctly.")
        except Exception as e:
            print(f"❌ API Error: {str(e)}")
            
            # Try to extract more error details
            if hasattr(e, 'response') and hasattr(e.response, 'content'):
                try:
                    error_details = json.loads(e.response.content)
                    print("Error details:")
                    pprint(error_details)
                except:
                    print(f"Raw error response: {e.response.content}")
        
        return True
    
    except Exception as e:
        print(f"Error testing product payload: {str(e)}")
        traceback.print_exc()
        return False

def examine_category_finder_issues():
    """Examine issues with the category finder"""
    print("\nExamining category finder issues...")
    
    api_client = get_api_client_from_config()
    if not api_client:
        print("Failed to get API client")
        return False
        
    product_manager = TrendyolProductManager(api_client)
    
    # Test with a few common categories
    test_categories = [
        "Bebek Takım",
        "Erkek Bebek Tişört",
        "Erkek T-Shirt",
        "Kadın Bluz",
        "Kız Çocuk Elbise"
    ]
    
    for category_name in test_categories:
        print(f"\nTesting category: {category_name}")
        try:
            category_id = product_manager.category_finder.find_best_category(category_name)
            print(f"Found category ID: {category_id}")
            
            # Get attributes for this category
            try:
                attributes = product_manager.category_finder.get_category_attributes(category_id)
                attr_count = len(attributes.get('categoryAttributes', []))
                print(f"Found {attr_count} attributes for category {category_id}")
                
                # Print some sample attributes
                if 'categoryAttributes' in attributes:
                    sample_attrs = attributes['categoryAttributes'][:3]
                    for i, attr in enumerate(sample_attrs):
                        attr_name = attr.get('attribute', {}).get('name', 'Unknown')
                        is_required = attr.get('required', False)
                        values_count = len(attr.get('attributeValues', []))
                        print(f"  Attr {i+1}: {attr_name} (Required: {is_required}, Values: {values_count})")
            except Exception as e:
                print(f"Error getting attributes: {str(e)}")
                
        except Exception as e:
            print(f"Error finding category: {str(e)}")
    
    # Test getting sample attributes
    print("\nTesting _get_sample_attributes function...")
    # Test with a few known category IDs
    test_category_ids = [1000, 1081, 3300, 944]
    
    for category_id in test_category_ids:
        print(f"\nTesting category ID: {category_id}")
        try:
            sample_attrs = product_manager.category_finder._get_sample_attributes(category_id)
            print(f"Retrieved {len(sample_attrs)} sample attributes")
            
            # Check attribute format
            for i, attr in enumerate(sample_attrs[:3]):
                print(f"  Attribute {i+1}:")
                for key, value in attr.items():
                    print(f"    {key}: {value} (type: {type(value).__name__})")
        except Exception as e:
            print(f"Error getting sample attributes: {str(e)}")
    
    return True

if __name__ == "__main__":
    print("\n===== TRENDYOL API CLIENT DIAGNOSTICS =====\n")
    print("This script will diagnose and fix common issues with the Trendyol API client.\n")
    
    try:
        fix_result = fix_trendyol_api_client()
        if fix_result:
            print("\nSuccessfully diagnosed API client issues.")
        else:
            print("\nFailed to fully diagnose API client issues.")
        
        examine_result = examine_category_finder_issues()
        if examine_result:
            print("\nSuccessfully examined category finder issues.")
        else:
            print("\nFailed to examine category finder issues.")
        
    except Exception as e:
        print(f"Error running diagnostics: {str(e)}")
        traceback.print_exc()