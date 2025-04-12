"""
Script to update the Trendyol API configuration with the working token.

This is a simplified version of the fix_trendyol_api_new.py script that only
updates the API configuration without trying to modify the API client code.

Run this script with: python manage.py shell < update_api_config.py
"""

import logging
import os
from trendyol.models import TrendyolAPIConfig
from django.utils import timezone
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def test_api_call():
    """Test the API with direct request."""
    logger.info("Testing direct API call with updated configuration")
    
    API_TOKEN = "cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="
    SELLER_ID = "535623"
    
    headers = {
        'Authorization': f'Basic {API_TOKEN}',
        'Content-Type': 'application/json',
        'User-Agent': f'{SELLER_ID} - SelfIntegration',
        'Accept-Encoding': 'gzip, deflate',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }
    
    url = "https://apigw.trendyol.com/integration/product/product-categories"
    
    logger.info(f"=== DEBUG API REQUEST ===")
    logger.info(f"URL: {url}")
    logger.info(f"Method: GET")
    logger.info(f"Headers: {headers}")
    
    try:
        attempts = 3
        for i in range(attempts):
            logger.info(f"Attempt {i+1} of {attempts}...")
            response = requests.get(url, headers=headers)
            
            logger.info(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if 'categories' in data:
                    logger.info(f"Response: {data}")
                    logger.info(f"=== END DEBUG API REQUEST ===")
                    return True
                else:
                    logger.info(f"Unexpected response format: {data}")
            else:
                logger.info(f"Response: {response.text}")
        
        logger.info(f"=== END DEBUG API REQUEST ===")
        return False
    except Exception as e:
        logger.error(f"Error making direct API call: {str(e)}")
        logger.info(f"=== END DEBUG API REQUEST ===")
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
        
        # Let's look at the model fields first
        logger.info("TrendyolProduct model fields:")
        for field in TrendyolProduct._meta.fields:
            logger.info(f"- {field.name}: {field.get_internal_type()}")
        
        # Create a new test product with only valid fields
        new_product = TrendyolProduct(
            title='TEST PRODUCT - LC Waikiki Erkek T-Shirt',
            barcode='TEST123456789',
            description='Test ürün açıklaması',
            price='299.99',
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

def main():
    """Main function."""
    logger.info("Starting API configuration update")
    
    # Update the API configuration
    config_updated = update_api_config()
    
    if config_updated:
        logger.info("API configuration updated. Testing direct API call...")
        
        # Test direct API call
        api_test = test_api_call()
        
        if api_test:
            logger.info("Direct API call successful. Creating test product...")
            
            # Create test product
            test_product = create_test_product()
            
            if test_product:
                logger.info("Test product created/updated successfully.")
                logger.info("Now you can try submitting this product from the admin panel.")
            else:
                logger.error("Failed to create test product")
        else:
            logger.error("Direct API call failed")
    else:
        logger.error("Failed to update API configuration")
    
    logger.info("Process completed")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()