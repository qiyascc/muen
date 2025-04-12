"""
Script to retry pending Trendyol products.

This script tries to resubmit products that were previously reset to pending status.

Run this script with: python manage.py shell < retry_pending_products.py
"""

import logging
import time
from trendyol.models import TrendyolProduct
from trendyol import trendyol_api_new

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Retry pending Trendyol products."""
    logger.info("Starting product retry process")
    
    # Get all pending products
    products = TrendyolProduct.objects.filter(batch_status='pending')
    logger.info(f"Found {products.count()} pending products to retry")
    
    if products.count() == 0:
        logger.info("No pending products found. Exiting.")
        return
    
    # Get the API client
    api_client = trendyol_api_new.get_api_client_from_config()
    if not api_client:
        logger.error("Failed to get API client. Exiting.")
        return
    
    # Get the product manager
    product_manager = trendyol_api_new.TrendyolProductManager(api_client)
    
    success_count = 0
    error_count = 0
    
    for product in products:
        try:
            logger.info(f"Processing product {product.id}: {product.title[:50]}...")
            
            # Print product details for debugging
            logger.info(f"- Barcode: {product.barcode}")
            logger.info(f"- Brand ID: {product.brand_id}")
            logger.info(f"- Category ID: {product.category_id}")
            logger.info(f"- Image URL: {product.image_url[:100]}...")
            
            # Sync the product to Trendyol
            result = trendyol_api_new.sync_product_to_trendyol(product)
            
            if result and product.batch_id:
                logger.info(f"Success! Product sent to Trendyol with batch ID: {product.batch_id}")
                success_count += 1
                
                # Brief pause to avoid rate limits
                time.sleep(1)
            else:
                logger.error(f"Failed to send product to Trendyol: {product.status_message}")
                error_count += 1
                
        except Exception as e:
            logger.error(f"Error processing product {product.id}: {str(e)}")
            error_count += 1
    
    logger.info(f"Product retry completed: {success_count} successful, {error_count} failed")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()