"""
Script to fix the attribute format in the Trendyol API client.

This script adds an ensure_integer_attributes method to the TrendyolProductManager class
to ensure proper attribute formatting for Trendyol API requests.

Run this script with: python manage.py shell < fix_attribute_format_simple.py
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
from trendyol.trendyol_api_new import TrendyolProductManager, get_api_client_from_config
from trendyol.models import TrendyolProduct

def add_integer_attributes_method():
    """Add the ensure_integer_attributes method to the TrendyolProductManager class"""
    print("\n===== ADDING ensure_integer_attributes METHOD =====\n")
    
    # Define the new method to add to TrendyolProductManager
    def ensure_integer_attributes(self, attributes_list):
        """Ensure all attribute IDs are integers"""
        fixed_attributes = []
        for attr in attributes_list:
            fixed_attr = {}
            
            # Convert attributeId to integer
            if "attributeId" in attr:
                try:
                    fixed_attr["attributeId"] = int(attr["attributeId"])
                except (ValueError, TypeError):
                    fixed_attr["attributeId"] = attr["attributeId"]
            
            # Convert attributeValueId to integer
            if "attributeValueId" in attr:
                try:
                    fixed_attr["attributeValueId"] = int(attr["attributeValueId"])
                except (ValueError, TypeError):
                    fixed_attr["attributeValueId"] = attr["attributeValueId"]
            
            fixed_attributes.append(fixed_attr)
        
        return fixed_attributes
    
    # Add the method to the class
    print("Adding ensure_integer_attributes method to TrendyolProductManager")
    TrendyolProductManager._ensure_integer_attributes = ensure_integer_attributes
    
    print("Method added successfully.")
    return True

def patch_build_product_payload():
    """Patch the _build_product_payload method to use ensure_integer_attributes"""
    print("\n===== PATCHING _build_product_payload METHOD =====\n")
    
    # Get the original method reference
    original_method = TrendyolProductManager._build_product_payload
    
    # Define the new method that wraps the original one
    def patched_build_product_payload(self, product, category_id, brand_id, attributes):
        """Build a product payload with proper attribute format"""
        # Call the original method
        payload = original_method(self, product, category_id, brand_id, attributes)
        
        # Fix attribute format in the payload
        if "items" in payload and payload["items"] and isinstance(payload["items"], list):
            for item in payload["items"]:
                if "attributes" in item and item["attributes"]:
                    item["attributes"] = self._ensure_integer_attributes(item["attributes"])
        
        return payload
    
    # Patch the method
    print("Patching _build_product_payload method")
    TrendyolProductManager._build_product_payload = patched_build_product_payload
    
    print("Method patched successfully.")
    return True

def test_payload_building():
    """Test building a product payload with the patched methods"""
    print("\n===== TESTING PRODUCT PAYLOAD BUILDING =====\n")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        # Get a product manager
        product_manager = TrendyolProductManager(api_client)
        
        # Get a sample product
        product = TrendyolProduct.objects.first()
        if not product:
            print("No products found to test")
            return False
        
        print(f"Using product: {product.title}")
        
        # Find a category ID
        print("Finding category ID...")
        category_id = product_manager.category_finder.find_best_category(product.category_name)
        print(f"Found category ID: {category_id}")
        
        # Get a brand ID
        print("Finding brand ID...")
        brand_id = product_manager.get_brand_id(product.brand_name)
        print(f"Found brand ID: {brand_id}")
        
        # Get sample attributes
        print("Getting sample attributes...")
        attributes = product_manager.category_finder._get_sample_attributes(category_id)
        print(f"Found {len(attributes)} attributes")
        
        # Print sample attributes
        if attributes:
            print("\nSample attribute before processing:")
            print(attributes[0])
        
        # Build the payload
        print("\nBuilding product payload...")
        payload = product_manager._build_product_payload(product, category_id, brand_id, attributes)
        
        # Check attribute format
        if "items" in payload and payload["items"] and isinstance(payload["items"], list):
            item = payload["items"][0]
            if "attributes" in item:
                attributes = item["attributes"]
                print(f"\nChecking {len(attributes)} attributes in payload:")
                
                all_valid = True
                for i, attr in enumerate(attributes[:3]):
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
        
        return True
    except Exception as e:
        print(f"Error testing payload building: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("\n===== TRENDYOL ATTRIBUTE FORMAT FIX =====\n")
    
    try:
        # Add the ensure_integer_attributes method
        add_integer_attributes_method()
        
        # Patch the _build_product_payload method
        patch_build_product_payload()
        
        # Test the patched methods
        test_payload_building()
        
        print("\nAttribute format fix has been applied to the TrendyolProductManager class in memory.")
        print("To make this fix permanent, you'll need to modify the trendyol_api_new.py file.")
        
        return True
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()