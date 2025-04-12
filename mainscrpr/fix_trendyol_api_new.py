"""
Script to fix the Trendyol API integration with the working approach found in tests.

This script updates the Trendyol API client to use the endpoint and authentication format
that has been confirmed to work correctly.

Run this script with: python manage.py shell < fix_trendyol_api_new.py
"""

import logging
import json
import os
from trendyol.models import TrendyolAPIConfig
from trendyol.trendyol_api_new import TrendyolAPI
from django.utils import timezone

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_api_client():
    """Fix the Trendyol API client with the working approach."""
    logger.info("Updating TrendyolAPI client with the working approach")
    
    # Update the TrendyolAPI class to use the correct endpoint format
    trendyol_api_path = 'trendyol/trendyol_api_new.py'
    try:
        with open(trendyol_api_path, 'r') as f:
            content = f.read()
        
        # Replace make_request method
        old_make_request = """
    def make_request(self, method, endpoint, data=None, params=None, files=None):
        """Make a request to the Trendyol API."""
        full_url = f"{self.base_url}{endpoint}"
        
        headers = self.get_headers().copy()
        
        logger.debug(f"Making request to {full_url}")
        
        try:
            if method.upper() == 'GET':
                response = requests.get(full_url, headers=headers, params=params)
            elif method.upper() == 'POST':
                if files:
                    response = requests.post(full_url, headers=headers, data=data, files=files)
                else:
                    response = requests.post(full_url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(full_url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(full_url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Trendyol API: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            raise
"""
        
        new_make_request = """
    def make_request(self, method, endpoint, data=None, params=None, files=None):
        """Make a request to the Trendyol API."""
        # Debug logging
        logger.debug(f"[DEBUG-API] make_request çağrısı. Orijinal endpoint: {endpoint}")
        
        # Ensure endpoint has the product prefix if it's a category or product related request
        if endpoint.startswith('/product-categories') or endpoint.startswith('/product/product-categories'):
            # Use the working endpoint format for categories
            full_url = f"{self.base_url}/product/product-categories"
        elif endpoint.startswith('/sellers') and ('products' in endpoint or 'brands' in endpoint):
            # Use the working endpoint format for product operations
            full_url = f"{self.base_url}/product{endpoint}"
        elif endpoint.startswith('/suppliers') and 'products' in endpoint:
            # Use the working endpoint format for product operations
            full_url = f"{self.base_url}/product{endpoint}"
        else:
            # For other endpoints, use standard format
            full_url = f"{self.base_url}{endpoint}"
        
        logger.debug(f"[DEBUG-API] Oluşturulan URL: {full_url}")
        
        headers = self.get_headers().copy()
        
        # Explicitly add the Accept header which was present in working requests
        headers.update({
            'Accept': '*/*',
            'Connection': 'keep-alive'
        })
        
        logger.debug(f"[DEBUG-API] SON İSTEK: {method} {full_url}")
        logger.debug(f"[DEBUG-API] İSTEK HEADERS: {headers}")
        
        try:
            if method.upper() == 'GET':
                response = requests.get(full_url, headers=headers, params=params)
            elif method.upper() == 'POST':
                if files:
                    response = requests.post(full_url, headers=headers, data=data, files=files)
                else:
                    response = requests.post(full_url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(full_url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(full_url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Trendyol API: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            raise
"""
        
        # Replace get_headers method
        old_get_headers = """
    def get_headers(self):
        """Get the headers for API requests."""
        return {
            'Authorization': f'Basic {self.auth_token}',
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent
        }
"""
        
        new_get_headers = """
    def get_headers(self):
        """Get the headers for API requests."""
        return {
            'Authorization': f'Basic {self.auth_token}',
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
"""
        
        # Update the content
        updated_content = content.replace(old_make_request, new_make_request)
        updated_content = updated_content.replace(old_get_headers, new_get_headers)
        
        # Write the updated content back to the file
        with open(trendyol_api_path, 'w') as f:
            f.write(updated_content)
        
        logger.info("Successfully updated TrendyolAPI client")
        return True
    except Exception as e:
        logger.error(f"Error updating TrendyolAPI client: {str(e)}")
        return False

def update_api_config():
    """Update API configuration with the correct token and settings."""
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

def test_new_api_client():
    """Test the updated API client."""
    logger.info("Testing the updated API client")
    
    try:
        # Get the API client
        from trendyol.api_client import get_api_client
        api_client = get_api_client()
        
        # Test getting categories
        logger.info("Testing getting categories")
        try:
            result = api_client.get_categories()
            if result and isinstance(result, list) and len(result) > 0:
                logger.info(f"Successfully retrieved {len(result)} categories")
                logger.info(f"First category: {result[0]['name']} (ID: {result[0]['id']})")
                return True
            else:
                logger.error("Failed to retrieve categories")
                return False
        except Exception as e:
            logger.error(f"Error getting categories: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error testing API client: {str(e)}")
        return False

def create_test_product():
    """Create a test product for submission testing."""
    logger.info("Creating a test product for submission testing")
    
    try:
        from trendyol.models import TrendyolProduct
        
        # Check if we already have a test product
        test_product = TrendyolProduct.objects.filter(title__startswith='TEST PRODUCT').first()
        if test_product:
            logger.info(f"Using existing test product: {test_product.id} - {test_product.title}")
            
            # Reset its status to pending
            test_product.batch_status = 'pending'
            test_product.batch_id = None
            test_product.status_message = None
            test_product.save()
            
            logger.info("Reset test product to pending status")
            return test_product
        
        # Create a new test product
        new_product = TrendyolProduct(
            title='TEST PRODUCT - LC Waikiki Erkek T-Shirt',
            barcode='TEST123456789',
            lcw_url='https://www.lcwaikiki.com/tr-TR/TR/test-product',
            description='Test ürün açıklaması',
            price='299.99',
            old_price='349.99',
            discount='14',
            currency='TL',
            brand_id=102,  # LC Waikiki Brand ID
            category_id=2356,  # Example category ID
            image_url='https://img-lcwaikiki.mncdn.com/mnresize/1200/1800/pim/productimages/20231/5915299/l_20231-s37982z8-ctk-1-t2899_2.jpg',
            batch_status='pending'
        )
        new_product.save()
        
        logger.info(f"Created new test product: {new_product.id} - {new_product.title}")
        return new_product
    except Exception as e:
        logger.error(f"Error creating test product: {str(e)}")
        return None

def submit_test_product():
    """Submit the test product to Trendyol."""
    logger.info("Submitting test product to Trendyol")
    
    try:
        test_product = create_test_product()
        if not test_product:
            logger.error("Failed to create test product")
            return False
        
        # Manually submit the product
        from trendyol.api_client import get_api_client
        api_client = get_api_client()
        
        try:
            # Get the product manager
            product_manager = api_client.get_product_manager()
            
            # Submit the product
            logger.info("Submitting product to Trendyol")
            result = product_manager.submit_product(test_product)
            
            if result and isinstance(result, dict) and 'batchRequestId' in result:
                batch_id = result['batchRequestId']
                logger.info(f"Successfully submitted test product with batch ID: {batch_id}")
                
                # Update the product
                test_product.batch_id = batch_id
                test_product.batch_status = 'processing'
                test_product.status_message = f"Submitted with batch ID: {batch_id}"
                test_product.save()
                
                return True
            else:
                logger.error("Failed to submit test product")
                logger.error(f"API result: {result}")
                return False
        except Exception as e:
            logger.error(f"Error submitting test product: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error in submit_test_product: {str(e)}")
        return False

def main():
    """Main function to fix Trendyol API integration."""
    logger.info("Starting to fix Trendyol API integration")
    
    # Fix the API client
    api_client_fixed = fix_api_client()
    
    # Update API configuration
    api_config_updated = update_api_config()
    
    if api_client_fixed and api_config_updated:
        logger.info("API client and configuration updated. Testing new setup...")
        
        # Test the new API client
        api_test_successful = test_new_api_client()
        
        if api_test_successful:
            logger.info("API client test successful. Proceeding to submit a test product...")
            
            # Submit a test product
            submission_successful = submit_test_product()
            
            if submission_successful:
                logger.info("Test product submission successful!")
                logger.info("Trendyol API integration has been successfully fixed")
            else:
                logger.error("Test product submission failed")
        else:
            logger.error("API client test failed")
    else:
        logger.error("Failed to update API client or configuration")
    
    logger.info("Fix process completed")

if __name__ == "__main__":
    main()
else:
    # When imported from Django shell
    main()