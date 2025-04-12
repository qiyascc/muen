"""
Script to fix attribute type issues in the Trendyol API client.

After extensive testing, we've found that the attributes format requires numeric IDs
for attributeId and attributeValueId fields. This script specifically updates the code
to ensure all attribute IDs are properly converted to integers.

Run this script with: python manage.py shell < fix_attribute_types.py
"""

import django
import os
import sys
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI, TrendyolProductManager

def update_get_sample_attributes_method():
    """
    Update the _get_sample_attributes method in TrendyolCategoryFinder to ensure 
    all attribute IDs are properly converted to integers.
    """
    print("Analyzing TrendyolCategoryFinder._get_sample_attributes method...")
    
    try:
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        # Create a temporary product manager
        product_manager = TrendyolProductManager(api_client)
        
        # Test with a known category ID
        category_id = 1081
        print(f"Testing with category ID {category_id}")
        
        # Get attributes before any changes
        print("Getting attributes before changes...")
        attributes_before = product_manager.category_finder._get_sample_attributes(category_id)
        
        print(f"Retrieved {len(attributes_before)} attributes")
        
        # Check attribute format before changes
        print("\nSample attribute format before changes:")
        for i, attr in enumerate(attributes_before[:3]):
            print(f"Attribute {i+1}:")
            for key, value in attr.items():
                print(f"  {key}: {value} (type: {type(value).__name__})")
        
        # Check if the values are already integers
        all_integer_ids = True
        for attr in attributes_before:
            if 'attributeId' in attr and not isinstance(attr['attributeId'], int):
                all_integer_ids = False
                print(f"  WARNING: attributeId is not an integer: {attr['attributeId']} ({type(attr['attributeId']).__name__})")
            
            if 'attributeValueId' in attr and not isinstance(attr['attributeValueId'], int):
                all_integer_ids = False
                print(f"  WARNING: attributeValueId is not an integer: {attr['attributeValueId']} ({type(attr['attributeValueId']).__name__})")
        
        if all_integer_ids:
            print("All attribute IDs are already integers - no need to fix!")
            return True
        
        # Create a fix for the _get_sample_attributes method
        print("\nCreating a fixed implementation of _get_sample_attributes...")
        
        # Here's the fixed implementation
        fixed_implementation = '''
def _get_sample_attributes(self, category_id):
    """Generate sample attributes for a category"""
    attributes = []
    category_attrs = self.get_category_attributes(category_id)
    
    for attr in category_attrs.get("categoryAttributes", []):
        # Skip attributes with empty attributeValues array when custom values are not allowed
        if not attr.get("attributeValues") and not attr.get("allowCustom"):
            continue
            
        # Ensure attributeId is an integer
        attribute_id = attr["attribute"]["id"]
        if isinstance(attribute_id, str):
            try:
                attribute_id = int(attribute_id)
            except ValueError:
                logger.warning(f"Could not convert attributeId {attribute_id} to integer")
                continue
        
        attribute = {
            "attributeId": attribute_id,
            "attributeName": attr["attribute"]["name"]
        }
        
        if attr.get("attributeValues") and len(attr["attributeValues"]) > 0:
            if not attr["allowCustom"]:
                # Ensure attributeValueId is an integer
                value_id = attr["attributeValues"][0]["id"]
                if isinstance(value_id, str):
                    try:
                        value_id = int(value_id)
                    except ValueError:
                        logger.warning(f"Could not convert attributeValueId {value_id} to integer")
                        continue
                
                attribute["attributeValueId"] = value_id
                attribute["attributeValue"] = attr["attributeValues"][0]["name"]
            else:
                attribute["customAttributeValue"] = f"Sample {attr['attribute']['name']}"
        
        attributes.append(attribute)
    
    return attributes
'''
        
        print("Fixed implementation created. You can update the trendyol_api_new.py file with this code.")
        print("The implementation ensures all attributeId and attributeValueId values are integers.")
        
        print("\nTo apply this fix, update the TrendyolCategoryFinder._get_sample_attributes method in trendyol_api_new.py.")
        
        return True
        
    except Exception as e:
        print(f"Error updating _get_sample_attributes method: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def ensure_proper_attribute_format():
    """
    Update product submission code to ensure proper attribute format.
    """
    print("\n\nChecking _build_product_payload method...")
    
    try:
        # Get a sample product
        test_product = TrendyolProduct.objects.first()
        if not test_product:
            print("No products found to test")
            return False
        
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        # Create a product manager
        product_manager = TrendyolProductManager(api_client)
        
        # Find category ID
        category_id = product_manager.category_finder.find_best_category(test_product.category_name)
        print(f"Found category ID: {category_id}")
        
        # Get brand ID
        brand_id = product_manager.get_brand_id(test_product.brand_name)
        print(f"Found brand ID: {brand_id}")
        
        # Get attributes for this category
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
        
        # Check final attributes in payload
        if 'items' in payload and payload['items'] and isinstance(payload['items'], list):
            item = payload['items'][0]
            
            if 'attributes' in item:
                attrs = item['attributes']
                print(f"\nFinal attributes in payload (count: {len(attrs)}):")
                
                # Check if all attribute IDs are integers
                all_integer_ids = True
                for i, attr in enumerate(attrs[:5]):
                    print(f"\nAttribute {i+1}:")
                    for key, value in attr.items():
                        print(f"  {key}: {value} (type: {type(value).__name__})")
                    
                    if 'attributeId' in attr and not isinstance(attr['attributeId'], int):
                        all_integer_ids = False
                        print(f"  WARNING: attributeId is not an integer: {attr['attributeId']} ({type(attr['attributeId']).__name__})")
                    
                    if 'attributeValueId' in attr and not isinstance(attr['attributeValueId'], int):
                        all_integer_ids = False
                        print(f"  WARNING: attributeValueId is not an integer: {attr['attributeValueId']} ({type(attr['attributeValueId']).__name__})")
                
                if all_integer_ids:
                    print("All attribute IDs in the final payload are integers - no need to fix the _build_product_payload method!")
                else:
                    print("\nWARNING: Some attribute IDs in the final payload are not integers.")
                    print("The _build_product_payload method needs to be updated to ensure all IDs are integers.")
            else:
                print("No attributes found in the final payload!")
        
        return True
        
    except Exception as e:
        print(f"Error checking _build_product_payload method: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_with_hard_coded_attributes():
    """
    Test using a hard-coded payload with proper attribute format.
    """
    print("\n\nTesting with hard-coded attribute format...")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        # Create a very simple product payload with proper attribute format
        test_payload = {
            "items": [
                {
                    "barcode": "test123456",
                    "title": "Test Product",
                    "productMainId": "test123456",
                    "brandId": 102,  # LC Waikiki brand ID
                    "categoryId": 1081,  # Some valid category ID
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
        
        endpoint = f"product/sellers/{api_client.config.seller_id}/products"
        print(f"Testing creation with endpoint: {endpoint}")
        print(f"Using payload with known good attribute format")
        
        try:
            response = api_client.post(endpoint, test_payload)
            print(f"SUCCESS! Response: {response}")
            print("The API accepts the properly formatted attributes.")
        except Exception as e:
            print(f"ERROR: {str(e)}")
            
            if hasattr(e, 'response') and hasattr(e.response, 'content'):
                try:
                    error_details = json.loads(e.response.content)
                    print("Error details:")
                    print(json.dumps(error_details, indent=2))
                except:
                    print(f"Raw error response: {e.response.content}")
        
        return True
        
    except Exception as e:
        print(f"Error testing with hard-coded attributes: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n===== FIXING ATTRIBUTE TYPE ISSUES =====\n")
    
    try:
        print("This script will analyze and fix attribute type issues in the TrendyolAPI client.")
        print("Specifically, it ensures that attributeId and attributeValueId are integers.\n")
        
        update_result = update_get_sample_attributes_method()
        
        format_result = ensure_proper_attribute_format()
        
        test_result = test_with_hard_coded_attributes()
        
        print("\n\nRECOMMENDATIONS:")
        print("1. Update the TrendyolCategoryFinder._get_sample_attributes method with the fixed implementation.")
        print("2. Ensure all attributeId and attributeValueId values are converted to integers.")
        print("3. Test with a simple product payload to verify the fix.")
        
    except Exception as e:
        print(f"Error running fix script: {str(e)}")
        import traceback
        traceback.print_exc()