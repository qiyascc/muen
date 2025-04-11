import os
import django
import json
import base64
import requests
from loguru import logger

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Now import the models and functions
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.api_client import get_api_client


def fix_trendyol_api_client():
    """
    Check and fix the Trendyol API client configuration
    """
    # First, check if we have any API configs
    configs = TrendyolAPIConfig.objects.all()
    active_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    
    print(f"Found {configs.count()} API configurations in database")
    if active_config:
        print(f"Active configuration: {active_config.name}")
        
        # Create auth string (Basic Authentication)
        auth_string = f"{active_config.api_key}:{active_config.api_secret}"
        encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        
        # Test with direct API call
        headers = {
            'Authorization': f'Basic {encoded_auth}',
            'User-Agent': active_config.user_agent,
            'Content-Type': 'application/json'
        }
        
        # Print current headers for debugging
        print("\nCurrent API Headers:")
        for key, value in headers.items():
            if key == 'Authorization':
                print(f"  {key}: Basic {encoded_auth[:10]}...")
            else:
                print(f"  {key}: {value}")
        
        # Attempt to get brands (simple API call)
        # First, let's try to get categories (general API call)
        categories_url = "https://api.trendyol.com/sapigw/product-categories"
        
        try:
            print(f"\nTesting API connection to: {categories_url}")
            response = requests.get(categories_url, headers=headers)
            
            if response.status_code != 200:
                # Try alternative URL structure based on Trendyol documentation
                brands_url = f"https://api.trendyol.com/sapigw/suppliers/{active_config.supplier_id}/brands"
                print(f"\nFirst URL failed, trying alternative URL: {brands_url}")
                response = requests.get(brands_url, headers=headers)
            
            if response.status_code == 200:
                print(f"\n✅ Success! Direct API connection established.")
                brands_data = response.json()
                print(f"Retrieved {len(brands_data)} brands from Trendyol API")
                
                # Now test using our get_api_client function
                client = get_api_client()
                if client:
                    print("\n✅ API client initialized successfully")
                    
                    # Check our failed products
                    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
                    if failed_products:
                        print(f"\nFound {failed_products.count()} failed products")
                        latest_failed = failed_products.last()
                        print(f"Latest failed product: {latest_failed.title}")
                        print(f"Error message: {latest_failed.status_message}")
                    else:
                        print("\nNo failed products found in database")
                else:
                    print("\n❌ Error: get_api_client() returned None")
            else:
                print(f"\n❌ API connection failed with status code {response.status_code}")
                print(f"Error: {response.text}")
                
                if response.status_code == 401:
                    print("\nAuthentication failed. Please check your API credentials.")
                    
                    # Get expected format
                    print("\nExpected format for API credentials:")
                    print("Supplier ID: Your supplier ID in Trendyol (e.g., 535623)")
                    print("API Key: Your API key from Trendyol seller panel")
                    print("API Secret: Your API secret from Trendyol seller panel")
                    print("User Agent: Should be in format '{supplier_id} - SelfIntegration' or '{supplier_id} - {EntegratorName}'")
                
                elif response.status_code == 403:
                    print("\nAccess forbidden. Please check your User-Agent header.")
                    print(f"Current User-Agent: {active_config.user_agent}")
                    print(f"Expected format: '{active_config.supplier_id} - SelfIntegration'")
                
                elif response.status_code == 429:
                    print("\nToo many requests. Trendyol API has a limit of 50 requests per 10 seconds.")
        
        except Exception as e:
            print(f"\n❌ Error connecting to Trendyol API: {str(e)}")
    else:
        print("\n❌ No active API configuration found!")
        print("Please run python api_config_test.py to set up a new configuration")


if __name__ == "__main__":
    fix_trendyol_api_client()