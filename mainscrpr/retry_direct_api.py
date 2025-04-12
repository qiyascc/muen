"""
Script to retry Trendyol products using the direct API.

This script uses the direct_api module to bypass sentence-transformers,
which causes timeouts in the Replit environment.

Run this script with: python manage.py shell < retry_direct_api.py
"""

import logging
from trendyol.models import TrendyolProduct
from trendyol.direct_api import direct_sync_product_to_trendyol

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Retry Trendyol products using the direct API."""
    logger.info("Starting direct API product retry")
    
    # Get pending products
    products = TrendyolProduct.objects.filter(batch_status='pending')
    logger.info(f"Found {products.count()} pending products to retry")
    
    if products.count() == 0:
        logger.info("No pending products found. Exiting.")
        return
    
    # Process just one product for testing
    product = products.first()
    logger.info(f"Processing product {product.id}: {product.title[:50]}...")
    
    # Use the direct API to sync the product
    success = direct_sync_product_to_trendyol(product)
    
    if success:
        logger.info(f"Successfully sent product {product.id} to Trendyol with batch ID: {product.batch_id}")
    else:
        logger.error(f"Failed to send product {product.id} to Trendyol: {product.status_message}")
    
    logger.info("Direct API product retry completed")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()