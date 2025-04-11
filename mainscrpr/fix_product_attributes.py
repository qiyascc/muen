"""
Script to fix all product attributes to use the correct numeric format.

This script will update all TrendyolProduct instances to ensure their attributes
are using the correct format with numeric IDs, especially for color attributes.

Run this script with: python manage.py shell < fix_product_attributes.py
"""
import os
import sys
import json
import logging
from datetime import datetime

# Set up Django environment
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.models import TrendyolProduct
from django.utils import timezone
from loguru import logger

def main():
    """Fix attributes format to use numeric IDs for all products"""
    # Color ID mapping to use numeric IDs instead of string values
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
        'Kahverengi': 1010,
        'Ekru': 1011,
        'Bej': 1012,
        'Lacivert': 1013,
        'Turuncu': 1014,
        'Krem': 1015
    }
    
    # Get all products
    products = TrendyolProduct.objects.all()
    print(f"Found {len(products)} products to process")
    
    updated_count = 0
    
    for product in products:
        if not product.attributes:
            logger.info(f"Product {product.id} has no attributes, skipping")
            continue
            
        # Check if attributes are in dictionary format
        if isinstance(product.attributes, dict):
            # Initialize new attributes list
            new_attributes = []
            
            # Process each attribute
            for key, value in product.attributes.items():
                if key == 'color' and isinstance(value, str):
                    # Use attribute ID 348 for color with proper numeric value ID
                    color_numeric_id = color_id_map.get(value)
                    if color_numeric_id:
                        new_attributes.append({
                            "attributeId": 348, 
                            "attributeValueId": color_numeric_id
                        })
                        print(f"Converted color '{value}' to numeric ID {color_numeric_id} for product {product.id}")
                    else:
                        # If we don't have a mapping, use a default
                        logger.warning(f"No color ID mapping for '{value}', using default for product {product.id}")
                        new_attributes.append({
                            "attributeId": 348, 
                            "attributeValueId": 1001  # Default to white
                        })
                else:
                    # For other attributes, try to convert to integers
                    try:
                        attr_id = int(key) if isinstance(key, str) and key.isdigit() else (348 if key == 'color' else key)
                        # Try to convert attributeValueId to integer if possible
                        attr_value_id = int(value) if isinstance(value, str) and value.isdigit() else value
                        new_attributes.append({
                            "attributeId": attr_id, 
                            "attributeValueId": attr_value_id
                        })
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert attribute {key}={value} for product {product.id}")
            
            # Update product with new attributes format
            if new_attributes:
                product.attributes = new_attributes
                product.updated_at = timezone.now()
                product.save()
                updated_count += 1
                logger.info(f"Updated attributes for product {product.id}")
            else:
                logger.warning(f"No valid attributes found for product {product.id}")
        elif isinstance(product.attributes, list):
            # Check if attributes are already in correct format
            has_numeric_attrs = all(
                isinstance(attr.get('attributeId'), int) and 
                isinstance(attr.get('attributeValueId'), int)
                for attr in product.attributes if 'attributeId' in attr and 'attributeValueId' in attr
            )
            
            if has_numeric_attrs:
                logger.info(f"Product {product.id} already has correctly formatted attributes")
            else:
                # Convert string IDs to numeric IDs
                new_attributes = []
                for attr in product.attributes:
                    if 'attributeId' in attr and 'attributeValueId' in attr:
                        # Special handling for color attribute
                        if attr.get('attributeId') == 'color' or attr.get('attributeId') == '348':
                            color_value = attr.get('attributeValueId')
                            if isinstance(color_value, str):
                                color_numeric_id = color_id_map.get(color_value)
                                if color_numeric_id:
                                    new_attributes.append({
                                        "attributeId": 348,
                                        "attributeValueId": color_numeric_id
                                    })
                                    logger.info(f"Converted color '{color_value}' to numeric ID {color_numeric_id} for product {product.id}")
                                else:
                                    # If we don't have a mapping, use a default
                                    logger.warning(f"No color ID mapping for '{color_value}', using default for product {product.id}")
                                    new_attributes.append({
                                        "attributeId": 348,
                                        "attributeValueId": 1001  # Default to white
                                    })
                            else:
                                new_attributes.append({
                                    "attributeId": 348,
                                    "attributeValueId": color_value
                                })
                        else:
                            # For other attributes, try to convert to integers
                            try:
                                attr_id = int(attr['attributeId']) if isinstance(attr['attributeId'], str) and attr['attributeId'].isdigit() else attr['attributeId']
                                attr_value_id = int(attr['attributeValueId']) if isinstance(attr['attributeValueId'], str) and attr['attributeValueId'].isdigit() else attr['attributeValueId']
                                new_attributes.append({
                                    "attributeId": attr_id,
                                    "attributeValueId": attr_value_id
                                })
                            except (ValueError, TypeError):
                                logger.warning(f"Could not convert attribute {attr} for product {product.id}")
                
                # Update product with new attributes format
                if new_attributes:
                    product.attributes = new_attributes
                    product.updated_at = timezone.now()
                    product.save()
                    updated_count += 1
                    logger.info(f"Updated attributes for product {product.id}")
                else:
                    logger.warning(f"No valid attributes found for product {product.id}")
        else:
            logger.warning(f"Product {product.id} has attributes in unknown format: {type(product.attributes)}")
    
    logger.info(f"Updated {updated_count} products with corrected attribute format")

if __name__ == "__main__":
    main()