"""
Script to test the attribute format handling.

This script tests fetching category attributes and how the system handles
the 'color' attribute properly without using string ID.

Run this script with: python manage.py shell < test_attribute_format.py
"""
import os
import sys
import json
from datetime import datetime

# Set up Django environment
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.api_client import get_api_client, get_required_attributes_for_category
from trendyol.category_finder_new import TrendyolCategoryFinder
from loguru import logger

# Configure logger to write to stdout
logger.remove()
logger.add(sys.stdout, level="INFO")

def test_category_attributes(category_id=2356):  # Default: Men's clothing
    """Test fetching category attributes"""
    print(f"Testing category attributes for category ID: {category_id}")
    
    # Debug - Ensure the test script is running
    print("Debug - Test script is running")
    """Test fetching category attributes"""
    print(f"Testing category attributes for category ID: {category_id}")
    
    # Get API client
    client = get_api_client()
    if not client:
        print("Could not get API client")
        return
    
    # Initialize the category finder
    finder = TrendyolCategoryFinder(client)
    
    # Test getting attributes directly from finder
    print("Testing get_required_attributes method from TrendyolCategoryFinder:")
    try:
        attributes = finder.get_required_attributes(category_id)
        print(f"Found {len(attributes)} attributes")
        print(json.dumps(attributes, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error getting attributes from finder: {str(e)}")
    
    # Test get_required_attributes_for_category function
    print("\nTesting get_required_attributes_for_category function:")
    try:
        attributes = get_required_attributes_for_category(category_id)
        print(f"Found {len(attributes)} attributes")
        print(json.dumps(attributes, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error getting attributes from function: {str(e)}")
    
    # Test our special attribute handling
    print("\nTesting attribute format handling:")
    test_attributes = [
        {
            "attributeId": "color",
            "attributeValueId": "Yeşil"
        },
        {
            "attributeId": 1205,
            "attributeValueId": 10621826
        }
    ]
    
    print("Original attributes:")
    print(json.dumps(test_attributes, indent=2, ensure_ascii=False))
    
    # Process attributes like we do in prepare_product_data
    existing_attr_ids = set()
    color_attribute_exists = False
    
    # Pre-process attributes to fix the color attribute issue
    fixed_attributes = []
    for attr in test_attributes:
        if attr.get('attributeId') == 'color':
            color_attribute_exists = True
            print(f"Found color attribute with string ID. Value: {attr.get('attributeValueId')}")
        else:
            fixed_attributes.append(attr)
            existing_attr_ids.add(attr.get('attributeId'))
    
    # Replace the original attributes with fixed ones (without 'color')
    processed_attributes = fixed_attributes
    
    print("Processed attributes (after removing string 'color'):")
    print(json.dumps(processed_attributes, indent=2, ensure_ascii=False))
    
    # Add required attributes from API
    print("Adding required attributes from API...")
    for attr in attributes:
        attr_id = attr.get('attributeId')
        if attr_id not in existing_attr_ids:
            processed_attributes.append(attr)
    
    print("Final attributes:")
    print(json.dumps(processed_attributes, indent=2, ensure_ascii=False))
    
    # Check if we have a proper numeric color attribute now
    color_attributes = [attr for attr in processed_attributes 
                        if isinstance(attr.get('attributeId'), int) and 
                        attr.get('attributeName', '').lower() in ['renk', 'color']]
    
    if color_attributes:
        print(f"Found proper color attribute(s): {json.dumps(color_attributes, ensure_ascii=False)}")
    else:
        print("No proper color attribute found")

def main():
    """Main test function"""
    test_category_attributes()
    
    # Try with a different category
    test_category_attributes(3283)  # Baby clothing

if __name__ == "__main__":
    main()