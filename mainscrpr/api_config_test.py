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
from trendyol.models import TrendyolAPIConfig

def test_trendyol_api_auth():
    """Test Trendyol API authentication and configuration"""
    
    # Check existing configurations
    configs = TrendyolAPIConfig.objects.all()
    print(f"Found {configs.count()} API configurations in database:")
    
    for config in configs:
        print(f"\nConfiguration: {config.name}")
        print(f"  Active: {'Yes' if config.is_active else 'No'}")
        print(f"  Supplier ID: {config.supplier_id}")
        print(f"  API Key: {config.api_key[:4]}...{config.api_key[-4:] if len(config.api_key) > 8 else ''}")
        print(f"  API Secret: {config.api_secret[:4]}...{config.api_secret[-4:] if len(config.api_secret) > 8 else ''}")
        print(f"  User Agent: {config.user_agent}")
    
    # Ask for new configuration
    print("\n=== Trendyol API Configuration Test ===")
    print("Enter your Trendyol API credentials (found in seller panel under 'Account Info' -> 'Integration Info'):")
    
    supplier_id = input("Supplier ID: ").strip()
    api_key = input("API Key: ").strip()
    api_secret = input("API Secret: ").strip()
    
    # Validate inputs
    if not supplier_id or not api_key or not api_secret:
        print("Error: All fields are required")
        return
    
    # Create user agent
    user_agent = f"{supplier_id} - SelfIntegration"
    
    # Create auth string (Basic Authentication)
    auth_string = f"{api_key}:{api_secret}"
    encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    
    # Now test the API
    print("\nTesting API connection...")
    
    # Headers for the API request
    headers = {
        'Authorization': f'Basic {encoded_auth}',
        'User-Agent': user_agent,
        'Content-Type': 'application/json'
    }
    
    # Attempt to get brands (simple API call)
    brands_url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/brands"
    
    try:
        response = requests.get(brands_url, headers=headers)
        
        if response.status_code == 200:
            brands_data = response.json()
            print(f"\n✅ Success! API connection established.")
            print(f"Retrieved {len(brands_data)} brands from Trendyol API")
            
            # Show first 5 brands as a sample
            if brands_data:
                print("\nSample brands:")
                for brand in brands_data[:5]:
                    print(f"  • {brand.get('name')} (ID: {brand.get('id')})")
            
            # Ask to save this configuration
            save_config = input("\nDo you want to save this configuration? (Y/n): ").strip().lower()
            
            if save_config != 'n':
                # Check if we should set this as active
                set_active = input("Set this configuration as the active one? (Y/n): ").strip().lower()
                is_active = set_active != 'n'
                
                # If setting as active, deactivate other configs
                if is_active:
                    TrendyolAPIConfig.objects.filter(is_active=True).update(is_active=False)
                
                # Create new config
                config_name = input("Enter a name for this configuration (e.g., 'Production'): ").strip()
                if not config_name:
                    config_name = "Trendyol API Config"
                
                config = TrendyolAPIConfig(
                    name=config_name,
                    supplier_id=supplier_id,
                    api_key=api_key,
                    api_secret=api_secret,
                    user_agent=user_agent,
                    is_active=is_active
                )
                config.save()
                
                print(f"\n✅ Configuration '{config_name}' saved successfully!")
                if is_active:
                    print("✅ This configuration is now the active one.")
        else:
            print(f"\n❌ API connection failed with status code {response.status_code}")
            print(f"Error: {response.text}")
            
            if response.status_code == 401:
                print("\nAuthentication failed. Please check your API credentials.")
            elif response.status_code == 403:
                print("\nAccess forbidden. Please check your User-Agent header.")
            elif response.status_code == 429:
                print("\nToo many requests. Trendyol API has a limit of 50 requests per 10 seconds.")
            
    except Exception as e:
        print(f"\n❌ Error connecting to Trendyol API: {str(e)}")

if __name__ == "__main__":
    test_trendyol_api_auth()