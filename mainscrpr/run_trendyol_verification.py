#!/usr/bin/env python
"""
Trendyol API Verification Script

This script provides a comprehensive verification of the Trendyol API integration.
It tests all major API functionality including connection, authentication, and core operations.

Usage:
    python run_trendyol_verification.py [--verbose] [--include-product-ops]

Options:
    --verbose           Show detailed logs and responses
    --include-product-ops   Include product creation/update tests (use with caution)
"""
import os
import sys
import json
import argparse
import logging
import django
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct
from trendyol.api_client import get_api_client, TrendyolCategoryFinder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('trendyol_verification')

def verify_api_config() -> Tuple[bool, Optional[TrendyolAPIConfig]]:
    """Verify that a valid Trendyol API configuration exists"""
    logger.info("Verifying API configuration...")
    
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("No active Trendyol API configuration found!")
        logger.error("Please configure one in the admin interface at /admin/trendyol/trendyolapiconfig/")
        return False, None
    
    # Check required fields
    required_fields = ['seller_id', 'api_key', 'api_secret', 'base_url']
    missing_fields = [field for field in required_fields if not getattr(config, field)]
    
    if missing_fields:
        logger.error(f"API configuration missing required fields: {', '.join(missing_fields)}")
        return False, None
    
    logger.info(f"API configuration valid: {config.name}")
    logger.info(f"Seller ID: {config.seller_id}")
    logger.info(f"Base URL: {config.base_url}")
    logger.info(f"User-Agent: {config.user_agent or f'{config.seller_id} - SelfIntegration'}")
    
    return True, config

def verify_api_client() -> Tuple[bool, Any]:
    """Verify that the API client can be initialized"""
    logger.info("Initializing API client...")
    
    client = get_api_client()
    if not client:
        logger.error("Failed to initialize API client!")
        return False, None
    
    logger.info("API client initialized successfully")
    logger.info(f"Base URL: {client.api_url}")
    logger.info(f"Supplier ID: {client.supplier_id}")
    logger.info(f"User-Agent: {client.user_agent}")
    
    return True, client

def test_brands_api(client) -> bool:
    """Test the Brands API"""
    logger.info("Testing Brands API...")
    
    try:
        response = client.brands.get_brands(page=0, size=10)
        
        if 'brands' not in response:
            logger.error("Brands API response missing 'brands' field")
            logger.error(f"Response: {json.dumps(response, indent=2)}")
            return False
        
        brands = response['brands']
        logger.info(f"Successfully fetched {len(brands)} brands")
        
        # Log the first few brands
        for i, brand in enumerate(brands[:3]):
            logger.info(f"Brand {i+1}: {brand.get('name')} (ID: {brand.get('id')})")
        
        return True
    except Exception as e:
        logger.error(f"Error testing Brands API: {str(e)}")
        return False

def test_categories_api(client) -> bool:
    """Test the Categories API"""
    logger.info("Testing Categories API...")
    
    try:
        response = client.categories.get_categories()
        
        if 'categories' not in response:
            logger.error("Categories API response missing 'categories' field")
            logger.error(f"Response: {json.dumps(response, indent=2)}")
            return False
        
        categories = response['categories']
        logger.info(f"Successfully fetched {len(categories)} top-level categories")
        
        # Log the first few categories
        for i, category in enumerate(categories[:3]):
            logger.info(f"Category {i+1}: {category.get('name')} (ID: {category.get('id')})")
        
        # Test category attributes for the first category
        if categories:
            category_id = categories[0]['id']
            logger.info(f"Testing category attributes for category ID {category_id}...")
            
            attr_response = client.categories.get_category_attributes(category_id)
            
            if 'categoryAttributes' not in attr_response:
                logger.error("Category attributes response missing 'categoryAttributes' field")
                logger.error(f"Response: {json.dumps(attr_response, indent=2)}")
                return False
            
            attributes = attr_response['categoryAttributes']
            logger.info(f"Successfully fetched {len(attributes)} attributes for category ID {category_id}")
            
            # Log the first few attributes
            for i, attr in enumerate(attributes[:3]):
                logger.info(f"Attribute {i+1}: {attr.get('name')} (ID: {attr.get('id')})")
        
        return True
    except Exception as e:
        logger.error(f"Error testing Categories API: {str(e)}")
        return False

def test_products_api(client) -> bool:
    """Test the Products API (read-only operations)"""
    logger.info("Testing Products API (list products)...")
    
    try:
        response = client.products.get_products(page=0, size=10)
        
        # Response format can vary, but shouldn't contain an error
        if 'error' in response:
            logger.error("Products API returned an error")
            logger.error(f"Error: {response.get('message')}")
            logger.error(f"Details: {json.dumps(response.get('details', {}), indent=2)}")
            return False
        
        logger.info("Successfully retrieved products list")
        
        # Log the response structure
        if 'content' in response:
            logger.info(f"Found {len(response['content'])} products")
            
            # Log the first few products
            for i, product in enumerate(response['content'][:3]):
                logger.info(f"Product {i+1}: {product.get('title')} (Barcode: {product.get('barcode')})")
        
        return True
    except Exception as e:
        logger.error(f"Error testing Products API: {str(e)}")
        return False

def test_category_finder() -> bool:
    """Test the TrendyolCategoryFinder"""
    logger.info("Testing TrendyolCategoryFinder...")
    
    try:
        finder = TrendyolCategoryFinder()
        
        categories = finder.categories
        if not categories:
            logger.error("Category finder returned no categories")
            return False
        
        logger.info(f"Category finder initialized with {len(categories)} top-level categories")
        
        # Test similarity calculation
        test_pairs = [
            ("t-shirt", "t-shirt", 1.0),
            ("t-shirt", "tshirt", 0.7),
            ("men's jeans", "mens jeans", 0.8)
        ]
        
        for str1, str2, expected_min in test_pairs:
            similarity = finder._calculate_similarity(str1, str2)
            logger.info(f"Similarity between '{str1}' and '{str2}': {similarity:.2f}")
            
            if similarity < expected_min:
                logger.error(f"Similarity score too low: {similarity:.2f} < {expected_min}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error testing TrendyolCategoryFinder: {str(e)}")
        return False

def verify_model_structure() -> bool:
    """Verify that the TrendyolProduct model has all required fields"""
    logger.info("Verifying TrendyolProduct model structure...")
    
    # Define required fields for Trendyol products
    required_fields = [
        'title', 'description', 'barcode', 'product_main_id', 'stock_code',
        'brand_name', 'brand_id', 'category_name', 'category_id',
        'price', 'quantity', 'vat_rate', 'currency_type',
        'image_url', 'attributes', 'batch_id', 'batch_status'
    ]
    
    # Get the model fields
    fields = [field.name for field in TrendyolProduct._meta.fields]
    
    # Check for missing fields
    missing_fields = [field for field in required_fields if field not in fields]
    
    if missing_fields:
        logger.error(f"TrendyolProduct model missing required fields: {', '.join(missing_fields)}")
        return False
    
    logger.info("TrendyolProduct model has all required fields")
    return True

def main():
    """Main verification function"""
    parser = argparse.ArgumentParser(description='Verify Trendyol API integration')
    parser.add_argument('--verbose', action='store_true', help='Show detailed logs and responses')
    parser.add_argument('--include-product-ops', action='store_true', help='Include product creation/update tests')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    print("=" * 80)
    print(f"Trendyol API Verification - {datetime.now()}")
    print("=" * 80)
    
    # Verification steps
    config_ok, config = verify_api_config()
    if not config_ok:
        sys.exit(1)
    
    client_ok, client = verify_api_client()
    if not client_ok:
        sys.exit(1)
    
    # Test API functionality
    brands_ok = test_brands_api(client)
    categories_ok = test_categories_api(client)
    products_ok = test_products_api(client)
    
    # Test helper components
    category_finder_ok = test_category_finder()
    model_structure_ok = verify_model_structure()
    
    # Summarize results
    print("\n" + "=" * 80)
    print("Verification Results")
    print("=" * 80)
    print(f"API Configuration: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"API Client: {'✅ PASS' if client_ok else '❌ FAIL'}")
    print(f"Brands API: {'✅ PASS' if brands_ok else '❌ FAIL'}")
    print(f"Categories API: {'✅ PASS' if categories_ok else '❌ FAIL'}")
    print(f"Products API (list): {'✅ PASS' if products_ok else '❌ FAIL'}")
    print(f"Category Finder: {'✅ PASS' if category_finder_ok else '❌ FAIL'}")
    print(f"Model Structure: {'✅ PASS' if model_structure_ok else '❌ FAIL'}")
    
    # Overall result
    all_ok = config_ok and client_ok and brands_ok and categories_ok and products_ok and category_finder_ok and model_structure_ok
    
    print("\n" + "=" * 80)
    if all_ok:
        print("✅ OVERALL VERIFICATION: PASSED")
        print("    The Trendyol API integration is correctly configured and functional.")
    else:
        print("❌ OVERALL VERIFICATION: FAILED")
        print("    Please fix the issues reported above.")
    print("=" * 80)
    
    # Return exit code
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())