"""
Script to debug working API call seen in logs.

This script analyzes the working API call seen in the logs
and tries to reproduce it with the exact same parameters.

Run this script with: python manage.py shell < debug_working_api.py
"""

import logging
import json
import os
import base64
import requests
from urllib.parse import urlparse, parse_qs
from pprint import pformat
from trendyol.models import TrendyolAPIConfig, TrendyolProduct

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use the directly provided token
API_TOKEN = "cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="
SELLER_ID = "535623"

def test_product_categories():
    """Test the product-categories endpoint that works in the logs."""
    logger.info("Testing product-categories endpoint that works in the logs")
    
    # Define headers exactly as they appear in the logs
    headers = {
        'User-Agent': f"{SELLER_ID} - SelfIntegration",
        'Accept-Encoding': 'gzip, deflate',
        'Accept': '*/*',
        'Connection': 'keep-alive',
        'Authorization': f'Basic {API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # The exact URL that worked in the logs
    url = "https://apigw.trendyol.com/integration/product/product-categories"
    
    logger.info(f"Making request to URL: {url}")
    logger.info(f"With headers: {pformat(headers)}")
    
    try:
        # Make the request exactly as it was made in the logs
        response = requests.get(url, headers=headers)
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("Success! Response received.")
            data = response.json()
            if 'categories' in data:
                logger.info(f"Found {len(data['categories'])} categories")
                # Print a few categories
                for i, category in enumerate(data['categories'][:3]):
                    logger.info(f"Category {i+1}: {category['name']} (ID: {category['id']})")
            return True
        else:
            logger.error(f"Failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error making request: {str(e)}")
        return False

def test_product_submission():
    """Test product submission with the working API format."""
    logger.info("Testing product submission with working API format")
    
    # Get a product to submit
    product = TrendyolProduct.objects.filter(batch_status='pending').first()
    if not product:
        logger.error("No pending products found")
        return False
    
    logger.info(f"Found product: {product.id} - {product.title[:50]}")
    
    # Define headers exactly as they appear in the logs for the working API call
    headers = {
        'User-Agent': f"{SELLER_ID} - SelfIntegration",
        'Accept-Encoding': 'gzip, deflate',
        'Accept': '*/*',
        'Connection': 'keep-alive',
        'Authorization': f'Basic {API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # Prepare product payload
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
    }
    
    # The base URL that worked in the logs
    base_url = "https://apigw.trendyol.com/integration/product"
    
    # Try different product submission endpoints
    endpoints = [
        f"/sellers/{SELLER_ID}/products",
        f"/suppliers/{SELLER_ID}/products",
        f"/v2/suppliers/{SELLER_ID}/products"
    ]
    
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        logger.info(f"Submitting to URL: {url}")
        logger.info(f"With payload: {pformat(payload)}")
        
        try:
            # Make the request
            response = requests.post(url, json=payload, headers=headers)
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response: {response.text}")
            
            if response.status_code == 200:
                try:
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
                except Exception as json_error:
                    logger.error(f"Error parsing response JSON: {str(json_error)}")
            elif response.status_code == 400:
                # Try to parse error details
                try:
                    error_data = response.json()
                    logger.error(f"Error details: {pformat(error_data)}")
                except:
                    pass
        except Exception as e:
            logger.error(f"Error with URL {url}: {str(e)}")
    
    logger.error("All URL combinations failed")
    return False

def main():
    """Run all tests."""
    logger.info("Starting debug of working API calls")
    
    # First, test the product categories endpoint that works in the logs
    categories_success = test_product_categories()
    
    if categories_success:
        logger.info("Successfully connected to product categories API")
        
        # Now try product submission
        submission_success = test_product_submission()
        
        if submission_success:
            logger.info("Product submission successful!")
        else:
            logger.error("Product submission failed")
    else:
        logger.error("Failed to connect to product categories API")
    
    logger.info("Tests completed")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()