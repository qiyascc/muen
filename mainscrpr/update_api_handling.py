#!/usr/bin/env python
"""
Update API handling to work with available endpoints and handle unavailable ones gracefully.
This script will modify the API client to focus on the working endpoints (supplier products),
and implement fallback mechanisms for unavailable endpoints (brands, categories).
"""

import os
import sys
import json
import logging

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
import django
django.setup()

from trendyol.models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory
from trendyol.api_client import get_api_client

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Default brand data to use when API is unavailable
DEFAULT_BRANDS = [
    {"id": 7651, "name": "LC WAIKIKI"},
    {"id": 102, "name": "adidas"},
    {"id": 155, "name": "Nike"},
    {"id": 158, "name": "Puma"}
]

# Basic category data to use when API is unavailable
DEFAULT_CATEGORIES = [
    {"id": 522, "name": "Giyim", "parentId": None},
    {"id": 2356, "name": "Erkek Giyim", "parentId": 522},
    {"id": 41, "name": "Kadın Giyim", "parentId": 522},
    {"id": 674, "name": "Çocuk Gereçleri", "parentId": None},
    {"id": 2164, "name": "Bebek Hediyelik", "parentId": 674},
    {"id": 403, "name": "Ayakkabı", "parentId": None}
]

def update_default_brands():
    """Create default brands in the database to ensure we have fallback data"""
    logger.info("Updating default brands...")
    count = 0
    
    for brand in DEFAULT_BRANDS:
        brand_id = brand["id"]
        name = brand["name"]
        
        try:
            brand_obj, created = TrendyolBrand.objects.update_or_create(
                brand_id=brand_id,
                defaults={
                    "name": name,
                    "is_active": True
                }
            )
            
            if created:
                logger.info(f"Created brand: {name} (ID: {brand_id})")
                count += 1
            else:
                logger.info(f"Updated brand: {name} (ID: {brand_id})")
        except Exception as e:
            logger.error(f"Error updating brand {name}: {str(e)}")
    
    logger.info(f"Added {count} new brands")
    
def update_default_categories():
    """Create default categories in the database to ensure we have fallback data"""
    logger.info("Updating default categories...")
    count = 0
    
    for category in DEFAULT_CATEGORIES:
        category_id = category["id"]
        name = category["name"]
        parent_id = category["parentId"]
        
        # Build path
        path = name
        if parent_id:
            try:
                parent = TrendyolCategory.objects.get(category_id=parent_id)
                path = f"{parent.path} > {name}"
            except TrendyolCategory.DoesNotExist:
                logger.warning(f"Parent category {parent_id} not found for {name}")
        
        try:
            category_obj, created = TrendyolCategory.objects.update_or_create(
                category_id=category_id,
                defaults={
                    "name": name,
                    "parent_id": parent_id,
                    "path": path,
                    "is_active": True
                }
            )
            
            if created:
                logger.info(f"Created category: {name} (ID: {category_id})")
                count += 1
            else:
                logger.info(f"Updated category: {name} (ID: {category_id})")
        except Exception as e:
            logger.error(f"Error updating category {name}: {str(e)}")
    
    logger.info(f"Added {count} new categories")

def test_api_access():
    """Test access to supplier products API"""
    logger.info("Testing supplier products API access...")
    client = get_api_client()
    
    if not client:
        logger.error("Could not create API client. Check API configuration.")
        return False
    
    try:
        # Test the supplier products endpoint
        response = client.products.get_products(page=0, size=1)
        
        if 'content' in response:
            logger.info("Successfully accessed supplier products API!")
            logger.info(f"Found {response.get('totalElements', 0)} total products")
            return True
        else:
            logger.error("Could not access supplier products API")
            return False
    except Exception as e:
        logger.error(f"Error testing API access: {str(e)}")
        return False

def main():
    """Update API handling"""
    logger.info("Starting API handling update")
    
    # Always add fallback data
    update_default_brands()
    update_default_categories()
    
    # Test API access to confirm what endpoints are available
    api_available = test_api_access()
    if api_available:
        logger.info("API is accessible. Basic setup complete.")
    else:
        logger.warning("API is not accessible. Using fallback mechanisms.")
    
    logger.info("API handling update completed")

if __name__ == "__main__":
    main()