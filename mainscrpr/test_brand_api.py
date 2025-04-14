#!/usr/bin/env python
"""
Script to test the Trendyol Brand API endpoint.

This script tests the brand API endpoint to ensure it correctly retrieves brand data.

Run this script with: python manage.py shell < test_brand_api.py
"""
import os
import sys
import json
import logging
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
import django
django.setup()

from trendyol.models import TrendyolAPIConfig, TrendyolBrand
from trendyol.api_client import get_api_client, fetch_brands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('brand_api_test')

def test_brands_api():
    """Test the Brand API endpoint"""
    logger.info("Testing Trendyol Brand API endpoint...")
    
    # Get API client
    client = get_api_client()
    if not client:
        logger.error("Failed to initialize API client")
        return False
    
    logger.info(f"Using API client with base URL: {client.base_url}")
    
    # Test brand endpoint directly
    try:
        logger.info("Testing brands endpoint...")
        endpoint = client.brands._get_brands_endpoint()
        logger.info(f"Using endpoint: {endpoint}")
        
        response = client.make_request('GET', endpoint, params={'page': 0, 'size': 10})
        
        if 'brands' not in response:
            logger.error("Brands API response missing 'brands' field")
            logger.error(f"Response: {json.dumps(response, indent=2)}")
            
            # Try alternate endpoint
            logger.info("Trying alternative endpoint /suppliers/brands...")
            alt_endpoint = '/suppliers/brands'
            logger.info(f"Using alternate endpoint: {alt_endpoint}")
            
            alt_response = client.make_request('GET', alt_endpoint, params={'page': 0, 'size': 10})
            
            if 'brands' not in alt_response:
                logger.error("Alternative brands endpoint also failed")
                logger.error(f"Response: {json.dumps(alt_response, indent=2)}")
                
                # Try more alternate endpoints
                logger.info("Trying second alternative endpoint /brands/suppliers...")
                alt_endpoint2 = '/brands/suppliers'
                logger.info(f"Using second alternate endpoint: {alt_endpoint2}")
                
                alt_response2 = client.make_request('GET', alt_endpoint2, params={'page': 0, 'size': 10})
                
                if 'brands' not in alt_response2:
                    logger.error("Second alternative brands endpoint also failed")
                    logger.error(f"Response: {json.dumps(alt_response2, indent=2)}")
                    
                    # Try integration/suppliers endpoint
                    logger.info("Trying third alternative endpoint /integration/suppliers/{seller_id}/brands...")
                    seller_id = client.supplier_id
                    alt_endpoint3 = f'/integration/suppliers/{seller_id}/brands'
                    logger.info(f"Using third alternate endpoint: {alt_endpoint3}")
                    
                    alt_response3 = client.make_request('GET', alt_endpoint3, params={'page': 0, 'size': 10})
                    
                    if 'brands' not in alt_response3:
                        # Try another variation
                        logger.info("Trying fourth alternative endpoint /suppliers/{seller_id}/brands...")
                        alt_endpoint4 = f'/suppliers/{seller_id}/brands'
                        logger.info(f"Using fourth alternate endpoint: {alt_endpoint4}")
                        
                        alt_response4 = client.make_request('GET', alt_endpoint4, params={'page': 0, 'size': 10})
                        
                        if 'brands' not in alt_response4:
                            # Try the endpoint from product creation example
                            logger.info("Trying fifth alternative endpoint /integration/product/brands...")
                            alt_endpoint5 = '/integration/product/brands'
                            logger.info(f"Using fifth alternate endpoint: {alt_endpoint5}")
                            
                            alt_response5 = client.make_request('GET', alt_endpoint5, params={'page': 0, 'size': 10})
                            
                            if 'brands' not in alt_response5:
                                logger.error("All brand endpoint variations failed")
                                return False
                            else:
                                logger.info(f"Fifth alternative endpoint succeeded! Found {len(alt_response5['brands'])} brands")
                                brands = alt_response5['brands']
                                logger.info("Updating BrandsAPI endpoint in api_client.py...")
                                logger.info(f"Please update _get_brands_endpoint() to return '{alt_endpoint5}'")
                                return True
                        else:
                            logger.info(f"Fourth alternative endpoint succeeded! Found {len(alt_response4['brands'])} brands")
                            brands = alt_response4['brands']
                            logger.info("Updating BrandsAPI endpoint in api_client.py...")
                            logger.info(f"Please update _get_brands_endpoint() to return '{alt_endpoint4}'")
                            return True
                    else:
                        logger.info(f"Third alternative endpoint succeeded! Found {len(alt_response3['brands'])} brands")
                        brands = alt_response3['brands']
                        logger.info("Updating BrandsAPI endpoint in api_client.py...")
                        logger.info(f"Please update _get_brands_endpoint() to return '{alt_endpoint3}'")
                        return True
                else:
                    logger.info(f"Second alternative endpoint succeeded! Found {len(alt_response2['brands'])} brands")
                    brands = alt_response2['brands']
                    logger.info("Updating BrandsAPI endpoint in api_client.py...")
                    logger.info("Please update _get_brands_endpoint() to return '/brands/suppliers'")
                    return True
            else:
                logger.info(f"Alternative endpoint succeeded! Found {len(alt_response['brands'])} brands")
                brands = alt_response['brands']
                logger.info("Updating BrandsAPI endpoint in api_client.py...")
                logger.info("Please update _get_brands_endpoint() to return '/suppliers/brands'")
                return True
        
        # Process the brand data
        brands = response['brands']
        logger.info(f"Successfully fetched {len(brands)} brands")
        
        # Log the first few brands
        for i, brand in enumerate(brands[:3]):
            logger.info(f"Brand {i+1}: {brand.get('name')} (ID: {brand.get('id')})")
        
        return True
    
    except Exception as e:
        logger.error(f"Error testing brands API: {e}")
        return False

def test_fetch_brands():
    """Test the fetch_brands function"""
    logger.info("Testing fetch_brands function...")
    
    try:
        brands = fetch_brands()
        if not brands:
            logger.error("Failed to fetch any brands")
            return False
        
        logger.info(f"Successfully fetched and processed {len(brands)} brands")
        
        # Check database
        brand_count = TrendyolBrand.objects.count()
        logger.info(f"Database now contains {brand_count} brands")
        
        return True
    except Exception as e:
        logger.error(f"Error testing fetch_brands: {e}")
        return False

def main():
    """Main function to test brand API endpoints"""
    logger.info("Starting Trendyol Brand API testing...")
    
    # Get API config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("No active Trendyol API configuration found")
        return
    
    logger.info(f"Using API config: {config.name}")
    logger.info(f"Base URL: {config.base_url}")
    logger.info(f"Supplier ID: {config.supplier_id or config.seller_id}")
    
    # Test brand API
    if test_brands_api():
        logger.info("Brand API endpoint test successful")
    else:
        logger.error("Brand API endpoint test failed")
        return
    
    # Test fetch_brands function
    if test_fetch_brands():
        logger.info("fetch_brands function test successful")
    else:
        logger.error("fetch_brands function test failed")
        return
    
    logger.info("All brand API tests completed successfully")

if __name__ == "__main__":
    main()
else:
    # When running as a Django shell script
    main()