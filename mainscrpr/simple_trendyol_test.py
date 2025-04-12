"""
Simple Trendyol API test with direct API Key.

Based on your description, this script uses a simplified approach
without the Base64 encoding of username:password.

Run this script with: python manage.py shell < simple_trendyol_test.py
"""

import os
import requests
import logging
import json
from trendyol.models import TrendyolAPIConfig

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_simple_auth():
    """Test simple authentication with just the API Key."""
    logger.info("Testing Trendyol API with simple auth")
    
    # Get the API config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("No active API configuration found")
        return False
    
    # Create a session with headers
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Basic {os.environ.get('TRENDYOL_API_KEY')}",
        "User-Agent": f"{config.seller_id} - SelfIntegration",
        "Content-Type": "application/json"
    })
    
    # Test different endpoint formats
    base_url = config.base_url.rstrip('/')
    base_urls = [
        base_url,  # https://apigw.trendyol.com/integration
        base_url.replace("/integration", "")  # https://apigw.trendyol.com
    ]
    
    endpoints = [
        "/brands",
        "/sellers/535623/brands",
        "/product/suppliers/535623/brands"
    ]
    
    for url_base in base_urls:
        for endpoint in endpoints:
            full_url = f"{url_base}{endpoint}"
            logger.info(f"Testing URL: {full_url}")
            
            try:
                response = session.get(full_url)
                status = response.status_code
                logger.info(f"Response status: {status}")
                
                if status == 200:
                    logger.info(f"Success! URL {full_url} works!")
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        logger.info(f"First few items: {data[:3]}")
                    return True
                else:
                    logger.info(f"Response: {response.text[:200]}")
            except Exception as e:
                logger.error(f"Error with URL {full_url}: {str(e)}")
    
    logger.error("All URL combinations failed")
    return False

def test_submit_product():
    """Test submitting a product with simplified auth."""
    if not test_simple_auth():
        logger.error("Authentication test failed. Cannot submit product.")
        return False
    
    logger.info("Authentication test passed. Submitting product...")
    # Get the API config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    
    # Create a session with headers
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Basic {os.environ.get('TRENDYOL_API_KEY')}",
        "User-Agent": f"{config.seller_id} - SelfIntegration",
        "Content-Type": "application/json"
    })
    
    # Get a product to submit
    from trendyol.models import TrendyolProduct
    product = TrendyolProduct.objects.filter(batch_status='pending').first()
    if not product:
        logger.error("No pending products found")
        return False
    
    logger.info(f"Found product: {product.id} - {product.title[:50]}")
    
    # Prepare a simplified payload
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
                "attributes": []
            }
        ]
    }
    
    # Try different URL combinations
    base_url = config.base_url.rstrip('/')
    endpoints = [
        f"/product/sellers/{config.seller_id}/products",
        f"/product/suppliers/{config.seller_id}/products"
    ]
    
    for endpoint in endpoints:
        full_url = f"{base_url}{endpoint}"
        logger.info(f"Submitting to URL: {full_url}")
        
        try:
            response = session.post(full_url, json=payload)
            status = response.status_code
            logger.info(f"Response status: {status}")
            logger.info(f"Response: {response.text}")
            
            if status == 200:
                data = response.json()
                if 'batchRequestId' in data:
                    batch_id = data['batchRequestId']
                    logger.info(f"Success! Product submitted with batch ID: {batch_id}")
                    
                    # Update product
                    product.batch_id = batch_id
                    product.batch_status = 'processing'
                    product.status_message = f"Submitted with batch ID: {batch_id}"
                    product.save()
                    return True
        except Exception as e:
            logger.error(f"Error with URL {full_url}: {str(e)}")
    
    logger.error("All URL combinations failed for product submission")
    return False

def main():
    """Run all tests."""
    logger.info("Starting Trendyol API tests")
    test_submit_product()
    logger.info("Tests completed")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()