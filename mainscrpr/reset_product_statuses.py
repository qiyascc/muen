"""
Script to reset the status of Trendyol products.

This script resets the batch_status of all failed products to allow retrying them.

Run this script with: python manage.py shell < reset_product_statuses.py
"""

import logging
from trendyol.models import TrendyolProduct

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Reset the status of failed Trendyol products."""
    logger.info("Starting product status reset process")
    
    # Reset failed products
    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
    logger.info(f"Found {failed_products.count()} failed products to reset")
    
    for product in failed_products:
        product.batch_status = 'pending'
        product.status_message = 'Reset for retry with fixed image URLs'
        product.save()
        logger.info(f"Reset product {product.id}: {product.title[:50]}...")
    
    logger.info(f"Product status reset completed: {failed_products.count()} products reset")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()