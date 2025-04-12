"""
Script to test updated auth credentials and submit a product to Trendyol.

This script uses the updated API credentials from environment variables
and attempts to send a product to Trendyol.

Run this script with: python manage.py shell < fix_auth_and_submit.py
"""

import logging
import json
import base64
import requests
from trendyol.models import TrendyolProduct, TrendyolAPIConfig

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_api_auth():
    """Test the Trendyol API authentication with updated credentials."""
    logger.info("Testing Trendyol API authentication with updated credentials")
    
    # Get the API config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("No active API configuration found")
        return False
    
    # Print the config (without revealing full credentials)
    logger.info(f"API URL: {config.base_url}")
    logger.info(f"Seller ID: {config.seller_id}")
    logger.info(f"API Key: ****{config.api_key[-4:] if config.api_key else '-'}")
    logger.info(f"API Secret: ****{config.api_secret[-4:] if config.api_secret else '-'}")
    logger.info(f"User Agent: {config.user_agent}")
    
    # Prepare authentication
    auth_str = f"{config.api_key}:{config.api_secret}"
    auth_bytes = auth_str.encode('ascii')
    auth_b64_bytes = base64.b64encode(auth_bytes)
    auth_b64 = auth_b64_bytes.decode('ascii')
    
    # Prepare headers
    headers = {
        'Authorization': f"Basic {auth_b64}",
        'Content-Type': 'application/json',
        'User-Agent': config.user_agent
    }
    
    # Test a simple API endpoint - brands
    base_url = config.base_url.rstrip('/')
    url = f"{base_url}/brands"
    
    logger.info(f"Testing authentication with URL: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        
        if response.status_code == 200:
            logger.info("Authentication successful!")
            
            # Print the first few brands to confirm data is being received
            data = response.json()
            logger.info(f"Received {len(data)} brands")
            if data:
                logger.info(f"First 5 brands: {data[:5]}")
            
            return True
        else:
            logger.error(f"Authentication failed with status code {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error testing authentication: {str(e)}")
        return False

def submit_product(product_id):
    """Submit a single product to Trendyol."""
    try:
        # Get the product
        product = TrendyolProduct.objects.get(id=product_id)
        logger.info(f"Processing product {product.id}: {product.title[:50]}...")
        
        # Get the API config
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            logger.error("No active API configuration found")
            return False
        
        # Prepare authentication
        auth_str = f"{config.api_key}:{config.api_secret}"
        auth_bytes = auth_str.encode('ascii')
        auth_b64_bytes = base64.b64encode(auth_bytes)
        auth_b64 = auth_b64_bytes.decode('ascii')
        
        # Prepare headers
        headers = {
            'Authorization': f"Basic {auth_b64}",
            'Content-Type': 'application/json',
            'User-Agent': config.user_agent
        }
        
        # Prepare URL
        base_url = config.base_url.rstrip('/')
        url = f"{base_url}/product/sellers/{config.seller_id}/products"
        
        # Prepare attributes
        attributes = []
        if product.attributes:
            if isinstance(product.attributes, str):
                try:
                    attrs = json.loads(product.attributes)
                except:
                    attrs = {}
            else:
                attrs = product.attributes
            
            if 'color' in attrs:
                attributes.append({
                    "attributeId": 348,
                    "attributeValueId": 1011
                })
        
        # Prepare payload
        payload = {
            "items": [
                {
                    "barcode": product.barcode,
                    "title": product.title[:100].strip(),
                    "productMainId": product.barcode,
                    "brandId": product.brand_id,
                    "categoryId": product.category_id,
                    "quantity": 10,
                    "stockCode": product.barcode,
                    "dimensionalWeight": 1,
                    "description": (product.description or product.title)[:500],
                    "currencyType": "TRY",
                    "listPrice": float(product.price),
                    "salePrice": float(product.price),
                    "vatRate": 10,
                    "cargoCompanyId": 17,
                    "images": [{"url": product.image_url}],
                    "attributes": attributes
                }
            ]
        }
        
        # Print request details for debugging
        logger.info(f"Submitting request to URL: {url}")
        logger.info(f"With headers: {headers}")
        logger.info(f"With payload: {json.dumps(payload, indent=2)}")
        
        # Make the request
        response = requests.post(url, json=payload, headers=headers)
        
        # Process response
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response text: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            if 'batchRequestId' in response_data:
                batch_id = response_data['batchRequestId']
                logger.info(f"Success! Product sent to Trendyol with batch ID: {batch_id}")
                
                # Update product
                product.batch_id = batch_id
                product.batch_status = 'processing'
                product.status_message = f"Submitted with batch ID: {batch_id}"
                product.save()
                
                return True
        
        # If we got here, something went wrong
        error_msg = f"Failed to submit product: HTTP {response.status_code} - {response.text}"
        logger.error(error_msg)
        
        product.batch_status = 'failed'
        product.status_message = error_msg
        product.save()
        
        return False
        
    except Exception as e:
        logger.error(f"Error submitting product: {str(e)}")
        return False

def main():
    """Test authentication and submit a product to Trendyol."""
    logger.info("Starting authentication test and product submission")
    
    # Test authentication
    auth_success = test_api_auth()
    if not auth_success:
        logger.error("Authentication test failed, cannot proceed with product submission")
        return
    
    # Get the first pending product
    product = TrendyolProduct.objects.filter(batch_status='pending').first()
    if not product:
        logger.info("No pending products found")
        return
    
    # Submit the product
    success = submit_product(product.id)
    
    if success:
        logger.info(f"Successfully submitted product {product.id}")
    else:
        logger.error(f"Failed to submit product {product.id}")
    
    logger.info("Authentication test and product submission completed")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()