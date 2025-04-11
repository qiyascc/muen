"""
Script to test batch status checking with enhanced logging.

This script tests the batch status checking functionality and logs the responses
to help diagnose issues with the API interaction.

Run this script with: python manage.py shell < test_batch_status.py
"""

import os
import sys
import logging
import django
from loguru import logger

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct
from trendyol.api_client import check_product_batch_status, get_api_client

def test_batch_request(batch_id):
    """Test batch request status endpoint with a specific batch ID"""
    client = get_api_client()
    if not client:
        print("No API client available")
        return
    
    # Configure logger to print to console
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    
    print(f"Testing batch status for ID: {batch_id}")
    
    # Test direct API request first
    response = client.products.get_batch_request_status(batch_id)
    print(f"Raw API response: {response}")
    
    # Create a temporary product for testing
    product = TrendyolProduct(
        batch_id=batch_id,
        title="Test Product",
        barcode=f"TESTBARCODE{batch_id}",
        batch_status="processing"
    )
    
    # Test the status checking function
    status = check_product_batch_status(product)
    print(f"Status after checking: {status}")
    print(f"Product batch_status: {product.batch_status}")
    print(f"Product status_message: {product.status_message}")

def main():
    """Main test function"""
    # Configure logger
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    
    print("Starting batch status test")
    
    # Get all products with batch IDs
    products_with_batch = TrendyolProduct.objects.exclude(batch_id__isnull=True).exclude(batch_id='')
    print(f"Found {products_with_batch.count()} products with batch IDs")
    
    # Check and show status for all products with batch IDs
    for product in products_with_batch:
        print(f"\nChecking product {product.id}: {product.title}")
        print(f"Current status: {product.batch_status}, Batch ID: {product.batch_id}")
        
        # Check status
        status = check_product_batch_status(product)
        
        print(f"Status after checking: {status}")
        print(f"Product status message: {product.status_message}")
    
    # Get all failed products
    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
    print(f"\nFound {failed_products.count()} failed products")
    
    # Show details for failed products
    for product in failed_products:
        print(f"Failed product {product.id}: {product.title}")
        print(f"Error message: {product.status_message}")

if __name__ == "__main__":
    main()