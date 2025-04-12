"""
Simple direct API send script for Trendyol.

This script bypasses the model constraints by making a direct API call without saving to database.

Run this script with: python manage.py shell < simple_api_send.py
"""

import logging
import json
import requests
import time
from pprint import pprint

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def direct_api_send():
    """Send a test product directly with API."""
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
    test_product = {
        "barcode": "TEST123456789",
        "title": "TEST PRODUCT - LC Waikiki Erkek T-Shirt",
        "productMainId": "TEST123456789",
        "brandId": 102,  # LC Waikiki
        "categoryId": 2356,  # Example category
        "quantity": 10,
        "stockCode": "TEST123456789",
        "dimensionalWeight": 1,
        "description": "Test ürün açıklaması",
        "currencyType": "TRY",
        "listPrice": 299.99,
        "salePrice": 299.99,
        "vatRate": 10,
        "cargoCompanyId": 17,
        "shipmentAddressId": 0,
        "deliveryDuration": 3,
        "images": [{"url": "https://img-lcwaikiki.mncdn.com/mnresize/1200/1800/pim/productimages/20231/5915299/l_20231-s37982z8-ctk-1-t2899_2.jpg"}],
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
    
    payload = {"items": [test_product]}
    
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
                
                # Check batch status
                check_batch_status(batch_id)
                return True
        
        logger.error(f"Failed to submit product. Status: {response.status_code}")
        logger.error(f"Response: {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error sending request: {str(e)}")
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
    
    # Wait a bit for processing
    logger.info("Waiting 5 seconds for batch processing...")
    time.sleep(5)
    
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

def add_to_standard_api():
    """Add the direct API send approach to the standard API client."""
    from trendyol.api_client import get_api_client
    
    logger.info("Examining the API client...")
    api_client = get_api_client()
    if not api_client:
        logger.error("Failed to get API client")
        return
    
    logger.info("Trying to check if the standard API client works...")
    
    try:
        categories = api_client.get_categories()
        logger.info(f"API client can get categories? {len(categories) > 0}")
    except Exception as e:
        logger.error(f"Error getting categories: {str(e)}")
    
    logger.info("To add this direct API send to the standard API client:")
    logger.info("1. Update trendyol_api_new.py to use the working endpoint format")
    logger.info("2. Ensure the API token is correctly set in the TrendyolAPIConfig")
    logger.info("3. Add proper attribute formatting in the TrendyolProductManager._build_product_payload method")
    
def main():
    """Main function."""
    logger.info("Starting simple direct API send...")
    
    # Try direct API
    success = direct_api_send()
    
    if success:
        logger.info("Direct API send was successful!")
        
        # Add to standard API
        add_to_standard_api()
    else:
        logger.error("Direct API send failed")
    
    logger.info("Simple direct API send completed")

if __name__ == "__main__":
    main()
else:
    # When imported from Django shell
    main()