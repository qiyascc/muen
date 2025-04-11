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
    if product.attributes:
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
            if not color and product.lcwaikiki_product and hasattr(product.lcwaikiki_product, 'color'):
                color = product.lcwaikiki_product.color
            
            if color:
                # Simple attribute format for Trendyol - just color as an attributeId
                product.attributes = [{"attributeId": "color", "attributeValueId": color}]
                changed = True
                logger.info(f"Simplified attributes with color: {color} for product {product.id}")
            else:
                # If we can't determine color, use empty attributes
                product.attributes = []
                changed = True
                logger.info(f"Reset attributes (no color found) for product {product.id}")
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