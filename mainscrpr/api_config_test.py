"""
Script to test Trendyol API authentication and connection configuration.

This script tests various authentication and connection options to help determine the root cause
of the 400 Bad Request errors in the Trendyol API client.

Run this script with: python manage.py shell < api_config_test.py
"""

import django
import os
import sys
import json
import logging
import requests
import base64
import time
from pprint import pprint
import traceback
from urllib.parse import quote

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI

def test_trendyol_api_auth():
    """Test Trendyol API authentication and configuration"""
    print("Testing Trendyol API authentication and configuration...")
    
    # Get API configuration
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("ERROR: No active Trendyol API configuration found!")
        return False
    
    print(f"API Config:")
    print(f"- Base URL: {config.base_url}")
    print(f"- Seller ID: {config.seller_id}")
    print(f"- API Key: {config.api_key}")
    print(f"- API Secret: {config.api_secret}")
    print(f"- User Agent: {config.user_agent}")
    
    # Generate auth token
    auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
    print(f"- Auth Token: {auth_token}")
    
    # Test with different URL formats and auth setups
    test_variations = [
        {
            "name": "Standard Configuration",
            "base_url": config.base_url,
            "headers": {
                "Authorization": f"Basic {auth_token}",
                "User-Agent": config.user_agent or f"{config.seller_id} - SelfIntegration",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        },
        {
            "name": "Integration URL",
            "base_url": "https://apigw.trendyol.com/integration/",
            "headers": {
                "Authorization": f"Basic {auth_token}",
                "User-Agent": config.user_agent or f"{config.seller_id} - SelfIntegration",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        },
        {
            "name": "SAPIGW URL",
            "base_url": "https://api.trendyol.com/sapigw/",
            "headers": {
                "Authorization": f"Basic {auth_token}",
                "User-Agent": config.user_agent or f"{config.seller_id} - SelfIntegration",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        },
        {
            "name": "Simple Auth Headers",
            "base_url": config.base_url,
            "headers": {
                "Authorization": f"Basic {auth_token}"
            }
        },
        {
            "name": "API Key + Secret in URL",
            "base_url": config.base_url,
            "headers": {},
            "auth": (config.api_key, config.api_secret)
        },
        {
            "name": "HTTP header names as lowercase",
            "base_url": config.base_url,
            "headers": {
                "authorization": f"Basic {auth_token}",
                "user-agent": config.user_agent or f"{config.seller_id} - SelfIntegration",
                "accept": "application/json",
                "content-type": "application/json"
            }
        }
    ]
    
    # Perform tests
    for test in test_variations:
        print(f"\n==== Testing: {test['name']} ====")
        
        # Test with basic endpoints
        endpoints_to_test = [
            "product/brands", 
            f"product/brands/by-name?name={quote('LC Waikiki')}"
        ]
        
        for endpoint in endpoints_to_test:
            endpoint_url = f"{test['base_url'].rstrip('/')}/{endpoint}"
            print(f"\nTesting endpoint: {endpoint_url}")
            try:
                # Add delay to avoid rate limiting
                time.sleep(1)
                
                # Make request
                if 'auth' in test:
                    response = requests.get(endpoint_url, headers=test['headers'], auth=test['auth'])
                else:
                    response = requests.get(endpoint_url, headers=test['headers'])
                
                print(f"Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    print("✅ SUCCESS!")
                    try:
                        # Try to parse response as JSON
                        data = response.json()
                        if isinstance(data, list):
                            print(f"  - Response is a list with {len(data)} items")
                            if data:
                                print(f"  - First item: {data[0]}")
                        else:
                            print(f"  - Response: {data}")
                    except Exception as e:
                        print(f"  - Could not parse response as JSON: {e}")
                        print(f"  - Raw response: {response.text[:200]}...")
                else:
                    print("❌ FAILED!")
                    print(f"Headers: {response.headers}")
                    print(f"Response: {response.text}")
            except Exception as e:
                print(f"❌ ERROR: {str(e)}")
    
    # Test creating a product
    print("\n\n==== Testing Product Creation ====")
    api_client = get_api_client_from_config()
    
    # Get a sample product
    test_product = TrendyolProduct.objects.first()
    if not test_product:
        print("No products found to test")
        return False
    
    # Create a very simple product payload
    test_payload = {
        "items": [
            {
                "barcode": "test123456",
                "title": "Test Product",
                "productMainId": "test123456",
                "brandId": 102,  # LC Waikiki brand ID
                "categoryId": 1000,  # Some valid category ID (might need to be changed)
                "quantity": 10,
                "stockCode": "test123456",
                "description": "Test product description",
                "currencyType": "TRY",
                "listPrice": 100.0,
                "salePrice": 100.0,
                "vatRate": 10,
                "cargoCompanyId": 17,
                "images": [{"url": "https://cdn.dsmcdn.com/mnresize/1200/1800/ty148/product/media/images/20210818/15/119273414/220496312/1/1_org_zoom.jpg"}],
                "attributes": [
                    {
                        "attributeId": 338,
                        "attributeValueId": 4290
                    },
                    {
                        "attributeId": 346,
                        "attributeValueId": 4761
                    }
                ]
            }
        ]
    }
    
    endpoint = f"product/sellers/{api_client.config.seller_id}/products"
    print(f"Testing creation with endpoint: {endpoint}")
    print(f"Using payload:\n{json.dumps(test_payload, indent=2)}")
    
    try:
        response = api_client.post(endpoint, test_payload)
        print(f"✅ SUCCESS! Response: {response}")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        
        # Try to extract more error details
        if hasattr(e, 'response') and hasattr(e.response, 'content'):
            try:
                error_details = json.loads(e.response.content)
                print("Error details:")
                pprint(error_details)
            except:
                print(f"Raw error response: {e.response.content}")
    
    # Test with direct requests
    print("\n==== Testing direct request to product creation endpoint ====")
    direct_url = f"{api_client.config.base_url.rstrip('/')}/{endpoint}"
    headers = {
        "Authorization": f"Basic {auth_token}",
        "User-Agent": config.user_agent or f"{config.seller_id} - SelfIntegration",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(direct_url, headers=headers, json=test_payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code in (200, 201, 202):
            print("✅ SUCCESS!")
            print(f"Response: {response.json()}")
        else:
            print("❌ FAILED!")
            print(f"Headers: {response.headers}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

if __name__ == "__main__":
    print("\n===== TRENDYOL API AUTHENTICATION TESTS =====\n")
    
    try:
        test_trendyol_api_auth()
    except Exception as e:
        print(f"Error running tests: {str(e)}")
        traceback.print_exc()