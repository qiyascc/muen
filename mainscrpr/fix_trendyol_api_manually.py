"""
Script to manually fix the Trendyol API client file.

This script reads and updates the trendyol_api_new.py file to add the
ensure_integer_attributes method and update the _build_product_payload method.

Run this script with: python fix_trendyol_api_manually.py
"""

import os
import sys
import json
import logging
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_build_product_payload():
    """Manually fix the trendyol_api_new.py file"""
    print("\n===== MANUALLY FIXING trendyol_api_new.py =====\n")
    
    # Define the path to the file
    file_path = "trendyol/trendyol_api_new.py"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return False
    
    # Read the file content
    print(f"Reading file: {file_path}")
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Create a backup of the original file
    backup_path = "trendyol/trendyol_api_new.py.bak"
    print(f"Creating backup at: {backup_path}")
    with open(backup_path, 'w') as f:
        f.write(content)
    
    # Define the ensure_integer_attributes method to add
    ensure_integer_attributes_method = """    def _ensure_integer_attributes(self, attributes_list):
        \"\"\"Ensure all attribute IDs are integers\"\"\"
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
        
        return fixed_attributes"""
    
    # Define the updated build_product_payload method
    build_payload_method = """    def _build_product_payload(self, product, category_id, brand_id, attributes):
        \"\"\"Construct the complete product payload\"\"\"
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
        
        return payload"""
    
    # Function to find the TrendyolProductManager class in the content
    def find_class_position(content, class_name):
        """Find the position of a class in the content"""
        import re
        class_pattern = rf"class {class_name}:"
        match = re.search(class_pattern, content)
        if match:
            return match.start()
        return -1
    
    # Function to find the _build_product_payload method in the content
    def find_method_position(content, method_name):
        """Find the position of a method in the content"""
        import re
        method_pattern = rf"    def {method_name}\("
        match = re.search(method_pattern, content)
        if match:
            return match.start()
        return -1
    
    # Function to find the end of a method
    def find_method_end(content, start_pos):
        """Find the end position of a method"""
        # Skip the method signature and find the first line with less indentation
        lines = content[start_pos:].split('\n')
        method_signature = lines[0]
        indent_level = len(method_signature) - len(method_signature.lstrip())
        
        # Calculate method end
        line_count = 0
        for i, line in enumerate(lines[1:], 1):
            if line.strip() and len(line) - len(line.lstrip()) <= indent_level:
                return start_pos + sum(len(l) + 1 for l in lines[:i])
            line_count = i
        
        # If we reach the end of the file
        return start_pos + sum(len(l) + 1 for l in lines[:line_count+1])
    
    # Find the TrendyolProductManager class
    class_pos = find_class_position(content, "TrendyolProductManager")
    if class_pos == -1:
        print("Error: Could not find TrendyolProductManager class")
        return False
    
    # Find the _build_product_payload method
    method_pos = find_method_position(content, "_build_product_payload")
    if method_pos == -1:
        print("Error: Could not find _build_product_payload method")
        return False
    
    # Find the end of the _build_product_payload method
    method_end = find_method_end(content, method_pos)
    
    # Replace the _build_product_payload method
    updated_content = content[:method_pos] + build_payload_method + content[method_end:]
    
    # Find where to insert the _ensure_integer_attributes method
    # We'll insert it right after the _build_product_payload method
    insert_pos = method_pos + len(build_payload_method)
    
    # Insert the _ensure_integer_attributes method
    final_content = updated_content[:insert_pos] + "\n\n" + ensure_integer_attributes_method + updated_content[insert_pos:]
    
    # Write the updated content to a new file for safety
    fixed_path = "trendyol_api_fixed.py"
    print(f"Writing fixed file to: {fixed_path}")
    with open(fixed_path, 'w') as f:
        f.write(final_content)
    
    print(f"Fixed file created: {fixed_path}")
    print("To apply the fix, copy this file to trendyol/trendyol_api_new.py")
    print(f"Original file backed up at: {backup_path}")
    
    return True

def main():
    """Main function"""
    print("\n===== TRENDYOL API MANUAL FIX =====\n")
    
    try:
        # Fix the build_product_payload method
        fix_build_product_payload()
        
        return True
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()