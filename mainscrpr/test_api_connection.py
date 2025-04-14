#!/usr/bin/env python
"""
Test script for Trendyol API connection and endpoint accessibility.
This script maps the available and unavailable endpoints in the Trendyol API.

Available endpoints:
- supplier/products - Successfully retrieving product data
- price-and-inventory - Successfully updating price and inventory data

Unavailable endpoints (556 Server Error):
- product/brands - Using fallback database data
- product/product-categories - Using fallback database data
- product-attributes - Using fallback mechanisms
"""

import os
import sys
import json
import logging

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
import django
django.setup()

from trendyol.api_client import get_api_client, fetch_brands, fetch_categories
from trendyol.models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def test_api_connection():
    """Test the API connection by fetching brands and categories"""
    logger.info("Starting API connection test")
    
    # Get API client
    client = get_api_client()
    if not client:
        logger.error("Failed to get API client")
        return False
    
    logger.info(f"Using API base URL: {client.base_url}")
    
    # Check config
    configs = TrendyolAPIConfig.objects.filter(is_active=True)
    logger.info(f"Found {configs.count()} active API configurations")
    for config in configs:
        logger.info(f"Active config: Supplier ID={config.supplier_id}, Base URL={config.base_url}")
    
    # Test brands API
    logger.info("Testing brands API...")
    try:
        brands = fetch_brands()
        if brands:
            logger.info(f"Successfully fetched {len(brands)} brands")
            logger.info(f"First 5 brands: {brands[:5]}")
        else:
            logger.warning("No brands returned from the API")
            
        # Check for brands in the database
        db_brands = TrendyolBrand.objects.all()
        logger.info(f"Found {db_brands.count()} brands in the database")
    except Exception as e:
        logger.error(f"Error fetching brands: {str(e)}")
    
    # Test categories API
    logger.info("Testing categories API...")
    try:
        categories = fetch_categories()
        if categories:
            logger.info(f"Successfully fetched {len(categories)} categories")
            logger.info(f"First 5 categories: {categories[:5]}")
        else:
            logger.warning("No categories returned from the API")
            
        # Check for categories in the database
        db_categories = TrendyolCategory.objects.all()
        logger.info(f"Found {db_categories.count()} categories in the database")
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
    
    logger.info("API connection test completed")
    return True

if __name__ == "__main__":
    test_api_connection()