"""
Script to send a test product to Trendyol.

This script gets a test product and directly submits it to Trendyol
using the TrendyolAPI client.

Run this script with: python manage.py shell < send_test_product.py
"""

import logging
import json
import requests
import os
import time
from trendyol.models import TrendyolProduct, TrendyolAPIConfig
from trendyol.api_client import get_api_client
from django.utils import timezone
from pprint import pprint

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_test_product():
    """Get a test product to send to Trendyol."""
    test_product = TrendyolProduct.objects.filter(title__startswith='TEST PRODUCT').first()
    if test_product:
        logger.info(f"Found test product: {test_product.id} - {test_product.title}")
        
        # Reset status
        test_product.batch_status = 'pending'
        test_product.batch_id = None
        test_product.status_message = None
        test_product.save()
        return test_product
    
    logger.error("No test product found. Please run update_api_config.py first.")
    return None

def show_api_config():
    """Show current API configuration."""
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("No active API configuration found")
        return
    
    logger.info("Current API configuration:")
    logger.info(f"- API Key: {'*'*10}{config.api_key[-4:] if config.api_key else '-'}")
    logger.info(f"- API Secret: {'*'*10}{config.api_secret[-4:] if config.api_secret else '-'}")
    logger.info(f"- Base URL: {config.base_url}")
    logger.info(f"- User agent: {config.user_agent}")
    logger.info(f"- Seller ID: {config.seller_id}")
    
def direct_api_send():
    """Send a test product directly with API."""
    # Get test product
    test_product = get_test_product()
    if not test_product:
        return False
    
    # API parameters
    API_TOKEN = "cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="
    SELLER_ID = "535623"
    
    logger.info("Building direct API request...")
    
    # Define headers
    headers = {
        'Authorization': f'Basic {API_TOKEN}',
        'Content-Type': 'application/json',
        'User-Agent': f'{SELLER_ID} - SelfIntegration',
        'Accept-Encoding': 'gzip, deflate',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }
    
    # Build the payload
    payload = {
        "items": [
            {
                "barcode": test_product.barcode,
                "title": test_product.title[:100].strip(),
                "productMainId": test_product.barcode,
                "brandId": test_product.brand_id,
                "categoryId": test_product.category_id,
                "quantity": 10,
                "stockCode": test_product.barcode,
                "dimensionalWeight": 1,
                "description": (test_product.description or test_product.title)[:500],
                "currencyType": "TRY",
                "listPrice": float(test_product.price),
                "salePrice": float(test_product.price),
                "vatRate": 10,
                "cargoCompanyId": 17,
                "shipmentAddressId": 0,
                "deliveryDuration": 3,
                "images": [{"url": test_product.image_url}],
                "attributes": [
                    {
                        "attributeId": 348,
                        "attributeValueId": 1011
                    },
                    {
                        "attributeId": 347,
                        "attributeValueId": 4294
                    },
                    {
                        "attributeId": 349,
                        "attributeValueId": 6927
                    },
                    {
                        "attributeId": 350,
                        "attributeValueId": 6980
                    }
                ]
            }
        ]
    }
    
    logger.info("Direct payload:")
    logger.info(json.dumps(payload, indent=2))
    
    # URL
    base_url = "https://apigw.trendyol.com/integration"
    endpoint = f"/product/suppliers/{SELLER_ID}/products"
    url = f"{base_url}{endpoint}"
    
    logger.info(f"Sending request to URL: {url}")

    try:
        # Make the request
        response = requests.post(url, json=payload, headers=headers)
        
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response content: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if 'batchRequestId' in data:
                batch_id = data['batchRequestId']
                logger.info(f"Success! Product submitted with batch ID: {batch_id}")
                
                # Update product
                test_product.batch_id = batch_id
                test_product.batch_status = 'processing'
                test_product.status_message = f"Direct API: Submitted with batch ID: {batch_id}"
                test_product.save()
                return True
        
        logger.error(f"Failed to submit product. Status: {response.status_code}")
        logger.error(f"Response: {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error sending request: {str(e)}")
        return False

def client_api_send():
    """Send a test product using the API client."""
    # Get test product
    test_product = get_test_product()
    if not test_product:
        return False
    
    try:
        # Get API client
        logger.info("Getting API client...")
        api_client = get_api_client()
        if not api_client:
            logger.error("Failed to get API client")
            return False
        
        logger.info(f"Got API client: {api_client}")
        
        # Get product manager
        logger.info("Getting product manager...")
        product_manager = api_client.get_product_manager()
        logger.info(f"Got product manager: {product_manager}")
        
        # Submit product
        logger.info("Submitting product...")
        result = product_manager.submit_product(test_product)
        
        logger.info(f"Submission result: {result}")
        
        if result and 'batchRequestId' in result:
            batch_id = result['batchRequestId']
            logger.info(f"Success! Product submitted with batch ID: {batch_id}")
            
            # Update product
            test_product.batch_id = batch_id
            test_product.batch_status = 'processing'
            test_product.status_message = f"API Client: Submitted with batch ID: {batch_id}"
            test_product.save()
            return True
        
        logger.error("Failed to submit product")
        return False
    except Exception as e:
        logger.error(f"Error using API client: {str(e)}")
        return False

def check_batch_status(batch_id):
    """Check the status of a batch."""
    if not batch_id:
        logger.error("No batch ID provided")
        return False
    
    logger.info(f"Checking status of batch: {batch_id}")
    
    # API parameters
    API_TOKEN = "cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="
    SELLER_ID = "535623"
    
    # Define headers
    headers = {
        'Authorization': f'Basic {API_TOKEN}',
        'Content-Type': 'application/json',
        'User-Agent': f'{SELLER_ID} - SelfIntegration',
        'Accept-Encoding': 'gzip, deflate',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }
    
    # URL
    base_url = "https://apigw.trendyol.com/integration"
    endpoint = f"/product/suppliers/{SELLER_ID}/products/batch-requests/{batch_id}"
    url = f"{base_url}{endpoint}"
    
    logger.info(f"Sending status request to URL: {url}")
    
    try:
        # Make the request
        response = requests.get(url, headers=headers)
        
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response content: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Batch status: {data.get('status', 'Unknown')}")
            return True
    except Exception as e:
        logger.error(f"Error checking batch status: {str(e)}")
    
    return False

def main():
    """Main function."""
    logger.info("Starting test product submission...")
    
    # Show API config
    show_api_config()
    
    # Try with direct API first
    logger.info("Trying direct API submission...")
    direct_success = direct_api_send()
    
    if direct_success:
        logger.info("Direct API submission successful!")
        
        # Get test product to get batch ID
        test_product = get_test_product()
        if test_product and test_product.batch_id:
            # Give Trendyol some time to process
            logger.info("Waiting 5 seconds before checking batch status...")
            time.sleep(5)
            
            # Check batch status
            check_batch_status(test_product.batch_id)
        return
    
    logger.info("Direct API submission failed. Trying with API client...")
    
    # Try with API client
    client_success = client_api_send()
    
    if client_success:
        logger.info("API client submission successful!")
        
        # Get test product to get batch ID
        test_product = get_test_product()
        if test_product and test_product.batch_id:
            # Give Trendyol some time to process
            logger.info("Waiting 5 seconds before checking batch status...")
            time.sleep(5)
            
            # Check batch status
            check_batch_status(test_product.batch_id)
        return
    
    logger.error("All submission methods failed")

if __name__ == "__main__":
    main()
else:
    # When imported from Django shell
    main()