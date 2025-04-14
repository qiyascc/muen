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

# Configure logger to write to stdout
logger.remove()
logger.add(sys.stdout, level="INFO")

def main():
    """Fix attributes format to use numeric IDs for all products"""
    # NOT USED ANYMORE - Instead we allow the attributes to be fetched from the API
    # This is just for backward compatibility with existing code
    color_id_map = {}
    
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
                        # Preserve the attributeId but make sure it's an integer
                        attr_id = attr.get('attributeId')
                        attr_value = attr.get('attributeValueId')
                        
                        # Handle string ID format (like "color")
                        if attr_id == 'color':
                            # We'll keep the value as is, and set numeric flag to False
                            # This will trigger a category attributes refresh when the product is processed
                            new_attributes.append({
                                "attributeId": attr_id,
                                "attributeValueId": attr_value
                            })
                            logger.info(f"Keeping color attribute with original values for product {product.id}")
                        else:
                            # Try to convert both to integers
                            try:
                                attr_id = int(attr_id) if isinstance(attr_id, str) and attr_id.isdigit() else attr_id
                                attr_value = int(attr_value) if isinstance(attr_value, str) and attr_value.isdigit() else attr_value
                                new_attributes.append({
                                    "attributeId": attr_id,
                                    "attributeValueId": attr_value
                                })
                            except (ValueError, TypeError):
                                # Keep the original values
                                new_attributes.append({
                                    "attributeId": attr_id,
                                    "attributeValueId": attr_value
                                })
                                logger.warning(f"Could not convert attribute ID/value to integer: {attr_id}={attr_value}, keeping original")

                
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
    
    print(f"Updated {updated_count} products with corrected attribute format")

if __name__ == "__main__":
    main()