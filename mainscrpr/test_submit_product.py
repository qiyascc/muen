"""
Script to test submitting a product to Trendyol with the fixes applied.

This script adds the attribute format fix to TrendyolProductManager and then
tests submitting a product to Trendyol API.

Run this script with: python manage.py shell < test_submit_product.py
"""

import django
import os
import sys
import json
import time
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
from trendyol.models import TrendyolProduct, TrendyolAPIConfig

def apply_fixes():
    """Apply the fixes to the TrendyolProductManager class"""
    print("\n===== APPLYING FIXES =====\n")
    
    # Add ensure_integer_attributes method
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
    
    # Add method to class
    TrendyolProductManager._ensure_integer_attributes = ensure_integer_attributes
    
    # Get original build_product_payload method
    original_method = TrendyolProductManager._build_product_payload
    
    # Create patched version
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
    TrendyolProductManager._build_product_payload = patched_build_product_payload
    
    print("Fixes applied successfully.")
    return True

def check_api_config():
    """Check and verify the API configuration"""
    print("\n===== CHECKING API CONFIGURATION =====\n")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return False
    
    print(f"Current API config:")
    print(f"- Name: {config.name}")
    print(f"- Base URL: {config.base_url}")
    print(f"- Seller ID: {config.seller_id}")
    print(f"- API Key: {config.api_key}")
    print(f"- User Agent: {config.user_agent}")
    
    return True

def submit_test_product():
    """Submit a test product to Trendyol API"""
    print("\n===== SUBMITTING TEST PRODUCT =====\n")
    
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
        
        # Print sample attributes after fixing
        fixed_attributes = product_manager._ensure_integer_attributes(attributes)
        if fixed_attributes:
            print("\nSample fixed attribute:")
            print(json.dumps(fixed_attributes[0], indent=2))
        
        # Create product
        print("\nCreating product...")
        try:
            batch_id = product_manager.create_product(product)
            print(f"Success! Batch ID: {batch_id}")
            
            # Update product with batch ID
            product.batch_id = batch_id
            product.batch_status = "processing"
            product.status_message = "Submitted for testing"
            product.save()
            
            # Wait and check batch status
            print("\nWaiting 5 seconds before checking batch status...")
            time.sleep(5)
            
            # Check batch status
            print(f"Checking batch status for ID: {batch_id}")
            status = product_manager.check_batch_status(batch_id)
            print(f"Batch status: {status}")
            
            return True
        except Exception as e:
            print(f"Error creating product: {str(e)}")
            traceback.print_exc()
            
            # Try to extract more error details
            if hasattr(e, 'response') and hasattr(e.response, 'content'):
                try:
                    error_details = json.loads(e.response.content)
                    print("Error details:")
                    print(json.dumps(error_details, indent=2))
                except:
                    print(f"Raw error response: {e.response.content}")
            
            return False
    except Exception as e:
        print(f"Error submitting test product: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("\n===== TRENDYOL PRODUCT SUBMISSION TEST =====\n")
    
    try:
        # Check API configuration
        check_api_config()
        
        # Apply fixes
        apply_fixes()
        
        # Submit test product
        submit_test_product()
        
        return True
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()