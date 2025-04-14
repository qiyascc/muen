"""
Script to reset the status of failed Trendyol products.

This script resets the batch_status and status_message of all products
that previously failed with API URL errors, allowing them to be retried
with the corrected API client.

Run this script with: python manage.py shell < reset_failed_products.py
"""

import os
import sys
import django
import logging
from loguru import logger

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct

def main():
    """Reset failed products with API URL errors"""
    # Get all products with failed status
    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
    logger.info(f"Found {failed_products.count()} failed products")
    
    # Filter by error types that could be fixed with updated API client
    api_errors = []
    for product in failed_products:
        msg = product.status_message or ""
        
        # Check for API or endpoint related errors
        if any(err_type in msg.lower() for err_type in 
              ['api', 'url', 'endpoint', 'connection', 'unknown', 'batch']):
            api_errors.append(product)
    
    logger.info(f"Found {len(api_errors)} products with API-related failures")
    
    # Reset these products
    if api_errors:
        for product in api_errors:
            old_status = product.status_message
            product.batch_status = None
            product.status_message = f"Reset from: {old_status}"
            product.save()
            
        logger.info(f"Reset {len(api_errors)} products")
    else:
        logger.info("No API-related failures found to reset")

if __name__ == "__main__":
    main()