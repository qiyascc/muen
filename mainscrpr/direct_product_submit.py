"""
Script to directly submit a Trendyol product without using sentence transformers.

This script bypasses the semantic search by directly using the product's existing category ID.

Run this script with: python manage.py shell < direct_product_submit.py
"""

import logging
import json
from trendyol.models import TrendyolProduct
from trendyol import trendyol_api_new

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def direct_submit_product(product_id):
    """Directly submit a product to Trendyol without using sentence transformers."""
    try:
        # Get the product
        product = TrendyolProduct.objects.get(id=product_id)
        logger.info(f"Processing product {product.id}: {product.title[:50]}...")
        
        # Print product details for debugging
        logger.info(f"- Barcode: {product.barcode}")
        logger.info(f"- Brand ID: {product.brand_id}")
        logger.info(f"- Category ID: {product.category_id}")
        logger.info(f"- Image URL: {product.image_url[:100]}...")
        
        # Get the API client
        api_client = trendyol_api_new.get_api_client_from_config()
        if not api_client:
            logger.error("Failed to get API client")
            return False
        
        # Get the product manager
        product_manager = trendyol_api_new.TrendyolProductManager(api_client)
        
        # Prepare the attributes - ensure color is in the right format
        attributes = []
        if product.attributes:
            # Parse the attributes JSON
            if isinstance(product.attributes, str):
                attrs = json.loads(product.attributes)
            else:
                attrs = product.attributes
                
            # Extract color if present
            if 'color' in attrs:
                color_name = attrs['color']
                attributes.append({
                    "attributeId": 348,  # Hard-coded color attribute ID
                    "attributeValueId": 1011  # Default to a common color (Ekru)
                })
        
        # Build a simple payload
        payload = {
            "items": [
                {
                    "barcode": product.barcode,
                    "title": product.title[:100],
                    "productMainId": product.barcode,
                    "brandId": product.brand_id,
                    "categoryId": product.category_id,
                    "quantity": 10,
                    "stockCode": product.barcode,
                    "dimensionalWeight": 1,
                    "description": product.description or product.title,
                    "currencyType": "TRY",
                    "listPrice": float(product.price),
                    "salePrice": float(product.price),
                    "vatRate": 10,
                    "cargoCompanyId": 17,
                    "images": [{"url": product.image_url}],
                    "attributes": attributes
                }
            ]
        }
        
        # Submit the product
        logger.info("Submitting product to Trendyol")
        response = api_client.post(
            f"product/sellers/{api_client.config.seller_id}/products", 
            payload
        )
        
        logger.info(f"API response: {response}")
        
        # Check if we got a batch ID
        if 'batchRequestId' in response:
            batch_id = response['batchRequestId']
            logger.info(f"Success! Product sent to Trendyol with batch ID: {batch_id}")
            
            # Update the product
            product.batch_id = batch_id
            product.batch_status = 'processing'
            product.status_message = f"Submitted with batch ID: {batch_id}"
            product.save()
            
            return True
        else:
            logger.error(f"Failed to get batch ID from response: {response}")
            
            # Update the product
            product.batch_status = 'failed'
            product.status_message = f"Failed to get batch ID: {response}"
            product.save()
            
            return False
            
    except Exception as e:
        logger.error(f"Error submitting product: {str(e)}")
        return False

def main():
    """Directly submit a few products to Trendyol."""
    logger.info("Starting direct product submission")
    
    # Get a few pending products to try
    products = TrendyolProduct.objects.filter(batch_status='pending')[:2]
    logger.info(f"Found {products.count()} pending products to try")
    
    for product in products:
        success = direct_submit_product(product.id)
        if success:
            logger.info(f"Successfully submitted product {product.id}")
        else:
            logger.error(f"Failed to submit product {product.id}")
    
    logger.info("Direct product submission completed")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()