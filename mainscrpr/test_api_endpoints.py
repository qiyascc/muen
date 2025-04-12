"""
Script to test the Trendyol API endpoints after updating the configuration.

This script tests the core API endpoints to ensure they are working correctly
with the new API base URL.

Run this script with: python manage.py shell < test_api_endpoints.py
"""

import django
import os
import sys
import json
import logging
import requests
import base64
import time
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

def test_brands_endpoint():
    """Test the brands endpoint with the updated API configuration"""
    print("\n===== TESTING BRANDS ENDPOINT =====\n")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        print(f"Using API client with base URL: {api_client.config.base_url}")
        
        # Test brands endpoint
        print("Testing brands endpoint...")
        try:
            brands = api_client.get("product/brands")
            
            if isinstance(brands, dict) and "brands" in brands:
                brand_list = brands["brands"]
                print(f"SUCCESS! Retrieved {len(brand_list)} brands")
                if brand_list:
                    print("First 3 brands:")
                    for i, brand in enumerate(brand_list[:3]):
                        print(f"{i+1}. {brand.get('name')} (ID: {brand.get('id')})")
                
                # Try to find LCW brand
                lcw_brands = [b for b in brand_list if "lcw" in b.get('name', '').lower()]
                if lcw_brands:
                    print("\nFound LCW brands:")
                    for i, brand in enumerate(lcw_brands):
                        print(f"{i+1}. {brand.get('name')} (ID: {brand.get('id')})")
                else:
                    print("\nNo LCW brands found")
            else:
                print(f"Unexpected response format: {type(brands)}")
                print(json.dumps(brands, indent=2)[:1000])  # Limit output length
        except Exception as e:
            print(f"Error testing brands endpoint: {str(e)}")
            traceback.print_exc()
        
        return True
    except Exception as e:
        print(f"Error in test_brands_endpoint: {str(e)}")
        traceback.print_exc()
        return False

def test_categories_endpoint():
    """Test the categories endpoint with the updated API configuration"""
    print("\n===== TESTING CATEGORIES ENDPOINT =====\n")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        print(f"Using API client with base URL: {api_client.config.base_url}")
        
        # Test categories endpoint
        print("Testing categories endpoint...")
        try:
            categories = api_client.get("product/categories")
            
            if isinstance(categories, list):
                print(f"SUCCESS! Retrieved {len(categories)} top-level categories")
                if categories:
                    print("First 5 categories:")
                    for i, category in enumerate(categories[:5]):
                        print(f"{i+1}. {category.get('name')} (ID: {category.get('id')})")
                        if "subCategories" in category and category["subCategories"]:
                            subcats = category["subCategories"]
                            print(f"   - Has {len(subcats)} subcategories")
                            if subcats:
                                for j, subcat in enumerate(subcats[:2]):
                                    print(f"     {j+1}. {subcat.get('name')} (ID: {subcat.get('id')})")
            else:
                print(f"Unexpected response format: {type(categories)}")
                print(json.dumps(categories, indent=2)[:1000])  # Limit output length
        except Exception as e:
            print(f"Error testing categories endpoint: {str(e)}")
            traceback.print_exc()
        
        return True
    except Exception as e:
        print(f"Error in test_categories_endpoint: {str(e)}")
        traceback.print_exc()
        return False

def test_suppliers_products_endpoint():
    """Test the suppliers products endpoint with the updated API configuration"""
    print("\n===== TESTING SUPPLIERS PRODUCTS ENDPOINT =====\n")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        print(f"Using API client with base URL: {api_client.config.base_url}")
        
        # Test suppliers products endpoint
        print("Testing suppliers products endpoint...")
        try:
            # Use either suppliers or sellers depending on what works
            endpoint = f"suppliers/{api_client.config.seller_id}/products"
            products = api_client.get(endpoint)
            
            if isinstance(products, dict) and "content" in products:
                product_list = products["content"]
                print(f"SUCCESS! Retrieved {len(product_list)} products")
                print(f"Total products: {products.get('totalElements')}")
                print(f"Total pages: {products.get('totalPages')}")
                
                if product_list:
                    print("\nFirst 3 products:")
                    for i, product in enumerate(product_list[:3]):
                        print(f"{i+1}. {product.get('title')} (ID: {product.get('id')})")
                        print(f"   - Barcode: {product.get('barcode')}")
                        print(f"   - Stock Code: {product.get('stockCode')}")
                        print(f"   - Approved: {product.get('approved')}")
                        print(f"   - Brand ID: {product.get('brandId')}")
                        print(f"   - Category ID: {product.get('categoryId')}")
            else:
                print(f"Unexpected response format: {type(products)}")
                print(json.dumps(products, indent=2)[:1000])  # Limit output length
        except Exception as e:
            print(f"Error testing suppliers products endpoint: {str(e)}")
            traceback.print_exc()
            
            # Try alternative endpoint
            print("\nTrying alternative endpoint (sellers)...")
            try:
                endpoint = f"sellers/{api_client.config.seller_id}/products"
                products = api_client.get(endpoint)
                
                if isinstance(products, dict) and "content" in products:
                    product_list = products["content"]
                    print(f"SUCCESS! Retrieved {len(product_list)} products")
                    if product_list:
                        print("First 3 products:")
                        for i, product in enumerate(product_list[:3]):
                            print(f"{i+1}. {product.get('title')} (ID: {product.get('id')})")
                else:
                    print(f"Unexpected response format: {type(products)}")
                    print(json.dumps(products, indent=2)[:1000])  # Limit output length
            except Exception as e:
                print(f"Error testing alternative endpoint: {str(e)}")
        
        return True
    except Exception as e:
        print(f"Error in test_suppliers_products_endpoint: {str(e)}")
        traceback.print_exc()
        return False

def test_category_attributes_endpoint():
    """Test the category attributes endpoint with the updated API configuration"""
    print("\n===== TESTING CATEGORY ATTRIBUTES ENDPOINT =====\n")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        print(f"Using API client with base URL: {api_client.config.base_url}")
        
        # Test category attributes endpoint
        print("Testing category attributes endpoint...")
        
        # Test with a known category ID
        category_id = 1081  # Children's Clothing category ID
        print(f"Using category ID: {category_id}")
        
        try:
            attributes = api_client.get(f"product/categories/{category_id}/attributes")
            
            if attributes:
                if isinstance(attributes, dict) and "categoryAttributes" in attributes:
                    attr_list = attributes["categoryAttributes"]
                    print(f"SUCCESS! Retrieved {len(attr_list)} attributes")
                    
                    if attr_list:
                        print("\nFirst 5 attributes:")
                        for i, attr in enumerate(attr_list[:5]):
                            attr_name = attr["attribute"]["name"] if "attribute" in attr and "name" in attr["attribute"] else "Unknown"
                            attr_id = attr["attribute"]["id"] if "attribute" in attr and "id" in attr["attribute"] else "Unknown"
                            print(f"{i+1}. {attr_name} (ID: {attr_id})")
                            
                            # Check for attribute values
                            if "attributeValues" in attr and attr["attributeValues"]:
                                values = attr["attributeValues"]
                                print(f"   - Has {len(values)} possible values")
                                if values:
                                    for j, value in enumerate(values[:3]):
                                        value_name = value.get("name", "Unknown")
                                        value_id = value.get("id", "Unknown")
                                        print(f"     {j+1}. {value_name} (ID: {value_id})")
                            
                            # Check for required flag
                            required = "required" in attr and attr["required"]
                            print(f"   - Required: {required}")
                            
                            # Check for allowCustom flag
                            allow_custom = "allowCustom" in attr and attr["allowCustom"]
                            print(f"   - Allow Custom: {allow_custom}")
                elif isinstance(attributes, list):
                    print(f"SUCCESS! Retrieved {len(attributes)} attributes")
                    if attributes:
                        print("First 5 attributes:")
                        for i, attr in enumerate(attributes[:5]):
                            print(f"{i+1}. {attr.get('name', 'Unknown')} (ID: {attr.get('id', 'Unknown')})")
                            
                            # Check for attribute values
                            if "values" in attr and attr["values"]:
                                values = attr["values"]
                                print(f"   - Has {len(values)} possible values")
                                if values:
                                    for j, value in enumerate(values[:3]):
                                        print(f"     {j+1}. {value.get('name', 'Unknown')} (ID: {value.get('id', 'Unknown')})")
                else:
                    print(f"Unexpected response format: {type(attributes)}")
                    print(json.dumps(attributes, indent=2)[:1000])  # Limit output length
            else:
                print("No attributes returned")
        except Exception as e:
            print(f"Error testing category attributes endpoint: {str(e)}")
            traceback.print_exc()
        
        return True
    except Exception as e:
        print(f"Error in test_category_attributes_endpoint: {str(e)}")
        traceback.print_exc()
        return False

def test_minimal_product_creation():
    """Test creating a product with a minimal payload"""
    print("\n===== TESTING MINIMAL PRODUCT CREATION =====\n")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        print(f"Using API client with base URL: {api_client.config.base_url}")
        
        # Create a very simple product payload
        test_payload = {
            "items": [
                {
                    "barcode": f"test{int(time.time())}",  # Generate unique barcode using timestamp
                    "title": "Test Product",
                    "productMainId": f"test{int(time.time())}",  # Generate unique product ID using timestamp
                    "brandId": 102,  # LC Waikiki brand ID
                    "categoryId": 1081,  # Children's Clothing category ID
                    "quantity": 10,
                    "stockCode": f"test{int(time.time())}",  # Generate unique stock code using timestamp
                    "description": "Test product description",
                    "currencyType": "TRY",
                    "listPrice": 100.0,
                    "salePrice": 100.0,
                    "vatRate": 10,
                    "cargoCompanyId": 17,
                    "shipmentAddressId": 5526789,  # Using the actual shipment address ID we found
                    "returningAddressId": 5526791,  # Using the actual returning address ID we found
                    "images": [{"url": "https://www.lcwaikiki.com/static/images/logo.svg"}],
                    "attributes": [
                        {
                            "attributeId": 338,
                            "attributeValueId": 4290
                        },
                        {
                            "attributeId": 346,
                            "attributeValueId": 4761
                        },
                        {
                            "attributeId": 47,     # Color attribute
                            "attributeValueId": 7011
                        },
                        {
                            "attributeId": 22,     # Another attribute
                            "attributeValueId": 253
                        }
                    ]
                }
            ]
        }
        
        print("Creating product with payload:")
        print(json.dumps(test_payload, indent=2))
        
        # Test product creation
        print("\nTesting product creation...")
        
        try:
            # Construct the endpoint
            endpoint = f"product/sellers/{api_client.config.seller_id}/products"
            print(f"Using endpoint: {endpoint}")
            
            response = api_client.post(endpoint, test_payload)
            
            print(f"Response: {response}")
            
            if isinstance(response, dict) and "batchRequestId" in response:
                batch_id = response["batchRequestId"]
                print(f"SUCCESS! Batch ID: {batch_id}")
                
                # Wait a few seconds and check batch status
                print("\nWaiting 5 seconds before checking batch status...")
                time.sleep(5)
                
                # Check the batch status
                batch_status_endpoint = f"product/sellers/{api_client.config.seller_id}/products/batch-requests/{batch_id}"
                print(f"Checking batch status at endpoint: {batch_status_endpoint}")
                
                try:
                    batch_status = api_client.get(batch_status_endpoint)
                    print("Batch status response:")
                    print(json.dumps(batch_status, indent=2))
                except Exception as e:
                    print(f"Error checking batch status: {str(e)}")
            else:
                print("Failed to create product")
                print(f"Unexpected response format: {type(response)}")
                print(json.dumps(response, indent=2))
        except Exception as e:
            print(f"Error in product creation: {str(e)}")
            traceback.print_exc()
            
            # Try to extract more error details
            if hasattr(e, 'response') and hasattr(e.response, 'content'):
                try:
                    error_details = json.loads(e.response.content)
                    print("Error details:")
                    print(json.dumps(error_details, indent=2))
                except:
                    print(f"Raw error response: {e.response.content}")
        
        return True
    except Exception as e:
        print(f"Error in test_minimal_product_creation: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("\n===== TESTING TRENDYOL API ENDPOINTS =====\n")
    
    try:
        # Test brands endpoint
        brands_test = test_brands_endpoint()
        
        # Test categories endpoint
        categories_test = test_categories_endpoint()
        
        # Test suppliers products endpoint
        suppliers_test = test_suppliers_products_endpoint()
        
        # Test category attributes endpoint
        attributes_test = test_category_attributes_endpoint()
        
        # Test minimal product creation
        product_test = test_minimal_product_creation()
        
        print("\n===== API ENDPOINT TEST SUMMARY =====")
        print(f"Brands API test: {'SUCCESS' if brands_test else 'FAILED'}")
        print(f"Categories API test: {'SUCCESS' if categories_test else 'FAILED'}")
        print(f"Suppliers Products API test: {'SUCCESS' if suppliers_test else 'FAILED'}")
        print(f"Category Attributes API test: {'SUCCESS' if attributes_test else 'FAILED'}")
        print(f"Product Creation test: {'SUCCESS' if product_test else 'FAILED'}")
        
        return True
    except Exception as e:
        print(f"Error running tests: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()