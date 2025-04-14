"""
Script to fix color attributes format for Trendyol products.

This script specifically addresses the 'Zorunlu kategori özellik bilgisi eksiktir. Eksik alan: Renk'
error, ensuring that all products have a valid color attribute in the correct format.

Run this script with: python manage.py shell < fix_color_attributes.py
"""

import os
import sys
import logging
import json

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import our models
from trendyol.models import TrendyolProduct, TrendyolAPIConfig
from trendyol.api_client_new import TrendyolAPI, TrendyolCategoryFinder, get_api_client

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def fix_color_attribute(product):
    """
    Ensure product has a valid color attribute in the correct format
    """
    if not product:
        return False
    
    logger.info(f"Processing product ID {product.id}: {product.title}")
    
    # Get the API client
    api_client = get_api_client()
    if not api_client:
        logger.error("Failed to get API client")
        return False
    
    # Check if product has a category ID
    if not product.category_id:
        logger.warning(f"Product {product.id} has no category_id, cannot process")
        return False
    
    try:
        # Create category finder
        category_finder = TrendyolCategoryFinder(api_client)
        
        # Fetch category attributes
        category_attrs = category_finder.get_category_attributes(product.category_id)
        
        if not category_attrs or 'categoryAttributes' not in category_attrs:
            logger.warning(f"No attributes found for category {product.category_id}")
            return False
        
        # Find color attribute
        color_attr_id = None
        color_attr_values = None
        
        for attr in category_attrs.get('categoryAttributes', []):
            attr_name = attr.get('attribute', {}).get('name', '').lower()
            if 'renk' in attr_name or 'color' in attr_name:
                color_attr_id = attr.get('attribute', {}).get('id')
                color_attr_values = attr.get('attributeValues', [])
                logger.info(f"Found color attribute: ID={color_attr_id}, Values count: {len(color_attr_values)}")
                break
        
        if not color_attr_id or not color_attr_values:
            logger.warning(f"Could not find color attribute for category {product.category_id}")
            return False
        
        # Choose a default color value (first one)
        default_color_value_id = color_attr_values[0].get('id')
        default_color_name = color_attr_values[0].get('name')
        
        # Get current attributes
        current_attrs = product.attributes or []
        
        # Check if color already exists with the correct format
        color_exists = False
        for attr in current_attrs:
            if attr.get('attributeId') == color_attr_id:
                color_exists = True
                logger.info(f"Product already has color attribute in correct format")
                break
            
            # Check for string 'color' attribute that needs conversion
            if attr.get('attributeId') == 'color':
                logger.info(f"Found old string format color attribute: {attr}")
                current_attrs.remove(attr)  # Remove the old string format
        
        # Add color attribute if it doesn't exist
        if not color_exists:
            current_attrs.append({
                'attributeId': color_attr_id,
                'attributeValueId': default_color_value_id
            })
            logger.info(f"Added color attribute: ID={color_attr_id}, ValueID={default_color_value_id} ({default_color_name})")
        
        # Update product
        product.attributes = current_attrs
        product.save()
        logger.info(f"Successfully updated product {product.id} with color attribute")
        return True
    
    except Exception as e:
        logger.error(f"Error fixing color attribute for product {product.id}: {str(e)}")
        return False

def main():
    """Fix color attributes for Trendyol products"""
    try:
        # Get all products that are not complete or marked for skip
        products = TrendyolProduct.objects.exclude(batch_status__in=['completed', 'skip'])
        
        logger.info(f"Found {products.count()} products to process")
        
        # Process each product
        success_count = 0
        fail_count = 0
        
        for product in products:
            if fix_color_attribute(product):
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(f"Processing complete. Success: {success_count}, Failed: {fail_count}")
        logger.info(f"Total products: {success_count + fail_count}")
    
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    # Execute when run directly
    main()