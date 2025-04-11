"""
Script to update Trendyol API configurations with the correct base URL.

This script updates all TrendyolAPIConfig entries to use the new Trendyol API base URL:
- Old URL: https://apigw.trendyol.com/integration
- New URL: https://api.trendyol.com/sapigw

Run this script with: python manage.py shell < update_api_urls.py
"""

import django
import os
import sys
from loguru import logger

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol.models import TrendyolAPIConfig

# Define correct URL
CORRECT_URL = "https://api.trendyol.com/sapigw"

def main():
    """Update all API configurations with the correct base URL"""
    # Get all API configurations
    configs = TrendyolAPIConfig.objects.all()
    
    if not configs:
        print("No Trendyol API configurations found in the database.")
        return
    
    count = 0
    print(f"Found {configs.count()} API configuration(s)")
    
    for config in configs:
        old_url = config.base_url
        
        # Check if URL needs to be updated
        if old_url != CORRECT_URL:
            print(f"Updating config '{config.name}' URL from '{old_url}' to '{CORRECT_URL}'")
            config.base_url = CORRECT_URL
            config.save()
            count += 1
        else:
            print(f"Config '{config.name}' already has the correct URL: '{config.base_url}'")
    
    print(f"Updated {count} API configuration(s) with the correct URL")

if __name__ == "__main__":
    main()