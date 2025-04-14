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

# Import models and API client
from trendyol.models import TrendyolProduct
from trendyol.api_client_new import get_api_client, get_required_attributes_for_category

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Common color mappings for default values
# Format: Turkish color name -> Trendyol color attribute value ID
COLOR_MAPPINGS = {
    'siyah': 686230,  # Black
    'beyaz': 686229,  # White
    'lacivert': 686240,  # Navy Blue
    'mavi': 686235,  # Blue
    'kırmızı': 686236,  # Red
    'yeşil': 686237,  # Green
    'sarı': 686238,  # Yellow
    'turuncu': 686239,  # Orange
    'mor': 686241,  # Purple
    'pembe': 686242,  # Pink
    'gri': 686244,  # Gray
    'kahverengi': 686243,  # Brown
    'bej': 686249,  # Beige
}

def fix_color_attribute(product):
    """
    Ensure product has a valid color attribute in the correct format
    """
    try:
        # Skip if already successfully processed
        if product.batch_status == 'success':
            return True
        
        # Ensure attributes is a list
        if not isinstance(product.attributes, list):
            product.attributes = []
        
        # Check if color attribute already exists
        has_color = False
        for attr in product.attributes:
            if isinstance(attr, dict) and attr.get('attributeId') == 348:
                has_color = True
                # Make sure the attributeValueId is a number, not a string
                if 'attributeValueId' in attr and isinstance(attr['attributeValueId'], str):
                    try:
                        attr['attributeValueId'] = int(attr['attributeValueId'])
                        logger.info(f"Converted color attribute value to numeric for product {product.id}")
                    except (ValueError, TypeError):
                        # If conversion fails, use a default value
                        attr['attributeValueId'] = 686230  # Default to black
                        logger.info(f"Set default color (black) for product {product.id}")
                break
        
        # If no color attribute, add it
        if not has_color:
            # Try to identify color from title or description
            color_id = None
            
            # Search title for color name
            title_lower = product.title.lower() if product.title else ""
            
            for color_name, color_id_value in COLOR_MAPPINGS.items():
                if color_name in title_lower:
                    color_id = color_id_value
                    logger.info(f"Found color '{color_name}' in title for product {product.id}")
                    break
            
            # If still no color, use black as default
            if not color_id:
                color_id = 686230  # Default to black
                logger.info(f"No color found in title, using default black for product {product.id}")
            
            # Add color attribute
            product.attributes.append({
                'attributeId': 348,
                'attributeValueId': color_id
            })
            
            logger.info(f"Added color attribute for product {product.id}")
        
        # Save changes
        product.save()
        
        # Log the updated attributes
        logger.info(f"Updated attributes for product {product.id}: {json.dumps(product.attributes)}")
        
        return True
    except Exception as e:
        logger.error(f"Error fixing color attribute for product {product.id}: {str(e)}")
        return False

def main():
    """Fix color attributes for Trendyol products"""
    try:
        # Get all Trendyol products
        products = TrendyolProduct.objects.filter(batch_status__in=['pending', 'failed'])
        
        logger.info(f"Found {products.count()} products to process")
        
        # Filter for failed products with color error
        color_error_pattern = "Zorunlu kategori özellik bilgisi eksiktir. Eksik alan: Renk"
        color_error_products = products.filter(status_message__icontains="Renk")
        
        logger.info(f"Found {color_error_products.count()} products with color errors")
        
        # Process color error products first
        success_count = 0
        for product in color_error_products:
            logger.info(f"Processing product {product.id} with color error")
            if fix_color_attribute(product):
                product.batch_status = 'pending'
                product.status_message = "Color attribute fixed, ready for retry"
                product.save()
                success_count += 1
        
        logger.info(f"Fixed {success_count} products with color errors")
        
        # Then process all pending products to ensure they have correct color attributes
        pending_products = products.filter(batch_status='pending')
        pending_count = 0
        
        logger.info(f"Processing {pending_products.count()} pending products")
        
        for product in pending_products:
            if fix_color_attribute(product):
                pending_count += 1
        
        logger.info(f"Processed {pending_count} pending products")
        logger.info(f"Total products processed: {success_count + pending_count}")
    
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    # Execute when run directly
    main()