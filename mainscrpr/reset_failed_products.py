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
    
    # Show all error messages
    print("\nError messages from failed products:")
    for product in failed_products:
        print(f"- Product ID {product.id}: {product.status_message}")
    
    print("\nResetting products...")
    for product in failed_products:
        error_msg = product.status_message or ""  # Use empty string if None
        
        # Check if the failure was related to an API URL error
        # Be more lenient with error matching to catch more cases
        api_related_keywords = [
            'apigw.trendyol.com', 
            'api.trendyol.com',
            '/integration/',
            'Server Error', 
            '502', 
            '556',
            'url'
        ]
        
        if any(e.lower() in error_msg.lower() for e in api_related_keywords):
            print(f"Resetting product: {product.title} (ID: {product.id})")
            print(f"  Previous error: {error_msg}")
            
            # Reset the product status
            product.batch_status = 'pending'
            product.status_message = "Reset after API URL fixes"
            product.save()
            
            url_error_count += 1
        else:
            print(f"Skipping product: {product.title} (ID: {product.id})")
            print(f"  Error doesn't appear API-related: {error_msg}")
        
        count += 1
    
    print(f"Processed {count} failed products")
    print(f"Reset {url_error_count} products with API URL errors")

# When running with python manage.py shell < script.py
# the __name__ == "__main__" condition is not met
# So we call main() directly

print("Starting the reset_failed_products script...")
main()
print("Script completed.")