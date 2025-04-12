"""
Script to fix the Trendyol API client with all the necessary improvements.

This script applies several fixes to the API client:
1. Uses the correct base URL
2. Ensures proper attribute format with integer IDs
3. Adds address IDs to product payload
4. Properly formats request headers

Run this script with: python manage.py shell < fix_trendyol_api.py
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

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI, TrendyolProductManager

def ensure_correct_api_url():
    """Ensure the API configuration uses the correct base URL"""
    print("\n===== ENSURING CORRECT API URL =====\n")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return False
    
    print(f"Current API config:")
    print(f"- Base URL: {config.base_url}")
    print(f"- User Agent: {config.user_agent}")
    
    # Verify the base URL is correct
    if config.base_url != "https://apigw.trendyol.com/integration":
        print(f"Updating base URL to: https://apigw.trendyol.com/integration")
        config.base_url = "https://apigw.trendyol.com/integration"
        config.save()
        print("Base URL updated successfully.")
    else:
        print("Base URL is already correct.")
    
    # Verify the user agent is correct
    expected_user_agent = f"{config.seller_id} - SelfIntegration"
    if config.user_agent != expected_user_agent:
        print(f"Updating user agent to: {expected_user_agent}")
        config.user_agent = expected_user_agent
        config.save()
        print("User agent updated successfully.")
    else:
        print("User agent is already correct.")
    
    return True

def fix_build_product_payload():
    """Fix the _build_product_payload method to ensure proper attribute format"""
    print("\n===== FIXING _build_product_payload METHOD =====\n")
    
    # Define the attribute format fix
    fix_code = '''    def _ensure_integer_attributes(self, attributes_list):
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
    
    # Create a fixed version of the _build_product_payload method
    fixed_method = '''    def _build_product_payload(self, product, category_id, brand_id, attributes):
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
        
        return payload'''
    
    # Original file path
    file_path = "trendyol/trendyol_api_new.py"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    # Read the original file
    print(f"Reading file: {file_path}")
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if the file already has the fix
    if "_ensure_integer_attributes" in content:
        print("File already contains the _ensure_integer_attributes method.")
        return True
    
    # Create a backup of the original file
    backup_path = "trendyol/trendyol_api_new.py.bak"
    print(f"Creating backup at: {backup_path}")
    with open(backup_path, 'w') as f:
        f.write(content)
    
    # Replace the _build_product_payload method
    import re
    pattern = r'    def _build_product_payload\(self, product, category_id, brand_id, attributes\):.*?return payload'
    replacement = fixed_method
    
    # Use a regex sub with DOTALL flag to match across multiple lines
    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Find where to insert the _ensure_integer_attributes method
    # Look for the TrendyolProductManager class
    manager_class_match = re.search(r'class TrendyolProductManager:', updated_content)
    if not manager_class_match:
        print("Could not find the TrendyolProductManager class. Manual fix required.")
        print("\nAdd this method to the TrendyolProductManager class:")
        print(fix_code)
        return False
    
    # Find the end of the _build_product_payload method
    build_payload_end = re.search(r'return payload', updated_content)
    if not build_payload_end:
        print("Could not find the end of the _build_product_payload method. Manual fix required.")
        print("\nAdd this method to the TrendyolProductManager class:")
        print(fix_code)
        return False
    
    # Calculate the position to insert the _ensure_integer_attributes method
    insert_pos = build_payload_end.end() + 1
    
    # Insert the method
    final_content = updated_content[:insert_pos] + "\n\n" + fix_code + updated_content[insert_pos:]
    
    # Write the updated file
    print(f"Writing fixed file to: {file_path}")
    with open(file_path, 'w') as f:
        f.write(final_content)
    
    print("File updated successfully. Backup saved at: trendyol/trendyol_api_new.py.bak")
    return True

def fix_make_request_method():
    """Fix the _make_request method to use the correct headers"""
    print("\n===== FIXING _make_request METHOD =====\n")
    
    # Define the header format fix
    fix_code = '''    def _make_request(self, method, endpoint, **kwargs):
        """Generic request method with retry logic"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        logger.info(f"[DEBUG-API] {method} isteği gönderiliyor: {endpoint}")
        
        # Construct full URL
        url = f"{self.config.base_url.rstrip('/')}/{endpoint}"
        logger.info(f"[DEBUG-API] URL: {url}")
        logger.info(f"[DEBUG-API] Method: {method}")
        
        # Create auth token for basic auth
        auth_token = base64.b64encode(f"{self.config.api_key}:{self.config.api_secret}".encode()).decode()
        
        # Set headers with auth token
        headers = {
            "User-Agent": self.config.user_agent or f"{self.config.seller_id} - SelfIntegration",
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/json"
        }
        
        # Add headers to kwargs if not already present
        if 'headers' not in kwargs:
            kwargs['headers'] = headers
        else:
            # Merge with existing headers
            kwargs['headers'].update(headers)
        
        logger.info(f"[DEBUG-API] Headers: {kwargs.get('headers')}")
        
        # Retry logic
        for attempt in range(1, max_retries + 1):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, **kwargs)
                elif method.upper() == 'POST':
                    response = requests.post(url, **kwargs)
                elif method.upper() == 'PUT':
                    response = requests.put(url, **kwargs)
                elif method.upper() == 'DELETE':
                    response = requests.delete(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                logger.info(f"[DEBUG-API] Status Code: {response.status_code}")
                try:
                    logger.info(f"[DEBUG-API] Response: {json.dumps(response.json())[:1000]}")
                except:
                    logger.info(f"[DEBUG-API] Response: {response.text[:1000]}")
                
                # Check for successful response
                response.raise_for_status()
                
                # Parse JSON response
                try:
                    result = response.json()
                except ValueError:
                    result = response.text
                
                logger.info(f"[DEBUG-API] {method} cevabı başarılı: {endpoint}")
                return result
            
            except requests.exceptions.RequestException as e:
                # Log the error
                logger.error(f"[DEBUG-API] Request failed on attempt {attempt}: {str(e)}")
                
                # Try to get more detailed error info
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail = e.response.json()
                        logger.error(f"[DEBUG-API] Error details: {json.dumps(error_detail)}")
                    except:
                        logger.error(f"[DEBUG-API] Error response: {e.response.text}")
                
                # If this is the last attempt, reraise the exception
                if attempt == max_retries:
                    logger.error(f"API request failed after {max_retries} attempts: {str(e)}")
                    if method.upper() == 'GET':
                        logger.error(f"[DEBUG-API] GET hatası: {str(e)} - {endpoint}")
                    elif method.upper() == 'POST':
                        logger.error(f"[DEBUG-API] POST hatası: {str(e)} - {endpoint}")
                    raise
                
                # Otherwise, wait and retry
                logger.warning(f"Attempt {attempt} failed, retrying...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff'''
    
    # Original file path
    file_path = "trendyol/trendyol_api_new.py"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    # Read the original file
    print(f"Reading file: {file_path}")
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Create a backup of the original file if not already done
    backup_path = "trendyol/trendyol_api_new.py.bak"
    if not os.path.exists(backup_path):
        print(f"Creating backup at: {backup_path}")
        with open(backup_path, 'w') as f:
            f.write(content)
    
    # Replace the _make_request method
    import re
    pattern = r'    def _make_request\(self, method, endpoint, \*\*kwargs\):.*?retry_delay \*= 2  # Exponential backoff'
    replacement = fix_code
    
    # Use a regex sub with DOTALL flag to match across multiple lines
    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if updated_content == content:
        print("Could not update the _make_request method. Pattern might be different.")
        print("\nManual fix for _make_request method:")
        print(fix_code)
        return False
    
    # Write the updated file
    print(f"Writing fixed file to: {file_path}")
    with open(file_path, 'w') as f:
        f.write(updated_content)
    
    print("File updated successfully with _make_request method fix.")
    return True

def fix_batch_status_checking():
    """Fix the check_batch_status method to handle various response formats"""
    print("\n===== FIXING check_batch_status METHOD =====\n")
    
    # Define the fixed method
    fix_code = '''    def check_batch_status(self, batch_id):
        """Check the status of a batch operation"""
        try:
            if not batch_id:
                logger.warning("No batch ID provided")
                return {"status": "failed", "message": "No batch ID provided"}
            
            # Ensure batch_id is a string
            batch_id = str(batch_id)
            
            # Remove any url prefix if present
            if '/' in batch_id:
                batch_id = batch_id.split('/')[-1]
            
            logger.info(f"Checking batch status for ID: {batch_id}")
            
            # Construct the endpoint
            endpoint = f"product/sellers/{self.api_client.config.seller_id}/products/batch-requests/{batch_id}"
            
            # Make the request
            response = self.api_client.get(endpoint)
            
            logger.info(f"Batch status response: {response}")
            
            # Check if response is a string (some error responses are strings)
            if isinstance(response, str):
                try:
                    # Try to parse as JSON
                    parsed = json.loads(response)
                    
                    # Check for status in parsed response
                    if "status" in parsed:
                        return parsed
                    
                    # If no status, return error
                    return {"status": "failed", "message": str(parsed)}
                except json.JSONDecodeError:
                    # Not JSON, just return as error
                    return {"status": "failed", "message": response}
            
            # Handle dictionary response
            if isinstance(response, dict):
                # If the response contains items, process them
                if "items" in response and response["items"]:
                    result = {"status": "success", "items": []}
                    
                    for item in response["items"]:
                        item_status = item.get("status", "unknown")
                        
                        # Map success/error status
                        if item_status.lower() in ["success", "approved"]:
                            status = "success"
                        else:
                            status = "failed"
                        
                        # Add error message if present
                        error_message = item.get("errorMessage", "")
                        
                        # Add productId if present
                        product_id = None
                        if "productId" in item:
                            product_id = item["productId"]
                        
                        # Create item result
                        item_result = {
                            "status": status,
                            "message": error_message
                        }
                        
                        if product_id:
                            item_result["productId"] = product_id
                        
                        result["items"].append(item_result)
                    
                    return result
                
                # If response has a status field directly
                if "status" in response:
                    return response
                
                # If batchRequestStatus is present
                if "batchRequestStatus" in response:
                    return {"status": response["batchRequestStatus"].lower()}
                
                # If no recognized fields, return the whole response
                return {"status": "unknown", "message": str(response)}
            
            # If response is a list or other type, convert to error response
            return {"status": "failed", "message": str(response)}
        
        except Exception as e:
            logger.error(f"Error checking batch status: {str(e)}")
            return {"status": "failed", "message": str(e)}'''
    
    # Original file path
    file_path = "trendyol/trendyol_api_new.py"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    # Read the original file
    print(f"Reading file: {file_path}")
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Create a backup of the original file if not already done
    backup_path = "trendyol/trendyol_api_new.py.bak"
    if not os.path.exists(backup_path):
        print(f"Creating backup at: {backup_path}")
        with open(backup_path, 'w') as f:
            f.write(content)
    
    # Replace the check_batch_status method
    import re
    pattern = r'    def check_batch_status\(self, batch_id\):.*?return \{"status": "failed", "message": str\(e\)\}'
    replacement = fix_code
    
    # Use a regex sub with DOTALL flag to match across multiple lines
    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if updated_content == content:
        print("Could not update the check_batch_status method. Pattern might be different.")
        print("\nManual fix for check_batch_status method:")
        print(fix_code)
        return False
    
    # Write the updated file
    print(f"Writing fixed file to: {file_path}")
    with open(file_path, 'w') as f:
        f.write(updated_content)
    
    print("File updated successfully with check_batch_status method fix.")
    return True

def main():
    """Main function"""
    print("\n===== TRENDYOL API CLIENT FIX =====\n")
    
    try:
        # Ensure correct API URL
        ensure_correct_api_url()
        
        # Fix the _build_product_payload method
        fix_build_product_payload()
        
        # Fix the _make_request method
        fix_make_request_method()
        
        # Fix the batch status checking
        fix_batch_status_checking()
        
        print("\n===== TRENDYOL API CLIENT FIX COMPLETE =====")
        print("The Trendyol API client has been updated with the following fixes:")
        print("1. Correct base URL and user agent")
        print("2. Proper attribute format with integer IDs")
        print("3. Inclusion of shipment and returning addresses in product payload")
        print("4. Improved error handling and response processing")
        print("5. Enhanced batch status checking")
        
        return True
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()