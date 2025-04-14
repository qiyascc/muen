"""
Test the updated Trendyol brand API integration.

This script tests the brands API with improved error handling and timeout management.
Run with: python manage.py shell < test_brand_api_updated.py
"""
import os
import sys
import django
import time

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.api_client import get_api_client, fetch_brands, _get_cached_brands_from_db
from trendyol.models import TrendyolBrand
from django.db import connection
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_brand_api')

# Set the Trendyol API client logger to debug
trendyol_logger = logging.getLogger('trendyol.api_client')
trendyol_logger.setLevel(logging.DEBUG)

# Ensure output appears in console
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)
trendyol_logger.addHandler(console_handler)

print("Starting brand API test...")

def test_fetch_brands():
    """Test fetching brands from Trendyol API with the improved implementation"""
    logger.info("=== Testing Trendyol Brand API with Improved Implementation ===")
    
    # Get the API client
    client = get_api_client()
    if not client:
        logger.error("Failed to create API client")
        return False
    
    logger.info(f"Successfully created API client with base URL: {client.base_url}")
    
    # Test direct brands API access
    logger.info("Testing direct brand API access...")
    start_time = time.time()
    response = client.brands.get_brands(page=0, size=50)  # Smaller batch to avoid timeouts
    elapsed = time.time() - start_time
    
    if isinstance(response, dict) and response.get('error'):
        logger.error(f"Direct API request failed: {response.get('message')}")
        logger.error(f"Error details: {response.get('details')}")
        return False
    
    if 'brands' not in response:
        logger.error("Direct API request did not return expected 'brands' field")
        logger.error(f"Response: {response}")
        return False
    
    brands = response.get('brands', [])
    logger.info(f"Direct API request successful - received {len(brands)} brands in {elapsed:.2f} seconds")
    
    # Test the improved fetch_brands function
    logger.info("Testing improved fetch_brands function...")
    start_time = time.time()
    brands = fetch_brands(page=0, size=50)  # Smaller batch to avoid timeouts
    elapsed = time.time() - start_time
    
    logger.info(f"Fetch brands function returned {len(brands)} brands in {elapsed:.2f} seconds")
    
    # Check if brands were cached in the database
    db_count = TrendyolBrand.objects.count()
    logger.info(f"Brand count in database: {db_count}")
    
    # Test fetching brands with smaller batch size
    logger.info("Testing with smaller batch size (10 brands)...")
    start_time = time.time()
    brands_small_batch = fetch_brands(page=0, size=10)
    elapsed = time.time() - start_time
    
    logger.info(f"Fetch with smaller batch returned {len(brands_small_batch)} brands in {elapsed:.2f} seconds")
    
    # Test database caching fallback
    logger.info("Testing database caching fallback...")
    cached_brands = _get_cached_brands_from_db()
    logger.info(f"Fallback returned {len(cached_brands)} brands from database cache")
    
    # Test query performance
    logger.info("Checking query performance...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM trendyol_trendyolbrand")
        brand_count = cursor.fetchone()[0]
    
    logger.info(f"Brand count via direct SQL: {brand_count}")
    
    logger.info("=== Brand API Testing Complete ===")
    return True

if __name__ == "__main__":
    success = test_fetch_brands()
    logger.info(f"Test completed with {'success' if success else 'failure'}")