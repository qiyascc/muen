"""
Script to retry failed Trendyol products.

This script attempts to resubmit products that previously failed,
using the improved batch status checking logic.

Run this script with: python manage.py shell < retry_trendyol_products.py
"""

import os
import sys
import logging
import json
import time

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

def check_batch_status(batch_id, client=None):
    """Check the status of a batch request"""
    if not client:
        client = get_api_client()
        if not client:
            logger.error("Failed to get API client")
            return None
    
    try:
        response = client.get(f"{client.products}/batch-requests/{batch_id}")
        return response
    except Exception as e:
        logger.error(f"Error checking batch status for {batch_id}: {str(e)}")
        return None

def retry_product(product):
    """Retry submitting a product to Trendyol"""
    try:
        logger.info(f"Retrying product ID {product.id}: {product.title}")
        
        # Reset the status
        product.batch_status = 'pending'
        product.status_message = "Retrying with new API client"
        product.save()
        
        # Submit the product
        batch_id = create_trendyol_product(product)
        
        if not batch_id:
            logger.error(f"Failed to create product {product.id}")
            return False
        
        logger.info(f"Successfully submitted product {product.id} with batch ID {batch_id}")
        
        # Wait a moment to let the batch process
        time.sleep(2)
        
        # Check the batch status
        status = check_batch_status(batch_id)
        if status:
            logger.info(f"Batch status: {json.dumps(status)}")
        
        return True
    except Exception as e:
        logger.error(f"Error retrying product {product.id}: {str(e)}")
        return False

def main():
    """Retry failed Trendyol products with the improved API client"""
    try:
        # Get all pending products first (reset from failed)
        pending_products = TrendyolProduct.objects.filter(batch_status='pending')
        
        logger.info(f"Found {pending_products.count()} pending products")
        
        success_count = 0
        for product in pending_products[:5]:  # Process 5 at a time to avoid rate limits
            if retry_product(product):
                success_count += 1
        
        logger.info(f"Successfully retried {success_count} out of {min(5, pending_products.count())} products")
    
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    # Execute when run directly
    main()