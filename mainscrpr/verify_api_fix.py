"""
Script to verify that the Trendyol API fix has been properly applied.

This script tests the operation of the Trendyol API client with the fixes 
to ensure that attributes are properly formatted.

Run this script with: python verify_api_fix.py
"""

import django
import os
import sys
import json
import logging
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client
from trendyol.trendyol_api_new import TrendyolProductManager, get_api_client_from_config, TrendyolAPI
from trendyol.models import TrendyolProduct, TrendyolAPIConfig

def verify_fix_applied():
    """Verify that the fix has been applied to the TrendyolProductManager class"""
    print("\n===== VERIFYING API FIX =====\n")
    
    # Check if the TrendyolProductManager class has the _ensure_integer_attributes method
    if not hasattr(TrendyolProductManager, '_ensure_integer_attributes'):
        print("ERROR: _ensure_integer_attributes method not found in TrendyolProductManager class")
        return False
    
    print("SUCCESS: _ensure_integer_attributes method found in TrendyolProductManager class")
    
    # Check if the _build_product_payload method has been patched
    # Get the source code of the method
    import inspect
    method_source = inspect.getsource(TrendyolProductManager._build_product_payload)
    
    # Check if the method calls _ensure_integer_attributes
    if "self._ensure_integer_attributes" not in method_source:
        print("ERROR: _build_product_payload method does not call _ensure_integer_attributes")
        return False
    
    print("SUCCESS: _build_product_payload method has been patched to call _ensure_integer_attributes")
    
    return True

def test_attribute_conversion():
    """Test the attribute conversion functionality"""
    print("\n===== TESTING ATTRIBUTE CONVERSION =====\n")
    
    # Create a TrendyolAPI instance
    api_client = get_api_client_from_config()
    if not api_client:
        print("ERROR: Failed to get TrendyolAPI instance")
        return False
    
    # Create a TrendyolProductManager instance
    product_manager = TrendyolProductManager(api_client)
    
    # Create test attributes with string IDs
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
    
    print("Test attributes before conversion:")
    print(json.dumps(test_attributes, indent=2))
    
    # Convert attributes
    fixed_attributes = product_manager._ensure_integer_attributes(test_attributes)
    
    print("\nAttributes after conversion:")
    print(json.dumps(fixed_attributes, indent=2))
    
    # Verify that all IDs are integers
    all_valid = True
    for attr in fixed_attributes:
        if not isinstance(attr.get("attributeId"), int):
            print(f"ERROR: attributeId {attr.get('attributeId')} is not an integer")
            all_valid = False
        
        if not isinstance(attr.get("attributeValueId"), int):
            print(f"ERROR: attributeValueId {attr.get('attributeValueId')} is not an integer")
            all_valid = False
    
    if all_valid:
        print("\nSUCCESS: All attribute IDs converted to integers")
    else:
        print("\nERROR: Some attribute IDs were not properly converted")
    
    return all_valid

def test_product_payload():
    """Test building a product payload with the fixed method"""
    print("\n===== TESTING PRODUCT PAYLOAD BUILDING =====\n")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("ERROR: Failed to get API client")
            return False
        
        # Get a product manager
        product_manager = TrendyolProductManager(api_client)
        
        # Get a sample product
        product = TrendyolProduct.objects.first()
        if not product:
            print("ERROR: No products found to test")
            return False
        
        print(f"Using product: {product.title}")
        
        # Use fixed category ID and brand ID to avoid complex lookups
        category_id = 1081  # Children's Clothing
        brand_id = 102  # LC Waikiki
        
        # Create test attributes with string IDs
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
        
        # Build the payload
        print("Building product payload...")
        payload = product_manager._build_product_payload(product, category_id, brand_id, test_attributes)
        
        # Print the payload for inspection
        print("\nProduct payload:")
        print(json.dumps(payload, indent=2))
        
        # Check attribute format
        if "items" in payload and payload["items"] and isinstance(payload["items"], list):
            item = payload["items"][0]
            if "attributes" in item:
                attributes = item["attributes"]
                print(f"\nChecking {len(attributes)} attributes in payload:")
                
                all_valid = True
                for i, attr in enumerate(attributes):
                    print(f"\nAttribute {i+1}:")
                    
                    # Check attributeId
                    if "attributeId" in attr:
                        attr_id = attr["attributeId"]
                        print(f"  attributeId: {attr_id} (type: {type(attr_id).__name__})")
                        
                        if not isinstance(attr_id, int):
                            print(f"  ERROR: attributeId is not an integer!")
                            all_valid = False
                    else:
                        print("  ERROR: No attributeId found!")
                        all_valid = False
                    
                    # Check attributeValueId if present
                    if "attributeValueId" in attr:
                        val_id = attr["attributeValueId"]
                        print(f"  attributeValueId: {val_id} (type: {type(val_id).__name__})")
                        
                        if not isinstance(val_id, int):
                            print(f"  ERROR: attributeValueId is not an integer!")
                            all_valid = False
                
                if all_valid:
                    print("\nSUCCESS: All attributes have correct format (integer IDs)")
                else:
                    print("\nERROR: Some attributes have incorrect format!")
                
                return all_valid
        
        print("ERROR: Could not find attributes in payload")
        return False
    except Exception as e:
        print(f"Error testing product payload: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("\n===== TRENDYOL API FIX VERIFICATION =====\n")
    
    try:
        # Verify that the fix has been applied
        fix_applied = verify_fix_applied()
        
        # Test attribute conversion
        attribute_conversion = test_attribute_conversion()
        
        # Test product payload building
        payload_valid = test_product_payload()
        
        # Print summary
        print("\n===== VERIFICATION SUMMARY =====")
        print(f"Fix applied to API client: {'SUCCESS' if fix_applied else 'FAILED'}")
        print(f"Attribute conversion test: {'SUCCESS' if attribute_conversion else 'FAILED'}")
        print(f"Product payload test: {'SUCCESS' if payload_valid else 'FAILED'}")
        
        all_success = fix_applied and attribute_conversion and payload_valid
        
        if all_success:
            print("\nVERIFICATION SUCCESSFUL: All tests passed!")
            print("The API fix has been properly applied and is working correctly.")
        else:
            print("\nVERIFICATION FAILED: Some tests did not pass.")
            print("Please check the error messages above for details.")
        
        return all_success
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()