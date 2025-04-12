"""
Direct API module for Trendyol integration.

This module provides direct API access to Trendyol without using sentence-transformers,
which can cause timeouts in the Replit environment.
"""

import logging
import json
from trendyol.models import TrendyolProduct
from trendyol import trendyol_api_new
from lcwaikiki.product_models import Product

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def direct_sync_product_to_trendyol(product):
    """
    Sync a product to Trendyol directly without using sentence transformers.
    
    This function is a replacement for the regular sync_product_to_trendyol function
    that bypasses the category finding with sentence transformers.
    
    Args:
        product: A TrendyolProduct instance
        
    Returns:
        Boolean indicating success
    """
    try:
        logger.info(f"Direct syncing product {product.id}: {product.title[:50]}...")
        
        # Get the API client
        api_client = trendyol_api_new.get_api_client_from_config()
        if not api_client:
            error_msg = "Failed to get API client"
            logger.error(error_msg)
            product.batch_status = 'failed'
            product.status_message = error_msg
            product.save()
            return False
        
        # Get the product manager
        product_manager = trendyol_api_new.TrendyolProductManager(api_client)
        
        # Use existing category ID and brand ID
        category_id = product.category_id
        brand_id = product.brand_id
        
        # Prepare attributes with proper format
        attributes = []
        if product.attributes:
            # Parse JSON if needed
            if isinstance(product.attributes, str):
                try:
                    attrs = json.loads(product.attributes)
                except:
                    attrs = {}
            else:
                attrs = product.attributes
            
            # Convert attributes to proper format
            if 'color' in attrs:
                color_name = attrs['color']
                attributes.append({
                    "attributeId": 348,  # Hard-coded color attribute ID
                    "attributeValueId": 1011  # Default to Ekru
                })
        
        # Build payload
        try:
            logger.info(f"Building product payload with category ID: {category_id}, brand ID: {brand_id}")
            payload = product_manager._build_product_payload(product, category_id, brand_id, attributes)
            
            # Submit product
            logger.info(f"Submitting product {product.barcode} to Trendyol")
            response = api_client.post(f"product/sellers/{api_client.config.seller_id}/products", payload)
            
            if response and 'batchRequestId' in response:
                batch_id = response['batchRequestId']
                logger.info(f"Success! Product sent to Trendyol with batch ID: {batch_id}")
                
                # Update product
                product.batch_id = batch_id
                product.batch_status = 'processing'
                product.status_message = f"Submitted with batch ID: {batch_id}"
                product.save()
                
                return True
            else:
                error_msg = f"Failed to get batch ID from response: {str(response)}"
                logger.error(error_msg)
                product.batch_status = 'failed'
                product.status_message = error_msg
                product.save()
                return False
                
        except Exception as e:
            error_msg = f"Error building or submitting product: {str(e)}"
            logger.error(error_msg)
            product.batch_status = 'failed'
            product.status_message = error_msg
            product.save()
            return False
            
    except Exception as e:
        error_msg = f"Unexpected error in direct_sync_product_to_trendyol: {str(e)}"
        logger.error(error_msg)
        product.batch_status = 'failed'
        product.status_message = error_msg
        product.save()
        return False

def batch_process_products_direct(products, batch_size=10, delay=0.5):
    """
    Process a list of products in batches, using the direct API approach.
    
    Args:
        products: List of TrendyolProduct instances
        batch_size: Number of products to process in each batch
        delay: Delay between products in seconds
        
    Returns:
        Tuple of (success_count, error_count, batch_ids)
    """
    import time
    from tqdm import tqdm
    
    logger.info(f"Processing {len(products)} products in batches of {batch_size}")
    
    success_count = 0
    error_count = 0
    batch_ids = []
    
    # Process in batches
    batches = [products[i:i+batch_size] for i in range(0, len(products), batch_size)]
    
    for batch in tqdm(batches, desc="Batches"):
        for product in batch:
            try:
                result = direct_sync_product_to_trendyol(product)
                
                if result and product.batch_id:
                    success_count += 1
                    batch_ids.append(product.batch_id)
                else:
                    error_count += 1
                    
                # Brief pause between products to avoid rate limits
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error processing product in batch: {str(e)}")
                error_count += 1
    
    logger.info(f"Batch processing completed: {success_count} successful, {error_count} failed")
    return success_count, error_count, batch_ids