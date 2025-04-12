"""
Script to update the Trendyol API configuration to use the correct working endpoints.

This script updates the TrendyolAPIConfig to use the correct base URL that works
with the Trendyol API.

Run this script with: python manage.py shell < update_api_config.py
"""

import django
import os
import sys
import json
import logging
from pprint import pprint

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol.models import TrendyolAPIConfig

def update_api_config():
    """Update the API configuration to use the correct URL"""
    print("\n===== UPDATING TRENDYOL API CONFIGURATION =====\n")
    
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
    print(f"- User Agent: {config.user_agent}")
    
    # Update the config to use the new URL
    old_base_url = config.base_url
    new_base_url = "https://api.trendyol.com/sapigw"
    
    if old_base_url == new_base_url:
        print("\nAPI configuration already using the correct URL.")
        return True
    
    print(f"\nUpdating API config base URL from {old_base_url} to {new_base_url}")
    
    # Update the config
    config.base_url = new_base_url
    config.save()
    
    print(f"API configuration updated successfully!")
    
    # Verify the update
    updated_config = TrendyolAPIConfig.objects.get(id=config.id)
    print(f"\nVerified updated config:")
    print(f"- Name: {updated_config.name}")
    print(f"- Base URL: {updated_config.base_url}")
    print(f"- Seller ID: {updated_config.seller_id}")
    
    return True

if __name__ == "__main__":
    update_api_config()