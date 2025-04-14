"""
Script to fix color attributes format for Trendyol products.

This script specifically addresses the 'Zorunlu kategori özellik bilgisi eksiktir. Eksik alan: Renk'
error, ensuring that all products have a valid color attribute in the correct format.

Run this script with: python manage.py shell < fix_color_attributes.py
"""

import os
import sys
import re
import django
import json

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct
from trendyol.api_client import get_api_client, prepare_product_data, sync_product_to_trendyol

# Color mapping for Trendyol (Renk attributeId is 348)
COLOR_ID_MAP = {
    'Beyaz': 686230,
    'Siyah': 686234,
    'Mavi': 686239,
    'Kırmızı': 686241,
    'Pembe': 686247,
    'Yeşil': 686238,
    'Sarı': 686245,
    'Mor': 686246,
    'Gri': 686233,
    'Kahverengi': 686231,
    'Ekru': 686236,
    'Bej': 686228,
    'Lacivert': 686232,
    'Turuncu': 686244,
    'Krem': 686251,
    # Add more accurate color IDs as needed
}

def fix_color_attribute(product):
    """
    Ensure product has a valid color attribute in the correct format
    """
    changed = False
    
    # Extract color from title or source product
    color = None
    color_match = None
    
    if product.title:
        # Try different Turkish color patterns with case insensitivity
        color_pattern = r'(Beyaz|Siyah|Mavi|Kırmızı|Pembe|Yeşil|Sarı|Mor|Gri|Kahverengi|Ekru|Bej|Lacivert|Turuncu|Krem|Sari|Yesil|Kirmizi)'
        color_match = re.search(color_pattern, product.title, re.IGNORECASE)
        
    if color_match:
        color = color_match.group(1)
        # Normalize Turkish characters (handle both with and without accents)
        color_map = {
            'Yesil': 'Yeşil',
            'Sari': 'Sarı',
            'Kirmizi': 'Kırmızı'
        }
        color = color_map.get(color, color)
    
    # If no color found in title, check if linked to a source product with color
    if not color and hasattr(product, 'lcwaikiki_product') and product.lcwaikiki_product:
        if hasattr(product.lcwaikiki_product, 'color') and product.lcwaikiki_product.color:
            color = product.lcwaikiki_product.color
    
    # Default to black if no color found
    if not color:
        color = 'Siyah'
        print(f"No color found for product {product.id}, defaulting to {color}")
    
    # Get color ID from mapping
    color_id = COLOR_ID_MAP.get(color)
    if not color_id:
        color = 'Siyah'  # Default to black if undefined color
        color_id = COLOR_ID_MAP[color]
        print(f"Unmapped color {color} for product {product.id}, defaulting to Siyah")
    
    # Initialize attributes if None
    if product.attributes is None:
        product.attributes = []
        changed = True
    
    # Check if existing attributes are a string and try to parse them
    if isinstance(product.attributes, str):
        try:
            product.attributes = json.loads(product.attributes)
            changed = True
            print(f"Converted string attributes to JSON for product {product.id}")
        except Exception as e:
            print(f"Error parsing attribute string for product {product.id}: {str(e)}")
            product.attributes = []
            changed = True
    
    # Find existing color attribute (attributeId 348 is for color in Trendyol)
    color_attribute_exists = False
    for i, attr in enumerate(product.attributes):
        if isinstance(attr, dict) and attr.get('attributeId') == 348:
            if attr.get('attributeValueId') != color_id:
                product.attributes[i]['attributeValueId'] = color_id
                changed = True
                print(f"Updated color attribute for product {product.id} to {color} (ID: {color_id})")
            color_attribute_exists = True
            break
    
    # Add color attribute if it doesn't exist
    if not color_attribute_exists:
        product.attributes.append({
            "attributeId": 348,
            "attributeValueId": color_id
        })
        changed = True
        print(f"Added color attribute for product {product.id}: {color} (ID: {color_id})")
    
    # Save if changes were made
    if changed:
        product.save()
        print(f"Saved changes to product {product.id}")
    
    return changed, color

def main():
    """Fix color attributes for Trendyol products"""
    # Get failed products with color-related errors
    failed_products = TrendyolProduct.objects.filter(
        batch_status='failed',
        status_message__contains='Renk'
    )
    print(f"Found {failed_products.count()} products with color-related failures")
    
    # Also get pending products that haven't been processed yet
    pending_products = TrendyolProduct.objects.filter(batch_status='pending')
    print(f"Found {pending_products.count()} pending products")
    
    # Get all products for comprehensive fix
    all_products = TrendyolProduct.objects.all()
    print(f"Total products in database: {all_products.count()}")
    
    # Process each failed product first
    fixed_count = 0
    retried_count = 0
    success_count = 0
    
    print("\n===== Processing failed products with color errors =====")
    for product in failed_products:
        print(f"Processing product {product.id}: {product.title}")
        print(f"Current status: {product.batch_status}, Error: {product.status_message}")
        
        # Fix color attribute
        fixed, color = fix_color_attribute(product)
        if fixed:
            fixed_count += 1
            
            # Try to resend the product
            try:
                print(f"Retrying product {product.id} with color {color}")
                result = sync_product_to_trendyol(product)
                
                if result and product.batch_id:
                    print(f"Successfully resubmitted product with batch ID: {product.batch_id}")
                    success_count += 1
                else:
                    print(f"Failed to resubmit product: {product.status_message}")
                    
                retried_count += 1
            except Exception as e:
                print(f"Error retrying product {product.id}: {str(e)}")
    
    # Now process pending products to ensure they have correct color format
    print("\n===== Processing pending products to prevent color errors =====")
    for product in pending_products:
        print(f"Processing pending product {product.id}: {product.title}")
        
        # Fix color attribute
        fixed, color = fix_color_attribute(product)
        if fixed:
            fixed_count += 1
            print(f"Fixed color attribute for pending product to {color}")
    
    print(f"\nSummary: Fixed {fixed_count} products, retried {retried_count}, succeeded {success_count}")

if __name__ == "__main__":
    main()
else:
    # When running with python manage.py shell < script.py
    main()