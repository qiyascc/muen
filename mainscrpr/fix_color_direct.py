#!/usr/bin/env python
"""
Fix color attributes directly in the database.
This script ensures all products have the proper color attribute format
according to Trendyol's requirements.

The color attribute must be present with attributeId: 348
"""

import os
import sys
import json
import logging

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
import django
django.setup()

from django.db.models import Q
from trendyol.models import TrendyolProduct, TrendyolAttribute, TrendyolAttributeValue

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Default color map for common colors in Turkish
COLOR_MAP = {
    'red': {'id': 347, 'name': 'Kırmızı'},
    'blue': {'id': 344, 'name': 'Mavi'},
    'green': {'id': 348, 'name': 'Yeşil'},
    'white': {'id': 343, 'name': 'Beyaz'},
    'black': {'id': 341, 'name': 'Siyah'},
    'pink': {'id': 349, 'name': 'Pembe'},
    'yellow': {'id': 345, 'name': 'Sarı'},
    'grey': {'id': 357, 'name': 'Gri'},
    'purple': {'id': 351, 'name': 'Mor'},
    'orange': {'id': 346, 'name': 'Turuncu'},
    'brown': {'id': 353, 'name': 'Kahverengi'},
    'navy': {'id': 355, 'name': 'Lacivert'}
}

def get_color_attribute_from_title(title):
    """
    Extract color from product title, using a fallback color (Pembe/Pink) if not found.
    """
    title_lower = title.lower()
    
    # Check for known color names (English & Turkish)
    for color, data in COLOR_MAP.items():
        # Check English color name
        if color in title_lower:
            return {'attributeId': 348, 'attributeValueId': data['id']}
        
        # Check Turkish color name
        if data['name'].lower() in title_lower:
            return {'attributeId': 348, 'attributeValueId': data['id']}
    
    # Fallback to Pink (most commonly used for LC Waikiki products)
    return {'attributeId': 348, 'attributeValueId': 349}

def fix_color_attributes():
    """
    Fix color attributes for all products in the database.
    """
    # Get products that don't have the required color attribute
    missing_color_products = []
    
    logger.info("Checking products for missing color attribute")
    
    products = TrendyolProduct.objects.all()
    logger.info(f"Found {products.count()} total products in database")
    
    for product in products:
        attributes = product.attributes or []
        
        # Check if color attribute exists
        has_color = False
        for attr in attributes:
            if isinstance(attr, dict) and attr.get('attributeId') == 348:
                has_color = True
                break
        
        if not has_color:
            missing_color_products.append(product.id)
    
    logger.info(f"Found {len(missing_color_products)} products with missing color attribute")
    
    # Fix missing color attributes
    fixed_count = 0
    for product_id in missing_color_products:
        try:
            product = TrendyolProduct.objects.get(id=product_id)
            
            # Get current attributes or initialize as empty list
            attributes = product.attributes or []
            
            # Extract color from title
            color_attribute = get_color_attribute_from_title(product.title)
            
            # Add color attribute if not exists
            attributes.append(color_attribute)
            
            # Update product attributes
            product.attributes = attributes
            product.save()
            
            fixed_count += 1
            logger.info(f"Fixed color attribute for product: {product.title} (ID: {product.id})")
            
        except Exception as e:
            logger.error(f"Error fixing color attribute for product ID {product_id}: {str(e)}")
    
    logger.info(f"Fixed color attributes for {fixed_count} products")
    return fixed_count

if __name__ == "__main__":
    fixed_count = fix_color_attributes()
    logger.info(f"Color attribute fix completed. Fixed {fixed_count} products.")
    sys.exit(0)