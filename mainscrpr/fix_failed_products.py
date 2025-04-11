"""
Script to fix failed Trendyol products.

This script specifically targets products that failed with the 400 Bad Request error
for the products endpoint, fixing their payloads and retrying them.

Run this script with: python manage.py shell < fix_failed_products.py
"""

import os
import sys
import re
import django
from loguru import logger

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct
from trendyol.api_client import get_api_client, create_trendyol_product, prepare_product_data

def fix_product_payload(product):
    """
    Fix common issues with product payloads that cause 400 Bad Request errors
    """
    # Set a flag to track if we made changes
    changed = False
    
    # 1. Ensure vatRate is set to 10 (default for most items)
    if not product.vat_rate or product.vat_rate != 10:
        product.vat_rate = 10
        changed = True
        logger.info(f"Fixed vat_rate for product {product.id} to 10")
    
    # 2. Ensure quantity is positive
    if product.quantity <= 0:
        product.quantity = 10  # Default to 10
        changed = True
        logger.info(f"Fixed quantity for product {product.id} to 10")
    
    # 3. Ensure price is positive
    if not product.price or product.price <= 0:
        if product.lcwaikiki_product and hasattr(product.lcwaikiki_product, 'price') and product.lcwaikiki_product.price:
            product.price = product.lcwaikiki_product.price
            changed = True
            logger.info(f"Fixed price for product {product.id} from LC Waikiki product")
        else:
            product.price = 99.99  # Default reasonable price
            changed = True
            logger.info(f"Fixed price for product {product.id} to default 99.99")
    
    # 4. Fix attributes based on color and size
    if product.attributes is not None:
        # Check if attributes are in the right format
        try:
            # Best format is a simple array with proper attributeId/attributeValueId pairs
            # For LCW products with color, use this simplified format that matches Trendyol's expectations
            color = None
            
            # Try to extract color from the title - common in LCW product titles
            if product.title:
                color_match = re.search(r'(Beyaz|Siyah|Mavi|Kirmizi|Pembe|Yeşil|Sarı|Mor|Gri|Kahverengi)', 
                                       product.title, re.IGNORECASE)
                if color_match:
                    color = color_match.group(1)
            
            # If a TrendyolProduct is linked to an LCWaikiki product, get the color from there
            if not color and hasattr(product, 'lcwaikiki_product') and product.lcwaikiki_product and hasattr(product.lcwaikiki_product, 'color'):
                color = product.lcwaikiki_product.color
            
            # Get color ID mapping for Trendyol
            color_id_map = {
                'Beyaz': 1001, 
                'Siyah': 1002, 
                'Mavi': 1003, 
                'Kirmizi': 1004, 
                'Pembe': 1005,
                'Yeşil': 1006,
                'Sarı': 1007,
                'Mor': 1008,
                'Gri': 1009,
                'Kahverengi': 1010
            }
            
            if color and color in color_id_map:
                # Format with numeric attributeValueId as expected by Trendyol API
                color_id = color_id_map[color]
                product.attributes = [{"attributeId": 348, "attributeValueId": color_id}]
                changed = True
                logger.info(f"Applied color attribute with ID mapping: {color} => {color_id} for product {product.id}")
            else:
                # If we can't determine color or don't have its ID, use empty attributes
                product.attributes = []
                changed = True
                logger.info(f"Reset attributes (no color ID mapping found) for product {product.id}")
        except Exception as e:
            # If there's any error processing attributes, reset them
            logger.error(f"Error fixing attributes for product {product.id}: {str(e)}")
            product.attributes = []
            changed = True
            logger.info(f"Reset attributes due to error for product {product.id}")
    
    # Save if changes were made
    if changed:
        product.save()
        logger.info(f"Saved changes to product {product.id}")
    
    return changed

def main():
    """Fix and retry failed Trendyol products"""
    # Configure logger to send output to stdout
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    
    # Add a direct print statement to ensure the script is executed
    print("Starting fix_failed_products.py script - DIRECT OUTPUT")
    
    # Get failed products
    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
    logger.info(f"Found {failed_products.count()} failed products")
    
    # Print failed products with their error messages
    for product in failed_products:
        print(f"Product {product.id}: {product.title}")
        print(f"Error: {product.status_message}")
    
    # Process each failed product
    fixed_count = 0
    retried_count = 0
    success_count = 0
    
    for product in failed_products:
        # Fix common payload issues
        fixed = fix_product_payload(product)
        if fixed:
            fixed_count += 1
        
        # Try to create product again
        try:
            logger.info(f"Retrying product {product.id}: {product.title}")
            
            # Keep the existing batch_id if it exists (to meet the not-null constraint)
            # Only reset the status and set a placeholder message (because the field can't be null)
            original_batch_id = product.batch_id
            product.batch_status = 'pending'  # Reset to pending instead of None
            product.status_message = 'Pending retry'  # Set a placeholder status message
            product.save()
            
            # Directly call API client to prepare and send the product
            # This bypasses the create_trendyol_product function which might be resetting the batch_id
            client = get_api_client()
            if client:
                # Prepare data
                api_data = prepare_product_data(product)
                if api_data:
                    try:
                        # Print API data for debugging
                        logger.info("Submitting product data to Trendyol:")
                        logger.info(f"Product title: {product.title}")
                        logger.info(f"Category ID: {product.category_id}")
                        logger.info(f"Barcode: {product.barcode}")
                        logger.info(f"Attributes: {product.attributes}")
                        
                        # Submit to API manually
                        response = client.products.create_products([api_data])
                        logger.info(f"API Response: {response}")
                        
                        # Log detailed response info
                        if isinstance(response, dict):
                            logger.info(f"Response keys: {list(response.keys())}")
                            if 'batchId' in response:
                                logger.info(f"Batch ID in response: {response['batchId']}")
                        else:
                            logger.warning(f"Unexpected response type: {type(response)}")
                        
                        # Update status based on response
                        if response and isinstance(response, dict) and 'batchId' in response:
                            batch_id = response['batchId']
                            product.batch_id = batch_id
                            product.batch_status = 'processing'
                            product.save()
                            
                            success_count += 1
                            logger.info(f"Successfully created product {product.id} with batch ID {batch_id}")
                            retried_count += 1
                        else:
                            logger.error(f"Invalid response from Trendyol API: {response}")
                    except Exception as e:
                        logger.error(f"API error during product creation: {str(e)}")
                else:
                    logger.error(f"Failed to prepare product data for {product.id}")
            else:
                logger.error("Failed to get API client")
        
        except Exception as e:
            logger.error(f"Error retrying product {product.id}: {str(e)}")
    
    logger.info(f"Summary: Fixed {fixed_count} products, retried {retried_count}, succeeded {success_count}")

if __name__ == "__main__":
    main()