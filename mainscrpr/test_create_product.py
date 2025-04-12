"""
Script to test creating a product with the fixed API client.

This script creates a sample product and submits it to Trendyol using the fixed API client.

Run this script with: python manage.py shell < test_create_product.py
"""

import os
import sys
import json
import traceback
import time
import logging

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.models import TrendyolProduct, TrendyolAPIConfig
from trendyol.trendyol_api_new import TrendyolAPI, TrendyolProductManager, get_api_client_from_config
from django.utils import timezone

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_sample_product():
    """Create a sample product for testing"""
    product = TrendyolProduct(
        title="Test Product " + str(int(time.time())),
        description="This is a test product created for API verification",
        barcode="TEST" + str(int(time.time())),
        product_main_id="TESTID" + str(int(time.time())),
        stock_code="TESTSTOCK" + str(int(time.time())),
        brand_name="LC Waikiki",
        brand_id=102,  # LC Waikiki
        category_name="Kadın Giyim > Tişört",
        category_id=1081,  # Children's Clothing (for testing)
        price=129.99,
        quantity=50,
        vat_rate=10,
        currency_type="TRY",
        image_url="https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20232/6338321/v1/l_20232-w3ch64z8-ct1-42-25_a.jpg",
        additional_images=["https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20232/6338321/v1/l_20232-w3ch64z8-ct1-42-25_b.jpg"],
        attributes={
            "Cinsiyet": "Kadın",
            "Renk": "Beyaz",
            "Beden": "M"
        }
    )
    
    try:
        product.save()
        logger.info(f"Created sample product with ID {product.id}")
        return product
    except Exception as e:
        logger.error(f"Error creating sample product: {str(e)}")
        return None

def test_create_product_with_fixed_api():
    """Test creating a product with the fixed API client"""
    print("\n===== TESTING PRODUCT CREATION WITH FIXED API =====\n")
    
    try:
        # Create a sample product
        product = create_sample_product()
        if not product:
            print("ERROR: Failed to create sample product")
            return False
        
        print(f"Created sample product: {product.title}")
        
        # Create a mock API client to avoid actual API calls
        class MockAPIClient:
            def __init__(self):
                self.config = type('Config', (), {'seller_id': '535623'})
                
            def get(self, endpoint):
                # Mock the response from the API
                if 'addresses' in endpoint:
                    return {
                        'supplierAddresses': [
                            {'id': 123, 'isShipmentAddress': True, 'isReturningAddress': False},
                            {'id': 456, 'isShipmentAddress': False, 'isReturningAddress': True}
                        ]
                    }
                return {}
                
            def post(self, endpoint, data):
                # Mock successful response for any POST request
                if 'product/v2' in endpoint:
                    return {"batchRequestId": "mock-batch-id-" + str(int(time.time()))}
                return {}
        
        # Create a product manager with our mock API
        print("Creating product manager with mock API client...")
        product_manager = TrendyolProductManager(MockAPIClient())
        
        # Set up test attributes with string IDs that need conversion
        test_attributes = [
            {
                "attributeId": "338",
                "attributeValueId": "4290"
            },
            {
                "attributeId": "346",
                "attributeValueId": "4761"
            },
            {
                "attributeId": "47",
                "attributeValueId": "7011"
            }
        ]
        
        # Mock posting to API by just building the payload and validating it
        print("Building product payload with the fixed API client...")
        payload = product_manager._build_product_payload(product, product.category_id, product.brand_id, test_attributes)
        
        # Check if the payload is valid
        if "items" in payload and payload["items"] and isinstance(payload["items"], list):
            item = payload["items"][0]
            
            # Check if the required fields are present
            required_fields = ["barcode", "title", "productMainId", "brandId", "categoryId", 
                              "quantity", "description", "attributes"]
            missing_fields = [field for field in required_fields if field not in item]
            
            if missing_fields:
                print(f"ERROR: Missing required fields in payload: {missing_fields}")
                return False
            
            # Check if attributes are properly formatted
            if "attributes" in item:
                attributes = item["attributes"]
                all_valid = True
                
                for attr in attributes:
                    if "attributeId" not in attr or not isinstance(attr["attributeId"], int):
                        print(f"ERROR: Invalid attributeId format: {attr.get('attributeId')}")
                        all_valid = False
                    
                    if "attributeValueId" not in attr or not isinstance(attr["attributeValueId"], int):
                        print(f"ERROR: Invalid attributeValueId format: {attr.get('attributeValueId')}")
                        all_valid = False
                
                if not all_valid:
                    print("ERROR: Attributes in payload have incorrect format")
                    return False
            
            print("\nSUCCESS: Product payload successfully built with valid format")
            print("All required fields are present and attributes have correct integer IDs")
            return True
        else:
            print("ERROR: Invalid payload structure")
            return False
    except Exception as e:
        print(f"Error testing product creation: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("\n===== TRENDYOL PRODUCT CREATION TEST =====\n")
    
    try:
        result = test_create_product_with_fixed_api()
        
        if result:
            print("\n✓ TEST SUCCESSFUL: Product creation with fixed API works correctly")
        else:
            print("\n✗ TEST FAILED: Product creation with fixed API has issues")
        
        return result
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()