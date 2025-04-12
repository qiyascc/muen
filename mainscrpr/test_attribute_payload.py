"""
Script to test Trendyol product creation with a hard-coded payload using properly formatted attributes.

This script creates a product using a minimal payload with correctly formatted attributes
to test if the API accepts the request and provides a valid batch ID.

Run this script with: python manage.py shell < test_attribute_payload.py
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
from trendyol.models import TrendyolAPIConfig, TrendyolProduct, TrendyolBrand
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI, TrendyolProductManager

def test_with_simple_payload():
    """
    Test product creation with a minimal payload that has correctly formatted attributes.
    """
    print("\n===== TESTING PRODUCT CREATION WITH SIMPLE PAYLOAD =====\n")
    
    try:
        # Get API client
        print("Getting API client...")
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        print(f"Using API client with base URL: {api_client.config.base_url}")
        
        # Create a very simple product payload with proper attribute format
        test_payload = {
            "items": [
                {
                    "barcode": "test123456",
                    "title": "Test Product",
                    "productMainId": "test123456",
                    "brandId": 102,  # LC Waikiki brand ID
                    "categoryId": 1081,  # Children's Clothing category ID
                    "quantity": 10,
                    "stockCode": "test123456",
                    "description": "Test product description",
                    "currencyType": "TRY",
                    "listPrice": 100.0,
                    "salePrice": 100.0,
                    "vatRate": 10,
                    "cargoCompanyId": 17,
                    "images": [{"url": "https://cdn.dsmcdn.com/mnresize/1200/1800/ty148/product/media/images/20210818/15/119273414/220496312/1/1_org_zoom.jpg"}],
                    "attributes": [
                        {
                            "attributeId": 338,
                            "attributeValueId": 4290
                        },
                        {
                            "attributeId": 346,
                            "attributeValueId": 4761
                        }
                    ]
                }
            ]
        }
        
        print("Using the following payload:")
        print(json.dumps(test_payload, indent=2))
        
        # Construct the endpoint
        endpoint = f"product/sellers/{api_client.config.seller_id}/products"
        print(f"\nTesting creation with endpoint: {endpoint}")
        
        # Make the request
        print("\nSending request to Trendyol API...")
        try:
            response = api_client.post(endpoint, test_payload)
            print(f"SUCCESS! Response: {response}")
            
            if isinstance(response, dict) and "batchRequestId" in response:
                batch_id = response["batchRequestId"]
                print(f"Batch ID: {batch_id}")
                
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
                print("No batch ID found in response!")
        except Exception as e:
            print(f"ERROR: {str(e)}")
            
            # Try to extract more error details
            if hasattr(e, 'response') and hasattr(e.response, 'content'):
                try:
                    error_details = json.loads(e.response.content)
                    print("Error details:")
                    print(json.dumps(error_details, indent=2))
                except:
                    print(f"Raw error response: {e.response.content}")
        
        # Return whether the test was successful
        return True
    except Exception as e:
        print(f"Error testing with simple payload: {str(e)}")
        traceback.print_exc()
        return False

def test_with_real_product():
    """
    Test product creation using data from an existing TrendyolProduct in the database.
    """
    print("\n===== TESTING PRODUCT CREATION WITH REAL PRODUCT DATA =====\n")
    
    try:
        # Get API client
        print("Getting API client...")
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        print(f"Using API client with base URL: {api_client.config.base_url}")
        
        # Create a product manager
        product_manager = TrendyolProductManager(api_client)
        
        # Get a sample product
        print("Finding a product in the database...")
        test_product = TrendyolProduct.objects.filter(batch_status='failed').first()
        if not test_product:
            test_product = TrendyolProduct.objects.first()
            
        if not test_product:
            print("No products found to test")
            return False
        
        print(f"Found test product: {test_product.title}")
        
        # Find category ID
        print(f"Finding best category for '{test_product.category_name}'")
        category_id = product_manager.category_finder.find_best_category(test_product.category_name)
        print(f"Found category ID: {category_id}")
        
        # Get brand ID
        print(f"Getting brand ID for '{test_product.brand_name}'")
        brand_id = product_manager.get_brand_id(test_product.brand_name)
        print(f"Found brand ID: {brand_id}")
        
        # Get attributes for this category
        print(f"Getting attributes for category ID {category_id}")
        attributes = product_manager.category_finder._get_sample_attributes(category_id)
        print(f"Found {len(attributes)} attributes for category")
        
        # Print sample attributes
        print("\nSample attributes from API:")
        for i, attr in enumerate(attributes[:3]):
            print(f"Attribute {i+1}:")
            for key, value in attr.items():
                print(f"  {key}: {value} (type: {type(value).__name__})")
        
        # Build payload
        print("\nBuilding product payload...")
        payload = product_manager._build_product_payload(test_product, category_id, brand_id, attributes)
        
        # Print the payload
        print("Using the following payload:")
        print(json.dumps(payload, indent=2))
        
        # Check attribute format
        if "items" in payload and payload["items"] and isinstance(payload["items"], list):
            item = payload["items"][0]
            if "attributes" in item:
                attributes = item["attributes"]
                print(f"\nChecking {len(attributes)} attributes in payload:")
                
                all_valid = True
                for i, attr in enumerate(attributes[:5]):
                    print(f"\nAttribute {i+1}:")
                    
                    # Check attributeId
                    if "attributeId" in attr:
                        attr_id = attr["attributeId"]
                        print(f"  attributeId: {attr_id} (type: {type(attr_id).__name__})")
                        
                        if not isinstance(attr_id, int):
                            print(f"  WARNING: attributeId is not an integer!")
                            all_valid = False
                    else:
                        print("  WARNING: No attributeId found!")
                        all_valid = False
                    
                    # Check attributeValueId if present
                    if "attributeValueId" in attr:
                        val_id = attr["attributeValueId"]
                        print(f"  attributeValueId: {val_id} (type: {type(val_id).__name__})")
                        
                        if not isinstance(val_id, int):
                            print(f"  WARNING: attributeValueId is not an integer!")
                            all_valid = False
                
                if all_valid:
                    print("\nAll checked attributes have correct format (integer IDs).")
                else:
                    print("\nWARNING: Some attributes have incorrect format!")
        
        # Make the request
        print("\nSending request to Trendyol API...")
        try:
            response = api_client.post(f"product/sellers/{api_client.config.seller_id}/products", payload)
            print(f"SUCCESS! Response: {response}")
            
            if isinstance(response, dict) and "batchRequestId" in response:
                batch_id = response["batchRequestId"]
                print(f"Batch ID: {batch_id}")
                
                # Update the product with the new batch ID
                test_product.batch_id = batch_id
                test_product.batch_status = "processing"
                test_product.status_message = "Product creation initiated via test script"
                test_product.save()
                
                print(f"Updated product {test_product.id} with new batch ID")
                
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
                print("No batch ID found in response!")
        except Exception as e:
            print(f"ERROR: {str(e)}")
            
            # Try to extract more error details
            if hasattr(e, 'response') and hasattr(e.response, 'content'):
                try:
                    error_details = json.loads(e.response.content)
                    print("Error details:")
                    print(json.dumps(error_details, indent=2))
                except:
                    print(f"Raw error response: {e.response.content}")
        
        # Return whether the test was successful
        return True
    except Exception as e:
        print(f"Error testing with real product: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n===== TRENDYOL PRODUCT CREATION TESTS =====\n")
    
    try:
        # Test with a simple payload first
        simple_payload_test = test_with_simple_payload()
        
        # Test with real product data
        real_product_test = test_with_real_product()
        
        print("\n===== TEST RESULTS =====")
        print(f"Simple payload test completed: {'Successfully' if simple_payload_test else 'Failed'}")
        print(f"Real product test completed: {'Successfully' if real_product_test else 'Failed'}")
        
    except Exception as e:
        print(f"Error running tests: {str(e)}")
        traceback.print_exc()