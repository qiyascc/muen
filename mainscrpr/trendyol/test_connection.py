import logging
import os
import json
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from loguru import logger
from .api_client import get_api_client, fetch_brands, fetch_categories

def test_trendyol_api_connection():
    """Test connection to Trendyol API and log response details"""
    logger.info("Testing Trendyol API connection...")
    
    # Get the API client
    client = get_api_client()
    if not client:
        logger.error("Failed to initialize API client. Check API configuration.")
        return False
    
    logger.info(f"API client initialized with base URL: {client.api_url}")
    logger.info(f"Using supplier ID: {client.supplier_id}")
    logger.info(f"Using User-Agent: {client.user_agent}")
    
    # Test brands API
    try:
        logger.info("Testing brands API...")
        response = client.brands.get_brands(page=0, size=10)
        if 'brands' in response:
            logger.success(f"Successfully connected to brands API. Found {len(response['brands'])} brands.")
            for brand in response['brands'][:3]:  # Show first 3 brands
                logger.info(f"Brand: {brand.get('name')} (ID: {brand.get('id')})")
            return True
        else:
            logger.error(f"Failed to fetch brands. Response: {json.dumps(response)}")
            return False
    except Exception as e:
        logger.error(f"Error testing brands API: {str(e)}")
        return False

def test_categories_api():
    """Test connection to Trendyol Categories API"""
    logger.info("Testing Trendyol Categories API...")
    
    # Get the API client
    client = get_api_client()
    if not client:
        logger.error("Failed to initialize API client. Check API configuration.")
        return False
    
    # Test categories API
    try:
        logger.info("Testing categories API...")
        response = client.categories.get_categories()
        if 'categories' in response:
            logger.success(f"Successfully connected to categories API. Found {len(response['categories'])} top-level categories.")
            for category in response['categories'][:3]:  # Show first 3 categories
                logger.info(f"Category: {category.get('name')} (ID: {category.get('id')})")
            return True
        else:
            logger.error(f"Failed to fetch categories. Response: {json.dumps(response)}")
            return False
    except Exception as e:
        logger.error(f"Error testing categories API: {str(e)}")
        return False

def test_fetch_and_store():
    """Test fetching and storing brands and categories in the database"""
    logger.info("Testing fetch and store functionality...")
    
    # Test fetching brands
    logger.info("Fetching brands...")
    brands = fetch_brands()
    if brands:
        logger.success(f"Successfully fetched {len(brands)} brands and stored them in the database.")
    else:
        logger.error("Failed to fetch brands.")
    
    # Test fetching categories
    logger.info("Fetching categories...")
    categories = fetch_categories()
    if categories:
        logger.success(f"Successfully fetched {len(categories)} categories and stored them in the database.")
    else:
        logger.error("Failed to fetch categories.")
    
    return bool(brands and categories)

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the tests
    connection_ok = test_trendyol_api_connection()
    categories_ok = test_categories_api()
    fetch_ok = test_fetch_and_store()
    
    if connection_ok and categories_ok and fetch_ok:
        logger.success("All tests passed! API connection is working correctly.")
    else:
        logger.error("Some tests failed. Check logs for details.")