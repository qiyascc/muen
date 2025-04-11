"""
Script to fix failed Trendyol products.

This script specifically targets products that failed with the 400 Bad Request error
for the products endpoint, fixing their payloads and retrying them.

Run this script with: python manage.py shell < fix_failed_products.py
"""

import os
import sys
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
    
    # 4. Fix attributes with numeric IDs
    if product.attributes:
        # Check if attributes are in the right format
        try:
            # Check the structure of attributes
            if isinstance(product.attributes, dict):
                # Convert to list format if it's a dict
                product.attributes = [{'attributeId': k, 'attributeValueId': v} 
                                    for k, v in product.attributes.items()]
                changed = True
                logger.info(f"Converted attributes from dict to list for product {product.id}")
            elif isinstance(product.attributes, list):
                # Fix any string attributeValueId that should be numeric
                for attr in product.attributes:
                    if isinstance(attr, dict) and 'attributeValueId' in attr:
                        val = attr['attributeValueId']
                        if isinstance(val, str) and val.isdigit():
                            attr['attributeValueId'] = int(val)
                            changed = True
                            logger.info(f"Fixed attribute value ID format for product {product.id}")
            else:
                # Reset attributes if format is completely wrong
                product.attributes = []
                changed = True
                logger.info(f"Reset invalid attributes format for product {product.id}")
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
            
            # Reset batch ID and status
            product.batch_id = None
            product.batch_status = None
            product.status_message = None
            product.save()
            
            # Retry product creation
            batch_id = create_trendyol_product(product)
            retried_count += 1
            
            if batch_id:
                success_count += 1
                logger.info(f"Successfully created product {product.id} with batch ID {batch_id}")
            else:
                logger.error(f"Failed to create product {product.id}")
        
        except Exception as e:
            logger.error(f"Error retrying product {product.id}: {str(e)}")
    
    logger.info(f"Summary: Fixed {fixed_count} products, retried {retried_count}, succeeded {success_count}")

if __name__ == "__main__":
    main()