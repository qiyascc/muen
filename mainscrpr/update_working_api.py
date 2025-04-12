"""
Script to update the Trendyol API integration with the working endpoints and authentication.

This script updates the TrendyolAPI class to use the endpoints that have been verified to work.

Run this script with: python manage.py shell < update_working_api.py
"""

import logging
import os
import sys
from trendyol.models import TrendyolAPIConfig
from django.utils import timezone

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_api_config():
    """Update the API configuration with the correct token and settings."""
    logger.info("Updating API configuration")
    
    try:
        # Get active config
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            logger.error("No active API configuration found")
            return False
        
        # Update with the working token
        config.auth_token = "cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="
        config.api_key = "qSohKkLKPWwDeSKjwz8R"
        config.api_secret = "yYF3Ycl9B6Vjs77q3MhE"
        config.base_url = "https://apigw.trendyol.com/integration"
        config.user_agent = "535623 - SelfIntegration"
        config.seller_id = "535623"
        config.last_updated = timezone.now()
        
        # Save the config
        config.save()
        
        logger.info("Successfully updated API configuration")
        logger.info(f"- Base URL: {config.base_url}")
        logger.info(f"- User Agent: {config.user_agent}")
        logger.info(f"- Seller ID: {config.seller_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating API configuration: {str(e)}")
        return False

def create_updated_api_client():
    """Create an updated version of the API client with working endpoints."""
    logger.info("Creating updated API client")
    
    file_path = "trendyol/trendyol_api_working.py"
    
    code = """\"\"\"
Updated Trendyol API client with working endpoints.

This module contains the updated TrendyolAPI class that uses the 
endpoints verified to work with the current Trendyol API version.
\"\"\"

import base64
import json
import logging
import requests
import time
from django.utils import timezone
from trendyol.models import TrendyolAPIConfig

logger = logging.getLogger(__name__)

class TrendyolAPI:
    \"\"\"
    Trendyol API client using verified working endpoints.
    \"\"\"
    
    def __init__(self, api_config=None):
        \"\"\"Initialize the API client with the given config or the active config from the database.\"\"\"
        if api_config:
            self.config = api_config
        else:
            try:
                self.config = TrendyolAPIConfig.objects.filter(is_active=True).first()
                if not self.config:
                    logger.error("No active API configuration found")
            except Exception as e:
                logger.error(f"Error loading API configuration: {str(e)}")
                self.config = None
        
        if self.config:
            self.base_url = self.config.base_url
            self.auth_token = self.config.auth_token
            self.api_key = self.config.api_key
            self.api_secret = self.config.api_secret
            self.seller_id = self.config.seller_id
            self.user_agent = self.config.user_agent
        else:
            logger.warning("Initializing with default values - this is likely not what you want")
            self.base_url = "https://apigw.trendyol.com/integration"
            self.auth_token = ""
            self.api_key = ""
            self.api_secret = ""
            self.seller_id = ""
            self.user_agent = ""
        
        logger.info(f"Initialized TrendyolAPI client with base URL: {self.base_url}")

    def get_headers(self):
        \"\"\"Get the headers for API requests.\"\"\"
        return {
            'Authorization': f'Basic {self.auth_token}',
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        
    def make_request(self, method, endpoint, data=None, params=None):
        \"\"\"
        Make a request to the Trendyol API using verified working endpoints.
        
        Args:
            method: HTTP method ('GET', 'POST', etc.)
            endpoint: API endpoint to call
            data: Optional data to send (for POST/PUT)
            params: Optional query parameters
            
        Returns:
            API response as a dict or raises an exception
        \"\"\"
        # Map endpoints to known working versions
        working_endpoints = {
            # Categories
            "/categories": "/product/product-categories",
            "/product-categories": "/product/product-categories",
            
            # Category attributes
            "/category-attributes": "/product/product-categories/{category_id}/attributes",
            
            # Brands
            "/brands": "/product/brands",
            
            # Products
            "/suppliers/{seller_id}/products": "/product/suppliers/{seller_id}/products"
        }
        
        # Try to find a working endpoint mapping
        for pattern, working_endpoint in working_endpoints.items():
            if pattern in endpoint:
                # Check if we need to replace parameters
                if "{category_id}" in working_endpoint:
                    # Extract category_id from parameters or endpoint
                    category_id = None
                    if params and "categoryId" in params:
                        category_id = params.pop("categoryId")
                    else:
                        # Try to extract from the endpoint
                        import re
                        match = re.search(r"/categories/([0-9]+)/", endpoint)
                        if match:
                            category_id = match.group(1)
                    
                    if category_id:
                        working_endpoint = working_endpoint.replace("{category_id}", str(category_id))
                    else:
                        logger.warning(f"Could not extract category_id for endpoint: {endpoint}")
                        continue
                        
                if "{seller_id}" in working_endpoint:
                    working_endpoint = working_endpoint.replace("{seller_id}", str(self.seller_id))
                    
                logger.info(f"Using working endpoint mapping: {endpoint} -> {working_endpoint}")
                endpoint = working_endpoint
                break
        
        full_url = f"{self.base_url}{endpoint}"
        
        headers = self.get_headers()
        
        logger.debug(f"Making request to {full_url}")
        logger.debug(f"Headers: {headers}")
        if data:
            logger.debug(f"Data: {json.dumps(data, indent=2)}")
        
        try:
            if method.upper() == 'GET':
                response = requests.get(full_url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = requests.post(full_url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(full_url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(full_url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response content: {response.text[:500]}...")
            
            if response.status_code >= 400:
                logger.error(f"Error making request: {response.status_code} - {response.text}")
                
            response.raise_for_status()
            
            if response.text and len(response.text.strip()) > 0:
                return response.json()
            return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Trendyol API: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            raise

    def get_categories(self):
        \"\"\"Get all categories from Trendyol.\"\"\"
        response = self.make_request('GET', '/product/product-categories')
        return response.get('categories', [])
        
    def get_category_attributes(self, category_id):
        \"\"\"Get attributes for a specific category.\"\"\"
        response = self.make_request('GET', f'/product/product-categories/{category_id}/attributes')
        return response.get('categoryAttributes', [])
        
    def get_brands(self, name=None):
        \"\"\"Get brands from Trendyol, optionally filtered by name.\"\"\"
        params = {}
        if name:
            params['name'] = name
            
        response = self.make_request('GET', '/product/brands', params=params)
        return response.get('brands', [])
    
    def submit_product(self, product_data):
        \"\"\"Submit a product to Trendyol.\"\"\"
        # Format product data as expected by Trendyol API
        if isinstance(product_data, dict):
            # Already in API format
            items = [product_data]
        elif isinstance(product_data, list):
            # List of products
            items = product_data
        else:
            # Convert from Django model
            from trendyol.models import TrendyolProduct
            if isinstance(product_data, TrendyolProduct):
                items = [{
                    "barcode": product_data.barcode,
                    "title": product_data.title[:100].strip(),
                    "productMainId": product_data.product_main_id or product_data.barcode,
                    "brandId": product_data.brand_id,
                    "categoryId": product_data.category_id,
                    "quantity": product_data.quantity or 10,
                    "stockCode": product_data.stock_code or product_data.barcode,
                    "dimensionalWeight": 1,
                    "description": (product_data.description or product_data.title)[:500],
                    "currencyType": product_data.currency_type or "TRY",
                    "listPrice": float(product_data.price),
                    "salePrice": float(product_data.price),
                    "vatRate": product_data.vat_rate or 10,
                    "cargoCompanyId": 17,
                    "shipmentAddressId": 0,
                    "deliveryDuration": 3,
                    "images": [{"url": product_data.image_url}],
                    "attributes": product_data.attributes or []
                }]
            else:
                raise ValueError(f"Unsupported product data type: {type(product_data)}")
                
        payload = {"items": items}
        response = self.make_request('POST', f'/product/suppliers/{self.seller_id}/products', data=payload)
        
        # Update batch ID in product model if it's a Django model
        if 'batchRequestId' in response and isinstance(product_data, TrendyolProduct):
            product_data.batch_id = response['batchRequestId']
            product_data.batch_status = 'processing'
            product_data.status_message = f"Submitted with batch ID: {response['batchRequestId']}"
            product_data.save()
            
        return response
    
    def get_batch_status(self, batch_id):
        \"\"\"Get the status of a batch request.\"\"\"
        response = self.make_request('GET', f'/product/suppliers/{self.seller_id}/products/batch-requests/{batch_id}')
        return response
"""
    
    # Write the code to the file
    with open(file_path, 'w') as f:
        f.write(code)
    
    logger.info(f"Created updated API client at {file_path}")
    return True

def update_api_module():
    """Update the API module to use the updated client."""
    logger.info("Updating API module")
    
    file_path = "trendyol/api_client.py"
    update_code = """
# Add import for the working API client
from trendyol.trendyol_api_working import TrendyolAPI as WorkingTrendyolAPI

# Change get_api_client to use the working API client
def get_api_client():
    \"\"\"Get a configured API client.\"\"\"
    try:
        # Use the working API client
        return WorkingTrendyolAPI()
    except Exception as e:
        logger.error(f"Error creating API client: {str(e)}")
        return None
"""
    
    # Check if the file exists
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} not found")
        return False
    
    # Update the file
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find the get_api_client function
        if "def get_api_client" in content:
            lines = content.split('\n')
            updated_lines = []
            
            # Add import before the first import
            if lines[0].startswith("import ") or lines[0].startswith("from "):
                updated_lines.append("# Updated import for working API client")
                updated_lines.append("from trendyol.trendyol_api_working import TrendyolAPI as WorkingTrendyolAPI")
                updated_lines.append("")
            
            # Replace get_api_client function
            in_function = False
            for line in lines:
                if not in_function and line.startswith("def get_api_client"):
                    in_function = True
                    updated_lines.append("def get_api_client():")
                    updated_lines.append("    \"\"\"Get a configured API client.\"\"\"")
                    updated_lines.append("    try:")
                    updated_lines.append("        # Use the working API client instead of the original")
                    updated_lines.append("        return WorkingTrendyolAPI()")
                    updated_lines.append("    except Exception as e:")
                    updated_lines.append("        logger.error(f\"Error creating API client: {str(e)}\")")
                    updated_lines.append("        return None")
                elif in_function and (not line.strip() or line.startswith("def ")):
                    in_function = False
                    updated_lines.append(line)
                elif not in_function:
                    updated_lines.append(line)
            
            # Write the updated content
            with open(file_path, 'w') as f:
                f.write('\n'.join(updated_lines))
            
            logger.info(f"Updated API module at {file_path}")
            return True
        else:
            logger.error("Could not find get_api_client function in API module")
            return False
    except Exception as e:
        logger.error(f"Error updating API module: {str(e)}")
        return False

def test_api():
    """Test the updated API client."""
    logger.info("Testing updated API client")
    
    try:
        # Import client
        from trendyol.trendyol_api_working import TrendyolAPI
        api = TrendyolAPI()
        
        # Test get_categories
        logger.info("Testing get_categories...")
        categories = api.get_categories()
        logger.info(f"Found {len(categories)} categories")
        
        if len(categories) > 0:
            # Test get_category_attributes
            category_id = categories[0]['id']
            logger.info(f"Testing get_category_attributes for category {category_id}...")
            attributes = api.get_category_attributes(category_id)
            logger.info(f"Found {len(attributes)} attributes")
            
            # Test get_brands
            logger.info("Testing get_brands...")
            brands = api.get_brands(name="LC Waikiki")
            logger.info(f"Found {len(brands)} brands matching 'LC Waikiki'")
            
            logger.info("API client is working correctly!")
            return True
    except Exception as e:
        logger.error(f"Error testing API client: {str(e)}")
        return False

def main():
    """Main function."""
    logger.info("Starting API update...")
    
    # Update API config
    api_config_updated = update_api_config()
    
    if not api_config_updated:
        logger.error("Failed to update API configuration")
        return
    
    # Create updated API client
    api_client_created = create_updated_api_client()
    
    if not api_client_created:
        logger.error("Failed to create updated API client")
        return
    
    # Update API module
    api_module_updated = update_api_module()
    
    if not api_module_updated:
        logger.error("Failed to update API module")
        return
    
    # Test API
    api_tested = test_api()
    
    if not api_tested:
        logger.error("Failed to test API")
        return
    
    logger.info("API update completed successfully!")

if __name__ == "__main__":
    main()
else:
    # When imported from Django shell
    main()