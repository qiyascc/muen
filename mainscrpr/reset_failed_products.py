"""
Script to reset the status of failed Trendyol products.

This script resets the batch_status and status_message of all products
that previously failed with API URL errors, allowing them to be retried
with the corrected API client.

Run this script with: python manage.py shell < reset_failed_products.py
"""

import os
import sys
import logging
import re

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import our models
from trendyol.models import TrendyolProduct

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def main():
    """Reset failed products with API URL errors"""
    try:
        # Get all failed products
        failed_products = TrendyolProduct.objects.filter(batch_status='failed')
        
        logger.info(f"Found {failed_products.count()} failed products")
        
        # Filter products with API URL errors
        api_url_pattern = re.compile(r'(api\.trendyol\.com|URL|404|400 Bad Request|500 Server Error)', re.IGNORECASE)
        color_pattern = re.compile(r'(renk|color|zorunlu kategori)', re.IGNORECASE)
        
        api_url_errors = 0
        color_errors = 0
        other_errors = 0
        
        for product in failed_products:
            if not product.status_message:
                continue
                
            if api_url_pattern.search(product.status_message):
                # This is an API URL error, reset it
                product.batch_status = 'pending'
                product.status_message = "Reset for retry with corrected API client"
                product.save()
                
                logger.info(f"Reset product {product.id} (API URL error)")
                api_url_errors += 1
            elif color_pattern.search(product.status_message):
                # This is a color attribute error
                product.batch_status = 'pending'
                product.status_message = "Reset for retry with corrected color attribute"
                product.save()
                
                logger.info(f"Reset product {product.id} (Color attribute error)")
                color_errors += 1
            else:
                # Other error
                logger.info(f"Skipping product {product.id} with error: {product.status_message}")
                other_errors += 1
        
        logger.info(f"Reset {api_url_errors} products with API URL errors")
        logger.info(f"Reset {color_errors} products with color attribute errors")
        logger.info(f"Skipped {other_errors} products with other errors")
        logger.info(f"Total: {api_url_errors + color_errors + other_errors} products processed")
    
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    # Execute when run directly
    main()