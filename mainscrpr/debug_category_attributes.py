"""
Script to debug category attributes from Trendyol API.

This script specifically focuses on debugging the attribute format and examining 
what data is returned from the category attributes endpoint.

Run this script with: python manage.py shell < debug_category_attributes.py
"""

import django
import os
import sys
import json
import logging
from pprint import pprint

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client functions
from trendyol.models import TrendyolAPIConfig
from trendyol.trendyol_api_new import get_api_client_from_config, TrendyolAPI, TrendyolCategoryFinder

def debug_category_attributes(category_id):
    """Debug the category attributes for the given category ID"""
    print(f"Debugging category attributes for category ID: {category_id}")
    
    # Get API client
    api_client = get_api_client_from_config()
    if not api_client:
        print("Failed to get API client")
        return
    
    # Make direct API request to get category attributes
    endpoint = f"product/product-categories/{category_id}/attributes"
    print(f"Making GET request to {endpoint}")
    
    try:
        response = api_client.get(endpoint)
        
        # Log full response for debugging
        print("\n=== FULL CATEGORY ATTRIBUTES RESPONSE ===")
        pprint(response)
        print("=======================================\n")
        
        # Extract category attributes
        if not response or 'categoryAttributes' not in response:
            print(f"No valid category attributes found for category {category_id}")
            return
        
        attributes = response.get('categoryAttributes', [])
        print(f"Found {len(attributes)} attributes for category {category_id}")
        
        # Print detailed information about each attribute
        for i, attr in enumerate(attributes):
            print(f"\nAttribute {i+1}:")
            
            # Extract attribute ID and name
            attr_id = attr.get('attribute', {}).get('id')
            attr_name = attr.get('attribute', {}).get('name')
            required = attr.get('required', False)
            print(f"  ID: {attr_id}")
            print(f"  Name: {attr_name}")
            print(f"  Required: {required}")
            
            # Extract attribute values
            values = attr.get('attributeValues', [])
            print(f"  Values count: {len(values)}")
            
            # Print first 5 values as examples
            for j, value in enumerate(values[:5]):
                value_id = value.get('id')
                value_name = value.get('name')
                print(f"    Value {j+1}: ID={value_id}, Name={value_name}")
            
            if len(values) > 5:
                print(f"    ... and {len(values) - 5} more values")
        
        # Create a sample attribute using numeric IDs for demonstration
        print("\n=== SAMPLE ATTRIBUTE FORMAT FOR API REQUEST ===")
        sample_attributes = []
        
        # Try to find some common attributes like color, size, etc.
        for attr in attributes:
            attr_info = attr.get('attribute', {})
            attr_id = attr_info.get('id')
            attr_name = attr_info.get('name')
            
            if attr.get('required', False) and attr.get('attributeValues', []):
                # For required attributes with values, use the first value as an example
                value = attr.get('attributeValues', [])[0]
                value_id = value.get('id')
                value_name = value.get('name')
                
                sample_attributes.append({
                    "attributeId": attr_id,
                    "attributeValueId": value_id,
                    # Include these for reference - they won't be sent to API
                    "_attributeName": attr_name,
                    "_attributeValue": value_name
                })
        
        print("Sample attributes using numeric IDs (correct format):")
        pprint(sample_attributes)
        
        print("\nThe above format is correct for API requests. Ensure 'attributeId' and 'attributeValueId' are numeric!")
        
    except Exception as e:
        print(f"Error debugging category attributes: {str(e)}")

if __name__ == "__main__":
    # Test with multiple categories to find one that works
    categories_to_test = [1000, 2356, 1081, 944]
    
    for category_id in categories_to_test:
        print(f"\n\n----------------------------------------")
        print(f"TESTING CATEGORY ID: {category_id}")
        print(f"----------------------------------------\n")
        debug_category_attributes(category_id)