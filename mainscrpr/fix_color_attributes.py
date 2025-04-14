"""
Script to fix color attributes format for Trendyol products.

This script specifically addresses the 'Zorunlu kategori özellik bilgisi eksiktir. Eksik alan: Renk'
error, ensuring that all products have a valid color attribute in the correct format.

Run this script with: python manage.py shell < fix_color_attributes.py
"""

import json
import logging
import os
import sys

# Set up Django environment
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct
from trendyol.fetch_api_data import get_color_attribute_id, get_color_value_id

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_color_attribute(product):
    """
    Ensure product has a valid color attribute in the correct format
    """
    try:
        # Get the product's attributes
        attributes = product.attributes
        
        # Check if attributes is a string, and if so, convert to object
        if isinstance(attributes, str):
            try:
                attributes = json.loads(attributes)
            except json.JSONDecodeError:
                attributes = []
        
        # If attributes is None, initialize as empty list
        if attributes is None:
            attributes = []
        
        # Ensure attributes is a list
        if not isinstance(attributes, list):
            if isinstance(attributes, dict):
                # Convert dict to list format expected by API
                attributes_list = []
                for key, value in attributes.items():
                    if key.isdigit():
                        attributes_list.append({
                            'attributeId': int(key),
                            'attributeValueId': value
                        })
                    else:
                        attributes_list.append({
                            'attributeId': key,
                            'attributeValueId': value
                        })
                attributes = attributes_list
            else:
                attributes = []
        
        # Check if there's already a color attribute
        has_color = False
        color_attribute_id = get_color_attribute_id(product.category_id)
        
        for attr in attributes:
            if attr.get('attributeId') == color_attribute_id:
                has_color = True
                break
        
        # If no color attribute, try to determine a sensible default
        if not has_color:
            # Try to extract color from title or description
            color_keywords = {
                'Beyaz': 'Beyaz',
                'Siyah': 'Siyah',
                'Mavi': 'Mavi',
                'Kırmızı': 'Kirmizi',
                'Pembe': 'Pembe',
                'Yeşil': 'Yeşil',
                'Sarı': 'Sarı',
                'Mor': 'Mor',
                'Gri': 'Gri',
                'Kahverengi': 'Kahverengi',
                'Lacivert': 'Lacivert',
                'Turuncu': 'Turuncu',
                'Bej': 'Bej',
                'Ekru': 'Ekru',
                'Krem': 'Krem',
                'Petrol': 'Petrol'
            }
            
            found_color = None
            for color, api_color in color_keywords.items():
                if color.lower() in product.title.lower() or (product.description and color.lower() in product.description.lower()):
                    found_color = api_color
                    break
            
            # Default to "Bej" if no color found, as this is a safe neutral
            if not found_color:
                found_color = "Bej"
            
            # Get the color value ID
            color_value_id = get_color_value_id(product.category_id, found_color)
            
            # Add the color attribute
            attributes.append({
                'attributeId': color_attribute_id,
                'attributeValueId': color_value_id
            })
            
            logger.info(f"Added color '{found_color}' to product {product.id} ({product.title})")
        
        # Update the product's attributes
        product.attributes = attributes
        product.save()
        
        return True
    except Exception as e:
        logger.error(f"Error fixing color attribute for product {product.id}: {str(e)}")
        return False

def main():
    """Fix color attributes for Trendyol products"""
    # Get all products
    products = TrendyolProduct.objects.all()
    total = products.count()
    success = 0
    failed = 0
    
    logger.info(f"Found {total} products to process")
    
    # Process each product
    for product in products:
        result = fix_color_attribute(product)
        if result:
            success += 1
        else:
            failed += 1
        
        # Log progress every 10 products
        if (success + failed) % 10 == 0:
            logger.info(f"Processed {success + failed}/{total} products ({success} succeeded, {failed} failed)")
    
    logger.info(f"Completed processing {total} products ({success} succeeded, {failed} failed)")

if __name__ == "__main__":
    main()