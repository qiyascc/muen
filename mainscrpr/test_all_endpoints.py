"""
Script to test all endpoints of the Trendyol API to find working ones.

This script tests various endpoints with different formats to identify 
which one works with our authentication tokens.

Run this script with: python manage.py shell < test_all_endpoints.py
"""

import logging
import json
import requests
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_endpoint(endpoint_path, method="GET", data=None):
    """Test a specific endpoint."""
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
    
    # Base URL
    base_url = "https://apigw.trendyol.com/integration"
    
    # If endpoint path already contains the full URL, use it directly
    url = endpoint_path if endpoint_path.startswith("http") else f"{base_url}{endpoint_path}"
    
    logger.info(f"Testing {method} {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            logger.error(f"Unsupported method: {method}")
            return False, None
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code < 300:  # Success
            logger.info(f"Success! Response content: {response.text[:500]}...")
            try:
                return True, response.json()
            except:
                return True, response.text
        else:
            logger.error(f"Failed with status {response.status_code}: {response.text}")
            return False, None
    except Exception as e:
        logger.error(f"Error testing endpoint: {str(e)}")
        return False, None

def test_product_categories():
    """Test product categories endpoint which was working before."""
    # This is the endpoint format that worked in logs
    endpoint = "/product/product-categories"
    
    success, data = test_endpoint(endpoint)
    if success and data:
        logger.info(f"Found {len(data.get('categories', []))} categories")
        
        # Sample first few categories
        for i, category in enumerate(data.get('categories', [])[:3]):
            logger.info(f"Category {i+1}: {category.get('name')} (ID: {category.get('id')})")
        
        return True
    return False

def test_category_attributes(category_id=2356):
    """Test getting category attributes."""
    endpoints = [
        f"/product/category-attributes?categoryId={category_id}",
        f"/product/product-categories/{category_id}/attributes", 
        f"/product-categories/{category_id}/attributes"
    ]
    
    for endpoint in endpoints:
        logger.info(f"Testing attributes endpoint: {endpoint}")
        success, data = test_endpoint(endpoint)
        if success:
            logger.info(f"Attributes endpoint {endpoint} works!")
            return True
    
    return False

def test_brands():
    """Test getting brands list."""
    endpoints = [
        "/product/brands", 
        "/brands",
        "/brands/by-name?name=LC%20Waikiki"
    ]
    
    for endpoint in endpoints:
        logger.info(f"Testing brands endpoint: {endpoint}")
        success, data = test_endpoint(endpoint)
        if success:
            logger.info(f"Brands endpoint {endpoint} works!")
            return True
    
    return False

def test_product_submission():
    """Test product submission with various endpoint formats."""
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
    
    SELLER_ID = "535623"
    endpoints = [
        f"/product/suppliers/{SELLER_ID}/products",
        f"/suppliers/{SELLER_ID}/products",
        "/product/products"
    ]
    
    for endpoint in endpoints:
        logger.info(f"Testing product submission endpoint: {endpoint}")
        success, data = test_endpoint(endpoint, method="POST", data=payload)
        if success:
            logger.info(f"Product submission endpoint {endpoint} works!")
            
            if isinstance(data, dict) and 'batchRequestId' in data:
                batch_id = data['batchRequestId']
                logger.info(f"Batch request ID: {batch_id}")
            
            return True
    
    return False

def main():
    """Main function."""
    logger.info("Testing Trendyol API endpoints to find working ones")
    
    # Test product categories first
    logger.info("Testing product categories...")
    categories_work = test_product_categories()
    
    # Test category attributes
    logger.info("Testing category attributes...")
    attributes_work = test_category_attributes()
    
    # Test brands
    logger.info("Testing brands...")
    brands_work = test_brands()
    
    # Test product submission
    logger.info("Testing product submission...")
    submission_works = test_product_submission()
    
    # Summary
    logger.info("=== TEST SUMMARY ===")
    logger.info(f"Categories endpoint: {'WORKS' if categories_work else 'FAILS'}")
    logger.info(f"Attributes endpoint: {'WORKS' if attributes_work else 'FAILS'}")
    logger.info(f"Brands endpoint: {'WORKS' if brands_work else 'FAILS'}")
    logger.info(f"Product submission: {'WORKS' if submission_works else 'FAILS'}")
    
    if categories_work or attributes_work or brands_work or submission_works:
        logger.info("At least one endpoint is working. Update the API client to use the working format.")
    else:
        logger.error("No endpoints are working. Check API credentials or try again later.")

if __name__ == "__main__":
    main()
else:
    # When imported from Django shell
    main()