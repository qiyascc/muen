"""
Test Trendyol API endpoints with new URL format.

This script tests that the updated endpoints are correctly configured
and work as expected. It verifies both the products endpoint and the
batch status endpoint.

Run this script with: python manage.py shell < test_api_endpoints.py
"""

import os
import sys
import json
import logging

# Setup Django environment
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol_app.models import TrendyolAPIConfig
from trendyol_app.services import TrendyolAPI

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trendyol_api_test')

def test_endpoints():
    """Test all Trendyol API endpoints with new URL format"""
    
    logger.info("Testing Trendyol API endpoints...")
    
    # Get active config
    try:
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            logger.error("No active Trendyol API config found")
            return
            
        logger.info(f"Using API config: ID={config.id}, Seller ID={config.seller_id}")
        
        # Initialize API client
        api = TrendyolAPI(config)
        
        # Test brands endpoint
        try:
            brands_endpoint = config.brands_endpoint
            logger.info(f"Testing BRANDS endpoint: {brands_endpoint}")
            
            brands_response = api.get(brands_endpoint)
            brand_count = len(brands_response) if isinstance(brands_response, list) else 0
            logger.info(f"Successfully accessed brands endpoint. Found {brand_count} brands.")
        except Exception as e:
            logger.error(f"Error accessing brands endpoint: {str(e)}")
        
        # Test categories endpoint
        try:
            categories_endpoint = config.categories_endpoint
            logger.info(f"Testing CATEGORIES endpoint: {categories_endpoint}")
            
            categories_response = api.get(categories_endpoint)
            category_count = len(categories_response) if isinstance(categories_response, list) else 0
            logger.info(f"Successfully accessed categories endpoint. Found {category_count} categories.")
        except Exception as e:
            logger.error(f"Error accessing categories endpoint: {str(e)}")
        
        # Test products endpoint format
        try:
            seller_id = config.seller_id
            products_endpoint = config.products_endpoint.format(sellerId=seller_id)
            logger.info(f"Testing PRODUCTS endpoint: {products_endpoint}")
            logger.info(f"Full URL would be: {config.base_url.rstrip('/')}/{products_endpoint}")
            
            # Note: We're not actually making this request as it requires a payload
            # Just validating the URL formation
            logger.info("Products endpoint URL validation successful")
        except Exception as e:
            logger.error(f"Error forming products endpoint URL: {str(e)}")
        
        # Test batch status endpoint format
        try:
            supplier_id = config.supplier_id or config.seller_id
            batch_id = "test-batch-id-12345"  # Fake ID for testing URL formation
            
            batch_endpoint = config.batch_status_endpoint.format(
                supplierId=supplier_id,
                batchId=batch_id
            )
            logger.info(f"Testing BATCH STATUS endpoint: {batch_endpoint}")
            logger.info(f"Full URL would be: {config.base_url.rstrip('/')}/{batch_endpoint}")
            
            # Note: We're not actually making this request as the batch ID is fake
            # Just validating the URL formation
            logger.info("Batch status endpoint URL validation successful")
        except Exception as e:
            logger.error(f"Error forming batch status endpoint URL: {str(e)}")
        
        logger.info("Endpoint testing completed")
        
    except Exception as e:
        logger.error(f"Error during endpoint testing: {str(e)}")

if __name__ == "__main__":
    test_endpoints()
    
# Execute if run as script
test_endpoints()