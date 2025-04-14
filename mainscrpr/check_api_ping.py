#!/usr/bin/env python
"""
Simple script to check various Trendyol API endpoints directly.
This will attempt to make a more direct request to check if the API is accessible.
"""

import os
import sys
import json
import base64
import requests
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configure API details
API_KEY = "qSohKkLKPWwDeSKjwz8R"
API_SECRET = "yYF3Ycl9B6Vjs77q3MhE" 
SUPPLIER_ID = "535623"
BASE_URL = "https://apigw.trendyol.com"

def check_endpoint(endpoint, method="GET", params=None, data=None):
    """Check if an endpoint is accessible"""
    url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    
    # Format the auth string and encode as Base64 for Basic Authentication
    auth_string = f"{API_KEY}:{API_SECRET}"
    auth_encoded = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        'Authorization': f"Basic {auth_encoded}",
        'Content-Type': 'application/json',
        'User-Agent': f"{SUPPLIER_ID} - SelfIntegration",
    }
    
    logger.info(f"Testing endpoint: {url}")
    logger.info(f"Method: {method}")
    logger.info(f"Headers: {headers}")
    
    if params:
        logger.info(f"Params: {params}")
    
    if data:
        logger.info(f"Data: {data}")
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data,
            timeout=30
        )
        
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        
        if response.text:
            try:
                # Try to parse and format JSON response
                response_json = json.loads(response.text)
                logger.info(f"Response JSON: {json.dumps(response_json, indent=2)[:2000]}")
            except:
                # If not JSON, log as text
                logger.info(f"Response text: {response.text[:2000]}")
        
        return response.status_code < 400
    except Exception as e:
        logger.error(f"Error checking endpoint {url}: {str(e)}")
        return False

def main():
    """Check various API endpoints"""
    logger.info("Starting Trendyol API check")
    
    # Test endpoints - from simplest to more complex
    tests = [
        {
            "name": "Brand API",
            "endpoint": "integration/product/brands",
            "method": "GET",
            "params": {"page": 0, "size": 10},
        },
        {
            "name": "Categories API",
            "endpoint": "integration/product/product-categories",
            "method": "GET",
        },
        {
            "name": "Supplier Products API",
            "endpoint": f"integration/product/sellers/{SUPPLIER_ID}/products",
            "method": "GET",
            "params": {"page": 0, "size": 10},
        },
        {
            "name": "Health Check",
            "endpoint": "health",
            "method": "GET",
        },
    ]
    
    results = []
    for test in tests:
        name = test["name"]
        logger.info(f"\n\nTesting {name}...")
        success = check_endpoint(
            test["endpoint"], 
            test["method"], 
            test.get("params"), 
            test.get("data")
        )
        results.append({"name": name, "success": success})
    
    # Print summary
    logger.info("\n\nAPI Check Summary:")
    for result in results:
        status = "SUCCESS" if result["success"] else "FAILED"
        logger.info(f"{result['name']}: {status}")
    
    return any(r["success"] for r in results)

if __name__ == "__main__":
    success = main()
    if not success:
        logger.error("All API tests failed. Please check your API credentials and connectivity.")
    sys.exit(0 if success else 1)