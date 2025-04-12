"""
Script to fix the attribute format in the product payload.

This script updates the _build_product_payload method in TrendyolProductManager
to ensure proper attribute format with integer IDs.

Run this script with: python manage.py shell < fix_attribute_format.py
"""

import django
import os
import sys
import json
import logging
from pprint import pprint
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.trendyol_api_new import TrendyolAPI, TrendyolProductManager, get_api_client_from_config

def test_product_payload():
    """Test building a product payload with proper attribute format"""
    print("\n===== TESTING PRODUCT PAYLOAD FORMAT =====\n")
    
    try:
        # Get API client
        api_client = get_api_client_from_config()
        if not api_client:
            print("Failed to get API client")
            return False
        
        print(f"Using API client with base URL: {api_client.config.base_url}")
        
        # Create a product manager
        product_manager = TrendyolProductManager(api_client)
        
        # Get a sample product
        sample_product = TrendyolProduct.objects.first()
        if not sample_product:
            print("No products found to test")
            return False
        
        print(f"Using product: {sample_product.title}")
        
        # Find category ID
        print(f"Finding best category for '{sample_product.category_name}'")
        category_id = product_manager.category_finder.find_best_category(sample_product.category_name)
        print(f"Found category ID: {category_id}")
        
        # Get brand ID
        print(f"Getting brand ID for '{sample_product.brand_name}'")
        brand_id = product_manager.get_brand_id(sample_product.brand_name)
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
        payload = product_manager._build_product_payload(sample_product, category_id, brand_id, attributes)
        
        # Print the payload
        print("Product payload:")
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
        
        return True
    except Exception as e:
        print(f"Error testing product payload: {str(e)}")
        traceback.print_exc()
        return False

def update_build_product_payload():
    """Update the _build_product_payload method in TrendyolProductManager to ensure proper attribute format"""
    print("\n===== UPDATING _build_product_payload METHOD =====\n")
    
    try:
        # Get a sample product
        sample_product = TrendyolProduct.objects.first()
        if not sample_product:
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
        category_id = product_manager.category_finder.find_best_category(sample_product.category_name)
        
        # Get brand ID
        brand_id = product_manager.get_brand_id(sample_product.brand_name)
        
        # Get attributes for this category
        attributes = product_manager.category_finder._get_sample_attributes(category_id)
        
        # Define a helper function to ensure integer attributes
        def ensure_integer_attributes(attributes_list):
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
        
        # Original method for reference
        original_method = product_manager._build_product_payload
        
        # Build payload with original method
        print("Building payload with original method...")
        original_payload = original_method(sample_product, category_id, brand_id, attributes)
        
        # Create a monkey-patched version of the method
        def patched_build_product_payload(self, product, category_id, brand_id, attributes):
            """Build a product payload with proper attribute format"""
            # Call the original method
            payload = original_method(product, category_id, brand_id, attributes)
            
            # Ensure attribute IDs are integers
            if "items" in payload and payload["items"] and isinstance(payload["items"], list):
                for item in payload["items"]:
                    if "attributes" in item and item["attributes"]:
                        item["attributes"] = ensure_integer_attributes(item["attributes"])
            
            return payload
        
        # Monkey-patch the method
        print("Monkey-patching _build_product_payload method...")
        TrendyolProductManager._build_product_payload = patched_build_product_payload
        
        # Build payload with patched method
        print("Building payload with patched method...")
        patched_payload = product_manager._build_product_payload(sample_product, category_id, brand_id, attributes)
        
        # Compare original and patched payloads
        print("\nComparing payloads:")
        if "items" in original_payload and original_payload["items"] and "items" in patched_payload and patched_payload["items"]:
            original_attrs = original_payload["items"][0].get("attributes", [])
            patched_attrs = patched_payload["items"][0].get("attributes", [])
            
            print(f"Original attributes: {len(original_attrs)}")
            print(f"Patched attributes: {len(patched_attrs)}")
            
            if original_attrs and patched_attrs:
                print("\nSample original attribute:")
                pprint(original_attrs[0])
                
                print("\nSample patched attribute:")
                pprint(patched_attrs[0])
        
        print("\nPayload patching complete. The _build_product_payload method has been updated in memory.")
        print("To make this change permanent, add the ensure_integer_attributes function to TrendyolProductManager")
        print("and update the _build_product_payload method in the trendyol_api_new.py file.")
        
        return True
    except Exception as e:
        print(f"Error updating _build_product_payload method: {str(e)}")
        traceback.print_exc()
        return False

def create_updated_api_file():
    """Create an updated version of trendyol_api_new.py with proper attribute handling"""
    print("\n===== CREATING UPDATED API FILE =====\n")
    
    try:
        # Path to the original API file
        original_path = "trendyol/trendyol_api_new.py"
        
        # Read the original file
        with open(original_path, 'r') as f:
            content = f.read()
        
        # Check if the file already has the fix
        if "ensure_integer_attributes" in content:
            print("File already contains the fix.")
            return True
        
        # Define the updated _build_product_payload method
        build_payload_method = '''    def _build_product_payload(self, product, category_id, brand_id, attributes):
        """Construct the complete product payload"""
        # Parse images
        images = []
        for image_url in product.image_urls.split(','):
            if image_url.strip():
                images.append({"url": image_url.strip()})
        
        # Ensure we have at least one image
        if not images and product.thumbnail:
            images.append({"url": product.thumbnail})
        
        # Prepare title - limit to 100 characters and normalize whitespace
        title = product.title
        if title and len(title) > 100:
            title = title[:97] + "..."
        if title:
            # Normalize whitespace to single spaces
            import re
            title = re.sub(r'\\s+', ' ', title).strip()
        
        # Build the product item
        item = {
            "barcode": product.barcode or product.product_code,
            "title": title or product.name or product.description[:100],
            "productMainId": product.product_code,
            "brandId": brand_id,
            "categoryId": category_id,
            "quantity": product.stock_quantity or 10,
            "stockCode": product.stock_code or product.product_code,
            "dimensionalWeight": product.weight or 1,
            "description": product.description or product.name or product.title,
            "currencyType": "TRY",
            "listPrice": float(product.list_price) if product.list_price else float(product.price),
            "salePrice": float(product.price),
            "vatRate": 10,  # Default VAT rate for clothing
            "cargoCompanyId": 17,  # Default cargo company
            "attributes": self._ensure_integer_attributes(attributes),
            "images": images
        }
        
        # Add shipment and returning addresses if available
        try:
            addresses = self.api_client.get(f"sellers/{self.api_client.config.seller_id}/addresses")
            if addresses and 'supplierAddresses' in addresses:
                for address in addresses['supplierAddresses']:
                    if address.get('isShipmentAddress', False):
                        item["shipmentAddressId"] = address.get('id')
                    if address.get('isReturningAddress', False):
                        item["returningAddressId"] = address.get('id')
        except Exception as e:
            logger.warning(f"Could not get addresses: {str(e)}")
        
        # Construct the complete payload
        payload = {
            "items": [item]
        }
        
        return payload
    
    def _ensure_integer_attributes(self, attributes_list):
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
        
        return fixed_attributes'''
        
        # Replace the original method
        pattern = r'    def _build_product_payload\(self, product, category_id, brand_id, attributes\):.*?return payload'
        replacement = build_payload_method
        
        # Use a regex sub with DOTALL flag to match across multiple lines
        import re
        updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        if updated_content == content:
            print("Could not update the file. Method signature might be different.")
            
            # Alternatively, just print the fix for manual application
            print("\nManual fix for _build_product_payload method:")
            print(build_payload_method)
            
            return False
        
        # Write the updated file
        updated_path = "trendyol_api_fixed.py"
        with open(updated_path, 'w') as f:
            f.write(updated_content)
        
        print(f"Updated API file created at: {updated_path}")
        print("Review the changes and if they look good, copy the file to trendyol/trendyol_api_new.py")
        
        return True
    except Exception as e:
        print(f"Error creating updated API file: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("\n===== TRENDYOL ATTRIBUTE FORMAT FIX =====\n")
    
    try:
        # Test current product payload
        test_product_payload()
        
        # Update the _build_product_payload method
        update_build_product_payload()
        
        # Create updated API file
        create_updated_api_file()
        
        return True
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()