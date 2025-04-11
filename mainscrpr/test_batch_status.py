"""
Script to test batch status checking with enhanced logging.

This script tests the batch status checking functionality and logs the responses
to help diagnose issues with the API interaction.

Run this script with: python test_batch_status.py
"""

import os
import sys
import django
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

# Import required modules
from trendyol.models import TrendyolProduct
from trendyol.api_client import get_api_client

def test_batch_request(batch_id):
    """Test batch request status endpoint with a specific batch ID"""
    logger.info(f"Testing batch request status for batch ID: {batch_id}")
    
    client = get_api_client()
    if not client:
        logger.error("No API client available")
        return
    
    # Log the endpoint
    endpoint = client.products._get_batch_request_endpoint(batch_id)
    logger.info(f"Endpoint: {endpoint}")
    
    # Make the request and log the raw response
    try:
        response = client.products.get_batch_request_status(batch_id)
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Raw response: {response}")
        
        # Try to parse as JSON if it's a string
        if isinstance(response, str):
            try:
                parsed = json.loads(response)
                logger.info(f"Parsed response: {parsed}")
            except json.JSONDecodeError:
                logger.info("Response is not valid JSON")
    except Exception as e:
        logger.error(f"Error making request: {str(e)}")

def main():
    """Main test function"""
    # Get product with a batch ID
    product = TrendyolProduct.objects.filter(batch_id__isnull=False).first()
    if not product:
        logger.error("No product with batch ID found")
        return
    
    logger.info(f"Found product ID {product.id} with batch ID {product.batch_id}")
    
    # Test with the product's batch ID
    test_batch_request(product.batch_id)
    
    # If the batch ID contains a timestamp suffix, try with just the UUID part
    if '-' in product.batch_id:
        uuid_part = product.batch_id.split('-')[0]
        logger.info(f"Testing with just the UUID part: {uuid_part}")
        test_batch_request(uuid_part)

if __name__ == "__main__":
    main()