#!/usr/bin/env python
"""
Script to test Trendyol API authentication with specific headers.

This script tests various header configurations to identify the correct format
that Trendyol's API expects, which might help resolve the 556 Server Error issues.

Run this script with: python manage.py shell < test_trendyol_auth.py
"""
import os
import sys
import json
import base64
import logging
import requests
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
import django
django.setup()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('trendyol_auth_test')

# Trendyol API credentials
API_KEY = "qSohKkLKPWwDeSKjwz8R"
API_SECRET = "yYF3Ycl9B6Vjs77q3MhE"
SELLER_ID = "535623"
BASE_URL = "https://api.trendyol.com/sapigw"

def generate_auth_token(api_key, api_secret):
    """Generate base64 encoded auth token"""
    auth_string = f"{api_key}:{api_secret}"
    auth_bytes = auth_string.encode('ascii')
    base64_bytes = base64.b64encode(auth_bytes)
    base64_string = base64_bytes.decode('ascii')
    return base64_string

def test_auth_with_headers(endpoint, headers, params=None):
    """Test authentication with specific headers"""
    url = f"{BASE_URL}{endpoint}"
    
    logger.info(f"Testing endpoint: {url}")
    logger.info(f"With headers: {json.dumps(headers, indent=2)}")
    
    if params:
        logger.info(f"With params: {json.dumps(params, indent=2)}")
    
    try:
        response = requests.get(url, headers=headers, params=params)
        status_code = response.status_code
        
        logger.info(f"Response status: {status_code}")
        
        if status_code == 200:
            logger.info("Authentication successful!")
            try:
                response_json = response.json()
                logger.info(f"Response: {json.dumps(response_json, indent=2)[:500]}...")
            except:
                logger.info(f"Raw response: {response.text[:500]}...")
            return True
        else:
            logger.error(f"Authentication failed with status code: {status_code}")
            logger.error(f"Response: {response.text[:500]}...")
            return False
    
    except Exception as e:
        logger.error(f"Error testing authentication: {str(e)}")
        return False

def test_auth_variations():
    """Test different authentication header variations"""
    # Generate auth token
    auth_token = generate_auth_token(API_KEY, API_SECRET)
    logger.info(f"Generated auth token: {auth_token}")
    
    # Create standard headers
    standard_headers = {
        "Authorization": f"Basic {auth_token}",
        "User-Agent": f"{SELLER_ID} - SelfIntegration",
        "Content-Type": "application/json"
    }
    
    # Try more endpoint variations to see if any are accessible
    endpoints = [
        # Product related endpoints
        "/product/brands",
        "/product-categories",
        f"/sellers/{SELLER_ID}/products",
        f"/integration/product/sellers/{SELLER_ID}/products",
        
        # Supplier related endpoints
        "/suppliers/brands",
        f"/suppliers/{SELLER_ID}/brands",
        f"/suppliers/{SELLER_ID}/addresses",
        
        # Other possible endpoints
        "/filters",
        "/healthcheck",
        "/version",
        
        # Different endpoint structures
        "/integration/api/brands",
        "/api/brands",
        "/v1/brands",
        "/v2/brands"
    ]
    
    # Try each endpoint with standard headers
    for endpoint in endpoints:
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing endpoint: {endpoint}")
        logger.info(f"{'='*50}")
        
        success = test_auth_with_headers(endpoint, standard_headers, params={"page": 0, "size": 5})
        
        if success:
            logger.info(f"Endpoint {endpoint} is accessible!")
        else:
            # Try different HTTP methods for verification endpoints
            if endpoint in ["/healthcheck", "/version"]:
                logger.info("Trying without parameters...")
                success = test_auth_with_headers(endpoint, standard_headers)
                
                if success:
                    logger.info(f"Endpoint {endpoint} is accessible without parameters!")
                else:
                    logger.info(f"Endpoint {endpoint} is not accessible")
            else:
                logger.info(f"Endpoint {endpoint} is not accessible")

def main():
    """Main function"""
    logger.info("Starting Trendyol authentication test")
    test_auth_variations()
    logger.info("Authentication test completed")

if __name__ == "__main__":
    main()
else:
    # When running as a Django shell script
    main()