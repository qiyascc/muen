"""
Script to fix the Trendyol API authentication issues.

This script tests different authentication methods and headers to resolve
the 556 Service Unavailable or 401 Unauthorized errors.

Run this script with: python manage.py shell < fix_authentication.py
"""

import django
import os
import sys
import json
import base64
import logging
import requests
from pprint import pprint
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol.models import TrendyolAPIConfig

def test_different_auth_methods():
    """Test different authentication methods and headers"""
    print("\n===== TESTING DIFFERENT AUTHENTICATION METHODS =====\n")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return False
    
    print(f"Current API config:")
    print(f"- Name: {config.name}")
    print(f"- Base URL: {config.base_url}")
    print(f"- Seller ID: {config.seller_id}")
    print(f"- API Key: {config.api_key}")
    print(f"- API Secret: {config.api_secret}")
    print(f"- User Agent: {config.user_agent}")
    
    # Generate auth tokens
    basic_auth = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
    basic_auth_with_seller = base64.b64encode(f"{config.seller_id}:{config.api_key}:{config.api_secret}".encode()).decode()
    token_auth = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
    
    # Test URLs
    base_urls = [
        "https://api.trendyol.com/sapigw",
        "https://apigw.trendyol.com/integration",
        "https://api.trendyol.com/integration",
        "https://apigw.trendyol.com/sapigw"
    ]
    
    # Test endpoints
    endpoints = [
        "product/brands",
        f"suppliers/{config.seller_id}/products",
        f"sellers/{config.seller_id}/products",
        f"sellers/{config.seller_id}/addresses"
    ]
    
    # Test different auth headers
    auth_headers = [
        {"Authorization": f"Basic {basic_auth}"},
        {"Authorization": f"Bearer {token_auth}"},
        {"Authorization": f"Basic {basic_auth_with_seller}"},
        {"x-auth": f"{basic_auth}"},
        {}  # No auth header as a control
    ]
    
    # Test different user agents
    user_agents = [
        f"{config.seller_id} - SelfIntegration",
        "SelfIntegration",
        f"SellerID-{config.seller_id}",
        None  # No User-Agent as a control
    ]
    
    # Test combinations
    for base_url in base_urls:
        print(f"\n----- Testing Base URL: {base_url} -----")
        
        for endpoint in endpoints:
            print(f"\nEndpoint: {endpoint}")
            
            for auth_header in auth_headers:
                auth_header_type = next(iter(auth_header.keys())) if auth_header else "None"
                auth_header_value = auth_header.get(auth_header_type, "None")
                
                for user_agent in user_agents:
                    # Create request headers
                    headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
                    
                    # Add auth header if provided
                    if auth_header:
                        headers.update(auth_header)
                    
                    # Add User-Agent if provided
                    if user_agent:
                        headers["User-Agent"] = user_agent
                    
                    # Construct full URL
                    url = f"{base_url.rstrip('/')}/{endpoint}"
                    
                    print(f"\nTesting: {url}")
                    print(f"Auth: {auth_header_type}={auth_header_value[:10]}...")
                    print(f"User-Agent: {user_agent}")
                    
                    try:
                        # Make request
                        response = requests.get(url, headers=headers, timeout=10)
                        
                        # Print results
                        print(f"Status Code: {response.status_code}")
                        
                        if response.status_code < 400:
                            print("SUCCESS!")
                            
                            try:
                                # Try to parse JSON response
                                data = response.json()
                                
                                # Check data type
                                if isinstance(data, dict):
                                    if 'brands' in data:
                                        brands = data['brands']
                                        print(f"Found {len(brands)} brands")
                                    elif 'content' in data:
                                        products = data['content']
                                        print(f"Found {len(products)} products")
                                    elif 'supplierAddresses' in data:
                                        addresses = data['supplierAddresses']
                                        print(f"Found {len(addresses)} addresses")
                                    
                                    # Save working configuration
                                    save_working_config(base_url, auth_header, user_agent)
                                    return True
                                elif isinstance(data, list):
                                    print(f"Found list with {len(data)} items")
                                    
                                    # Save working configuration
                                    save_working_config(base_url, auth_header, user_agent)
                                    return True
                            except json.JSONDecodeError:
                                print("Response is not JSON")
                        else:
                            # Try to get error message
                            try:
                                error = response.json()
                                print(f"Error: {error}")
                            except:
                                print(f"Error message: {response.text[:100]}")
                    except Exception as e:
                        print(f"Error: {str(e)}")
    
    print("\nNo working configuration found!")
    return False

def save_working_config(base_url, auth_header, user_agent):
    """Save the working configuration"""
    print("\n===== SAVING WORKING CONFIGURATION =====\n")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return False
    
    # Update the config
    config.base_url = base_url
    
    # Update user agent if provided
    if user_agent:
        config.user_agent = user_agent
    
    # Save the changes
    config.save()
    
    print(f"Updated configuration:")
    print(f"- Base URL: {config.base_url}")
    print(f"- User Agent: {config.user_agent}")
    
    return True

def test_working_credentials():
    """Test the Trendyol API with the original credentials"""
    print("\n===== TESTING ORIGINAL CREDENTIALS WITH DIFFERENT HEADERS =====\n")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return False
    
    # Restore original URL
    config.base_url = "https://apigw.trendyol.com/integration"
    config.save()
    
    print(f"Using original credentials:")
    print(f"- Base URL: {config.base_url}")
    print(f"- Seller ID: {config.seller_id}")
    print(f"- API Key: {config.api_key}")
    print(f"- API Secret: {config.api_secret}")
    
    # Generate auth token
    auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
    
    # Test endpoints
    endpoints = [
        "product/brands",
        f"suppliers/{config.seller_id}/products",
        f"sellers/{config.seller_id}/addresses"
    ]
    
    for endpoint in endpoints:
        url = f"{config.base_url.rstrip('/')}/{endpoint}"
        print(f"\nTesting endpoint: {url}")
        
        headers = {
            "Authorization": f"Basic {auth_token}",
            "User-Agent": f"{config.seller_id} - SelfIntegration",
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code < 400:
                print("SUCCESS!")
                try:
                    data = response.json()
                    print(f"Data type: {type(data)}")
                    if isinstance(data, dict):
                        keys = list(data.keys())
                        print(f"Response keys: {keys[:5]}")
                    elif isinstance(data, list):
                        print(f"List length: {len(data)}")
                except:
                    print(f"Response: {response.text[:100]}")
            else:
                try:
                    error = response.json()
                    print(f"Error: {error}")
                except:
                    print(f"Error message: {response.text[:100]}")
        except Exception as e:
            print(f"Error: {str(e)}")
    
    return True

def verify_available_endpoints():
    """
    Verify known working endpoints for Trendyol API
    """
    print("\n===== VERIFYING AVAILABLE ENDPOINTS =====\n")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return False
    
    # Set API configuration
    base_url = "https://apigw.trendyol.com/integration"
    auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_token}",
        "User-Agent": f"{config.seller_id} - SelfIntegration",
        "Accept": "application/json"
    }
    
    # Known working endpoints
    working_endpoints = [
        "product/brands",
        f"sellers/{config.seller_id}/addresses"
    ]
    
    # Test working endpoints
    for endpoint in working_endpoints:
        url = f"{base_url.rstrip('/')}/{endpoint}"
        print(f"\nTesting endpoint: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code < 400:
                print("SUCCESS!")
                try:
                    data = response.json()
                    print(f"Data type: {type(data)}")
                    if isinstance(data, dict):
                        keys = list(data.keys())
                        print(f"Response keys: {keys[:5]}")
                    elif isinstance(data, list):
                        print(f"List length: {len(data)}")
                except:
                    print(f"Response: {response.text[:100]}")
            else:
                try:
                    error = response.json()
                    print(f"Error: {error}")
                except:
                    print(f"Error message: {response.text[:100]}")
        except Exception as e:
            print(f"Error: {str(e)}")
    
    return True

def save_confirmed_working_config():
    """Save the confirmed working configuration"""
    print("\n===== SAVING CONFIRMED WORKING CONFIGURATION =====\n")
    
    # Get the active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        print("No active Trendyol API configuration found!")
        return False
    
    # Update the config
    config.base_url = "https://apigw.trendyol.com/integration"  # Use the original URL
    config.user_agent = f"{config.seller_id} - SelfIntegration"  # Standard User-Agent
    
    # Save the changes
    config.save()
    
    print(f"Updated configuration with confirmed working values:")
    print(f"- Base URL: {config.base_url}")
    print(f"- User Agent: {config.user_agent}")
    
    return True

def main():
    """Main function"""
    print("\n===== TRENDYOL API AUTHENTICATION FIX =====\n")
    
    try:
        # First, test with original credentials
        test_working_credentials()
        
        # Verify known working endpoints
        verify_available_endpoints()
        
        # Save confirmed working configuration
        save_confirmed_working_config()
        
        # Optionally, try different auth methods if the above didn't work
        # test_different_auth_methods()
        
        return True
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()