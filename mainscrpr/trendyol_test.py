"""
Trendyol API client test script

This script tests the new implementation of the Trendyol API client
to ensure that it can connect to the Trendyol API and perform basic operations.

Run with: python manage.py shell < trendyol_test.py
"""

import os
import sys
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models and API client
from trendyol.models import TrendyolAPIConfig, TrendyolProduct
from trendyol.api_client_new import (
    get_api_client, 
    TrendyolCategoryFinder, 
    find_brand_id_by_name,
    find_trendyol_category_id,
    get_required_attributes_for_category
)

def test_api_connection():
    """Test basic API connection"""
    logger.info("Testing API connection...")
    
    client = get_api_client()
    if not client:
        logger.error("Failed to get API client")
        return False
    
    logger.info(f"API client created: {client}")
    
    # Test the brands endpoint
    try:
        logger.info("Testing brands endpoint...")
        response = client.get(client.brands)
        if isinstance(response, dict) and response.get('error'):
            logger.error(f"API error: {response.get('message')}")
            return False
        
        logger.info(f"Found {len(response)} brands")
        logger.info(f"Sample brands: {response[:3]}")
        return True
    except Exception as e:
        logger.error(f"Error testing API: {str(e)}")
        return False

def test_category_finder():
    """Test category finder functionality"""
    logger.info("Testing category finder...")
    
    client = get_api_client()
    if not client:
        logger.error("Failed to get API client")
        return False
    
    finder = TrendyolCategoryFinder(client)
    
    # Test finding categories
    test_terms = ["T-shirt", "Pantolon", "Elbise", "Ayakkabı"]
    
    for term in test_terms:
        try:
            logger.info(f"Finding category for: {term}")
            category_id = finder.find_best_category(term)
            logger.info(f"Found category ID: {category_id}")
            
            # Get attributes for this category
            attrs = finder.get_category_attributes(category_id)
            attr_count = len(attrs.get('categoryAttributes', []))
            logger.info(f"Category has {attr_count} attributes")
            
            # Get required attributes
            req_attrs = get_required_attributes_for_category(category_id)
            logger.info(f"Required attributes: {json.dumps(req_attrs, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"Error testing category '{term}': {str(e)}")
    
    return True

def test_brand_lookup():
    """Test brand lookup functionality"""
    logger.info("Testing brand lookup...")
    
    test_brands = ["LC Waikiki", "LCW", "Nike", "Adidas"]
    
    for brand in test_brands:
        try:
            logger.info(f"Looking up brand: {brand}")
            brand_id = find_brand_id_by_name(brand)
            if brand_id:
                logger.info(f"Found brand ID: {brand_id}")
            else:
                logger.warning(f"Brand not found: {brand}")
        except Exception as e:
            logger.error(f"Error looking up brand '{brand}': {str(e)}")
    
    return True

def test_color_attribute_fix():
    """Test color attribute fix on a sample product"""
    from fix_color_attributes import fix_color_attribute
    
    logger.info("Testing color attribute fix...")
    
    # Get a sample product to test with
    product = TrendyolProduct.objects.filter(batch_status='pending').first()
    
    if not product:
        logger.warning("No pending products found to test")
        return False
    
    logger.info(f"Testing with product ID {product.id}: {product.title}")
    logger.info(f"Current attributes: {json.dumps(product.attributes, ensure_ascii=False)}")
    
    result = fix_color_attribute(product)
    
    # Refresh from database
    product.refresh_from_db()
    
    logger.info(f"Fix result: {result}")
    logger.info(f"Updated attributes: {json.dumps(product.attributes, ensure_ascii=False)}")
    
    return result

def main():
    """Run all tests"""
    logger.info("Starting Trendyol API client tests...")
    
    tests = [
        ("API Connection", test_api_connection),
        ("Category Finder", test_category_finder),
        ("Brand Lookup", test_brand_lookup),
        ("Color Attribute Fix", test_color_attribute_fix)
    ]
    
    results = {}
    for name, test_func in tests:
        logger.info(f"\n=== Running test: {name} ===\n")
        try:
            result = test_func()
            results[name] = "PASS" if result else "FAIL"
        except Exception as e:
            logger.error(f"Test '{name}' raised exception: {str(e)}")
            results[name] = "ERROR"
    
    logger.info("\n=== Test Results ===")
    for name, result in results.items():
        logger.info(f"{name}: {result}")

if __name__ == "__main__":
    main()