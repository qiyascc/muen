"""
Script to test Trendyol API with direct token.

This script uses the provided token directly instead of
generating it from API key and secret.

Run this script with: python manage.py shell < direct_token_test.py
"""

import logging
import json
import requests
from trendyol.models import TrendyolProduct

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use the directly provided token
API_TOKEN = "cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="
SELLER_ID = "535623"

def test_brands_api():
    """Test the Trendyol Brands API with direct token."""
    logger.info("Testing Trendyol Brands API with direct token")
    
    # Create session with headers
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Basic {API_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": f"{SELLER_ID} - SelfIntegration"
    })
    
    # Test different base URLs and endpoints
    base_urls = [
        "https://apigw.trendyol.com/integration",
        "https://apigw.trendyol.com",
        "https://api.trendyol.com/integration",
        "https://api.trendyol.com"
    ]
    
    endpoints = [
        "/brands",
        f"/sellers/{SELLER_ID}/brands",
        "/product-categories"
    ]
    
    success = False
    working_url = None
    
    for base_url in base_urls:
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            logger.info(f"Testing URL: {url}")
            
            try:
                response = session.get(url)
                logger.info(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info(f"Success with URL: {url}")
                    working_url = url
                    success = True
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        logger.info(f"First few items: {data[:3]}")
                    elif isinstance(data, dict) and 'categories' in data:
                        logger.info(f"Found {len(data['categories'])} categories")
                    break
                else:
                    logger.info(f"Response: {response.text[:200]}")
            except Exception as e:
                logger.error(f"Error with URL {url}: {str(e)}")
        
        if success:
            break
    
    return success, working_url

def test_product_submission():
    """Test product submission with direct token."""
    logger.info("Testing product submission with direct token")
    
    # Get a product to submit
    product = TrendyolProduct.objects.filter(batch_status='pending').first()
    if not product:
        logger.error("No pending products found")
        return False
    
    logger.info(f"Found product: {product.id} - {product.title[:50]}")
    
    # Prepare headers
    headers = {
        "Authorization": f"Basic {API_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": f"{SELLER_ID} - SelfIntegration"
    }
    
    # Test different payload variations
    payloads = []
    
    # Payload 1: Simplified
    payloads.append({
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
                "attributes": []
            }
        ]
    })
    
    # Payload 2: With basic attributes
    payloads.append({
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
                "shipmentAddressId": 0,
                "deliveryDuration": 3,
                "images": [{"url": product.image_url}],
                "attributes": [
                    {
                        "attributeId": 348,
                        "attributeValueId": 1011
                    }
                ]
            }
        ]
    })
    
    # Payload 3: With more detailed attributes
    payloads.append({
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
                "shipmentAddressId": 0,
                "deliveryDuration": 3,
                "images": [{"url": product.image_url}],
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
    })
    
    # Test different URLs
    base_urls = [
        "https://apigw.trendyol.com/integration",
        "https://api.trendyol.com/integration"
    ]
    
    endpoints = [
        f"/product/sellers/{SELLER_ID}/products",
        f"/product/suppliers/{SELLER_ID}/products",
        f"/suppliers/{SELLER_ID}/products"
    ]
    
    success = False
    for base_url in base_urls:
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            logger.info(f"Testing URL: {url}")
            
            for i, payload in enumerate(payloads):
                logger.info(f"Trying payload variation {i+1}")
                
                try:
                    response = requests.post(url, json=payload, headers=headers)
                    logger.info(f"Response status: {response.status_code}")
                    logger.info(f"Response: {response.text}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'batchRequestId' in data:
                            batch_id = data['batchRequestId']
                            logger.info(f"Success! Product submitted with batch ID: {batch_id}")
                            
                            # Update product
                            product.batch_id = batch_id
                            product.batch_status = 'processing'
                            product.status_message = f"Submitted with batch ID: {batch_id}"
                            product.save()
                            
                            success = True
                            return True
                except Exception as e:
                    logger.error(f"Error with URL {url} and payload {i+1}: {str(e)}")
    
    logger.error("All URL and payload combinations failed")
    return False

def main():
    """Run all tests."""
    logger.info("Starting Trendyol API tests with direct token")
    
    # Test the brands API first to see if we can connect
    brands_success, working_url = test_brands_api()
    
    if brands_success:
        logger.info(f"Successfully connected to Trendyol API with URL: {working_url}")
        
        # Now try product submission
        submission_success = test_product_submission()
        
        if submission_success:
            logger.info("Product submission successful!")
        else:
            logger.error("Product submission failed")
    else:
        logger.error("Failed to connect to Trendyol API")
    
    logger.info("Tests completed")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()