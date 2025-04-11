"""
Script to retry failed Trendyol products.

This script attempts to resubmit products that previously failed,
using the improved batch status checking logic.

Run this script with: python manage.py shell < retry_trendyol_products.py
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
from trendyol.api_client import sync_product_to_trendyol, batch_process_products

def main():
    """Retry failed Trendyol products with the improved API client"""
    print("Starting retry_trendyol_products.py script...")
    
    # Get all products with failed status
    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
    print(f"Found {failed_products.count()} failed products to retry")
    logger.info(f"Found {failed_products.count()} failed products to retry")
    
    if not failed_products:
        logger.info("No failed products found to retry.")
        return
    
    # Process all failed products
    logger.info("Starting batch processing of failed products...")
    success_count, error_count, batch_ids = batch_process_products(
        failed_products,
        sync_product_to_trendyol,
        batch_size=5,
        delay=1.0
    )
    
    logger.info(f"Retry completed: {success_count} succeeded, {error_count} failed")
    if batch_ids:
        logger.info(f"Batch IDs for successful operations: {batch_ids}")

if __name__ == "__main__":
    main()