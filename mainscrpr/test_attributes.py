"""
Script to test retrieving and formatting category attributes with the updated TrendyolAPI client.

This script specifically focuses on testing the attribute format and ensuring it uses 
numeric IDs for attributeId and attributeValueId, which is required by Trendyol API.

Run this script with: python manage.py shell < test_attributes.py
"""

import django
import os
import sys
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI, TrendyolCategoryFinder

def test_category_attributes():
    """Test retrieving and formatting category attributes"""
    print("Testing category attributes retrieval and formatting")
    
    # Get API client
    api_client = get_api_client_from_config()
    if not api_client:
        print("Failed to get API client")
        return
    
    # Create category finder
    category_finder = TrendyolCategoryFinder(api_client)
    
    # Test category IDs - try different categories to find one that works
    test_categories = [2356, 1081, 1000, 944]  # Clothing categories
    
    for category_id in test_categories:
        print(f"\nTesting category ID: {category_id}")
        
        try:
            # Direct API request for attributes
            print(f"Retrieving attributes for category {category_id}...")
            attributes_response = api_client.get(f"product/product-categories/{category_id}/attributes")
            
            if not attributes_response or not isinstance(attributes_response, dict):
                print(f"No valid response for category {category_id}, trying next category")
                continue
                
            category_attrs = attributes_response.get('categoryAttributes', [])
            print(f"Retrieved {len(category_attrs)} attributes")
            
            if not category_attrs:
                print(f"No attributes found for category {category_id}, trying next category")
                continue
            
            # Print sample of raw attributes
            print("\nSample of raw attributes from API:")
            for i, attr in enumerate(category_attrs[:3], 1):
                print(f"Attribute {i}:")
                print(f"  Name: {attr['attribute'].get('name')}")
                print(f"  ID: {attr['attribute'].get('id')}")
                print(f"  Allow Custom: {attr.get('allowCustom')}")
                print(f"  Required: {attr.get('required')}")
                print(f"  Varianter: {attr.get('varianter')}")
                print(f"  Values: {len(attr.get('attributeValues', []))} values")
                
                # Print sample values if available
                if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                    print(f"  Sample value: {attr['attributeValues'][0].get('name')} (ID: {attr['attributeValues'][0].get('id')})")
            
            # Now test the attribute formatting function
            print("\nTesting _get_sample_attributes function...")
            formatted_attrs = category_finder._get_sample_attributes(category_id)
            
            print(f"Formatted {len(formatted_attrs)} attributes")
            
            # Print sample of formatted attributes
            print("\nSample of formatted attributes:")
            for i, attr in enumerate(formatted_attrs[:5], 1):
                print(f"Formatted Attribute {i}:")
                print(f"  attributeId: {attr.get('attributeId')} (type: {type(attr.get('attributeId')).__name__})")
                
                if 'attributeValueId' in attr:
                    print(f"  attributeValueId: {attr.get('attributeValueId')} (type: {type(attr.get('attributeValueId')).__name__})")
                
                if 'attributeName' in attr:
                    print(f"  attributeName: {attr.get('attributeName')}")
                
                if 'attributeValue' in attr:
                    print(f"  attributeValue: {attr.get('attributeValue')}")
                    
                if 'customAttributeValue' in attr:
                    print(f"  customAttributeValue: {attr.get('customAttributeValue')}")
            
            # This category worked, so we can stop testing
            break
            
        except Exception as e:
            print(f"Error testing category {category_id}: {str(e)}")
            print("Trying next category...")

if __name__ == "__main__":
    test_category_attributes()