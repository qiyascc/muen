"""
Script to fix failed Trendyol products.

This script specifically targets products that failed with the 400 Bad Request error
for the products endpoint, fixing their payloads and retrying them.

Run this script with: python manage.py shell < fix_failed_products.py
"""

import os
import sys
import logging
import json
import re

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import our models and API client
from django.utils import timezone
from trendyol.models import TrendyolProduct, TrendyolAPIConfig
from trendyol.api_client_new import get_api_client, prepare_product_data, create_trendyol_product

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def fix_product_payload(product):
    """
    Fix common issues with product payloads that cause 400 Bad Request errors
    """
    try:
        # Check for missing fields
        if not product.barcode:
            product.barcode = f"LCW{product.id}{int(timezone.now().timestamp())}"
            logger.info(f"Generated new barcode for product {product.id}: {product.barcode}")
        
        # Ensure barcode is alphanumeric
        product.barcode = re.sub(r'[^a-zA-Z0-9]', '', product.barcode)
        
        # Ensure product_main_id exists
        if not product.product_main_id:
            product.product_main_id = product.barcode
            logger.info(f"Set product_main_id to barcode for product {product.id}")
        
        # Ensure stock_code exists
        if not product.stock_code:
            product.stock_code = product.barcode
            logger.info(f"Set stock_code to barcode for product {product.id}")
        
        # Ensure brand_id exists
        if not product.brand_id:
            # Set a default brand ID for LC Waikiki (7651)
            product.brand_id = 7651
            logger.info(f"Set default brand_id (7651) for product {product.id}")
        
        # Ensure category_id exists
        if not product.category_id:
            # Set a default category ID for Clothing (383)
            product.category_id = 383
            logger.info(f"Set default category_id (383) for product {product.id}")
        
        # Normalize title length
        if product.title and len(product.title) > 100:
            product.title = product.title[:97] + "..."
            logger.info(f"Trimmed title for product {product.id}")
        
        # Fix the attributes format - ensure it's a list
        if not product.attributes or not isinstance(product.attributes, list):
            product.attributes = []
            logger.info(f"Reset attributes to empty list for product {product.id}")
        
        # Save changes
        product.save()
        logger.info(f"Fixed product {product.id}")
        return True
    except Exception as e:
        logger.error(f"Error fixing product {product.id}: {str(e)}")
        return False

def main():
    """Fix and retry failed Trendyol products"""
    try:
        # Get all failed products
        failed_products = TrendyolProduct.objects.filter(batch_status='failed')
        
        logger.info(f"Found {failed_products.count()} failed products")
        
        success_count = 0
        for product in failed_products:
            logger.info(f"Processing product ID {product.id}: {product.title}")
            logger.info(f"Current status: {product.batch_status}, Message: {product.status_message}")
            
            # Fix the product payload
            if fix_product_payload(product):
                # Reset status
                product.batch_status = 'pending'
                product.status_message = "Fixed and ready for retry"
                product.save()
                
                # Retry submission
                logger.info(f"Retrying submission for product {product.id}")
                batch_id = create_trendyol_product(product)
                
                if batch_id:
                    logger.info(f"Successfully resubmitted product {product.id} with batch ID {batch_id}")
                    success_count += 1
                else:
                    logger.error(f"Failed to resubmit product {product.id}")
            else:
                logger.warning(f"Could not fix product {product.id}")
        
        logger.info(f"Successfully fixed and resubmitted {success_count} out of {failed_products.count()} products")
    
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    # Execute when run directly
    main()