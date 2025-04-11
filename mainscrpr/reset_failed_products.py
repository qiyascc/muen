"""
Script to reset the status of failed Trendyol products.

This script resets the batch_status and status_message of all products
that previously failed with API URL errors, allowing them to be retried
with the corrected API client.

Run this script with: python manage.py shell < reset_failed_products.py
"""

import django
import os
import sys
from loguru import logger

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from trendyol.models import TrendyolProduct

def main():
    """Reset failed products with API URL errors"""
    # Get all failed products
    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
    
    if not failed_products:
        print("No failed products found in the database.")
        return
    
    count = 0
    url_error_count = 0
    
    print(f"Found {failed_products.count()} failed products")
    
    for product in failed_products:
        error_msg = product.status_message
        
        # Check if the failure was related to an API URL error
        if any(e in error_msg for e in ['apigw.trendyol.com', '/integration/integration/', 'Server Error', '502', '556']):
            print(f"Resetting product: {product.title} (ID: {product.id})")
            print(f"  Previous error: {error_msg}")
            
            # Reset the product status
            product.batch_status = 'pending'
            product.status_message = "Reset after API URL fixes"
            product.save()
            
            url_error_count += 1
        
        count += 1
    
    print(f"Processed {count} failed products")
    print(f"Reset {url_error_count} products with API URL errors")

if __name__ == "__main__":
    main()