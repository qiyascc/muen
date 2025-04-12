"""
Script to debug Trendyol API with a minimal payload.

This script uses direct API requests with a very simple payload to debug
exactly what's causing the 400 Bad Request errors from Trendyol API.

Run this script with: python manage.py shell < debug_minimal_payload.py
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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig

def make_direct_api_request():
    """
    Make a direct API request to Trendyol API with a minimal payload.
    """
    print("\n===== TESTING DIRECT API REQUEST WITH MINIMAL PAYLOAD =====\n")
    
    try:
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
        
        # Create a very simple product payload 
        test_payload = {
            "items": [
                {
                    "barcode": "test123456",
                    "title": "Test Product",
                    "productMainId": "test123456",
                    "brandId": 102,
                    "categoryId": 1081, 
                    "quantity": 10,
                    "stockCode": "test123456",
                    "description": "Test product description",
                    "currencyType": "TRY",
                    "listPrice": 100.0,
                    "salePrice": 100.0,
                    "vatRate": 10,
                    "cargoCompanyId": 17,
                    "shipmentAddressId": 5526789,  # Using the actual shipment address ID we found
                    "returningAddressId": 5526791, # Using the actual returning address ID we found
                    "images": [{"url": "https://www.lcwaikiki.com/static/images/logo.svg"}],
                    "attributes": [
                        {
                            "attributeId": 338,
                            "attributeValueId": 4290
                        },
                        {
                            "attributeId": 346,
                            "attributeValueId": 4761
                        },
                        {
                            "attributeId": 47,     # Color attribute from API output
                            "attributeValueId": 7011
                        },
                        {
                            "attributeId": 22,     # Another attribute seen in API output
                            "attributeValueId": 253
                        }
                    ]
                }
            ]
        }
        
        print("\nUsing the following payload:")
        print(json.dumps(test_payload, indent=2))
        
        # Construct the endpoint
        endpoint = f"product/sellers/{config.seller_id}/products"
        url = f"{config.base_url.rstrip('/')}/{endpoint}"
        print(f"\nEndpoint URL: {url}")
        
        # Make the request
        print("\nSending direct request to Trendyol API...")
        headers = {
            "Authorization": f"Basic {auth_token}",
            "User-Agent": config.user_agent or f"{config.seller_id} - SelfIntegration",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        print(f"Headers:")
        for key, value in headers.items():
            print(f"- {key}: {value}")
        
        response = requests.post(url, headers=headers, json=test_payload)
        
        print(f"\nResponse Status Code: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            print(f"- {key}: {value}")
        
        print(f"\nResponse Content:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
        except:
            print(response.text)
        
        # If there's an error, let's try to get more detailed error information
        if response.status_code >= 400:
            print("\nAttempting to get more detailed error information...")
            try:
                # Try to get error details from the response
                error_details = response.json()
                if "errors" in error_details and isinstance(error_details["errors"], list):
                    for i, error in enumerate(error_details["errors"]):
                        print(f"Error {i+1}:")
                        print(json.dumps(error, indent=2))
            except:
                print("Could not extract detailed error information.")
        
        # Try alternative URL formats
        print("\n\n===== TESTING ALTERNATIVE API URL FORMATS =====")
        alt_urls = [
            "https://api.trendyol.com/sapigw",
            "https://api.trendyol.com/sapigw/",
            "https://api.trendyol.com/sapigw/suppliers/{}/products".format(config.seller_id),
            # Add more alternatives if needed
        ]
        
        for alt_url in alt_urls:
            if alt_url.endswith("products"):
                full_url = alt_url
            else:
                full_url = f"{alt_url.rstrip('/')}/{endpoint}"
            
            print(f"\nTrying alternative URL: {full_url}")
            
            try:
                alt_response = requests.post(full_url, headers=headers, json=test_payload)
                
                print(f"Response Status Code: {alt_response.status_code}")
                print(f"Response Content:")
                try:
                    alt_response_json = alt_response.json()
                    print(json.dumps(alt_response_json, indent=2))
                except:
                    print(alt_response.text)
            except Exception as e:
                print(f"Error: {str(e)}")
        
        return True
    except Exception as e:
        print(f"Error during direct API request: {str(e)}")
        traceback.print_exc()
        return False

def test_brand_api():
    """
    Test the brand API to verify API access is working correctly.
    """
    print("\n===== TESTING BRAND API ACCESS =====\n")
    
    try:
        # Get API configuration
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            print("ERROR: No active Trendyol API configuration found!")
            return False
        
        # Generate auth token
        auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
        
        # Construct the endpoint
        endpoint = "product/brands"
        url = f"{config.base_url.rstrip('/')}/{endpoint}"
        print(f"Brand API URL: {url}")
        
        # Make the request
        print("Sending request to Brand API...")
        headers = {
            "Authorization": f"Basic {auth_token}",
            "User-Agent": config.user_agent or f"{config.seller_id} - SelfIntegration",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS! Brand API is accessible.")
            data = response.json()
            if isinstance(data, list):
                print(f"Received {len(data)} brands")
                if data:
                    print("First 3 brands:")
                    for i, brand in enumerate(data[:3]):
                        print(f"{i+1}. {brand.get('name')} (ID: {brand.get('id')})")
            else:
                print(f"Unexpected response format: {type(data)}")
        else:
            print(f"FAILED! Brand API returned status code {response.status_code}")
            print(f"Response: {response.text}")
        
        return True
    except Exception as e:
        print(f"Error testing Brand API: {str(e)}")
        traceback.print_exc()
        return False

def check_seller_api():
    """
    Check if we can access the seller's own information.
    """
    print("\n===== CHECKING SELLER API ACCESS =====\n")
    
    try:
        # Get API configuration
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            print("ERROR: No active Trendyol API configuration found!")
            return False
        
        # Generate auth token
        auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
        
        # Try different seller endpoints
        endpoints = [
            f"suppliers/{config.seller_id}/addresses",
            f"suppliers/{config.seller_id}",
            f"suppliers/{config.seller_id}/products",
            f"sellers/{config.seller_id}/addresses",
            f"sellers/{config.seller_id}",
            f"sellers/{config.seller_id}/products"
        ]
        
        base_urls = [
            config.base_url,
            "https://api.trendyol.com/sapigw"
        ]
        
        for base_url in base_urls:
            for endpoint in endpoints:
                url = f"{base_url.rstrip('/')}/{endpoint}"
                print(f"\nTrying URL: {url}")
                
                # Make the request
                headers = {
                    "Authorization": f"Basic {auth_token}",
                    "User-Agent": config.user_agent or f"{config.seller_id} - SelfIntegration",
                    "Accept": "application/json"
                }
                
                try:
                    # Try GET first
                    response = requests.get(url, headers=headers)
                    
                    print(f"GET - Status Code: {response.status_code}")
                    if response.status_code < 400:
                        print("SUCCESS!")
                        try:
                            data = response.json()
                            print(json.dumps(data, indent=2)[:1000])  # Limit output length
                        except:
                            print(response.text[:1000])  # Limit output length
                    else:
                        print(f"Response: {response.text[:500]}")  # Limit output length
                except Exception as e:
                    print(f"Error: {str(e)}")
        
        return True
    except Exception as e:
        print(f"Error checking Seller API: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n===== TRENDYOL API DEBUG WITH MINIMAL PAYLOAD =====\n")
    
    try:
        # Test basic brand API access first to verify credentials
        brand_api_test = test_brand_api()
        
        # Check seller API endpoints
        seller_api_test = check_seller_api()
        
        # Make direct API request with minimal payload
        direct_api_test = make_direct_api_request()
        
        print("\n===== DEBUG SUMMARY =====")
        print(f"Brand API test: {'SUCCESS' if brand_api_test else 'FAILED'}")
        print(f"Seller API test: {'SUCCESS' if seller_api_test else 'FAILED'}")
        print(f"Direct API test: {'COMPLETED' if direct_api_test else 'FAILED'}")
        
    except Exception as e:
        print(f"Error running debug script: {str(e)}")
        traceback.print_exc()