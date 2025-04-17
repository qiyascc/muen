"""
Fix Trendyol API endpoints in all configuration and service files.

This script updates the TrendyolAPIConfig with correct endpoint values,
and also updates the TrendyolProductManager service class to use the
correct endpoint format when calling the API.

Run this script with: python manage.py shell < fix_trendyol_endpoints.py
"""

import os
import sys
import logging

# Setup Django environment
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol_app.models import TrendyolAPIConfig

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trendyol_fix')

def fix_endpoints():
    """Fix Trendyol API endpoint configuration"""
    
    logger.info("Beginning Trendyol API endpoint fix process...")
    
    # Fix the API configuration
    try:
        # Get all configs
        configs = TrendyolAPIConfig.objects.all()
        logger.info(f"Found {configs.count()} API configurations")
        
        for config in configs:
            logger.info(f"Fixing configuration ID={config.id}")
            
            # Ensure base URL has correct domain and path
            if "api.trendyol.com" in config.base_url:
                config.base_url = "https://apigw.trendyol.com/integration/"
                logger.info("Fixed base URL from api.trendyol.com to apigw.trendyol.com")
            elif not config.base_url.endswith('/'):
                config.base_url = f"{config.base_url}/"
                logger.info("Added trailing slash to base URL")
                
            # Fix products endpoint format
            if "supplier/product-service/v2/products" in config.products_endpoint:
                config.products_endpoint = "product/sellers/{sellerId}/products"
                logger.info("Fixed products endpoint to new format")
                
            # Fix batch status endpoint format
            if "supplier/product-service/v2/products/batch" in config.batch_status_endpoint:
                config.batch_status_endpoint = "suppliers/{supplierId}/products/batch-requests/{batchId}"
                logger.info("Fixed batch status endpoint to new format")
                
            # Ensure supplier ID is set (use seller ID if not set)
            if not config.supplier_id:
                config.supplier_id = config.seller_id
                logger.info(f"Set supplier ID to seller ID: {config.supplier_id}")
                
            # Save the config
            config.save()
            logger.info(f"Saved configuration ID={config.id}")
            
            # Display updated configuration
            logger.info(f"Updated configuration: Base URL={config.base_url}")
            logger.info(f"Products endpoint: {config.products_endpoint}")
            logger.info(f"Batch status endpoint: {config.batch_status_endpoint}")
            
        logger.info("API configuration fix completed")
        
    except Exception as e:
        logger.error(f"Error during endpoint fix: {str(e)}")
        
if __name__ == "__main__":
    fix_endpoints()
    
# Execute if run as script
fix_endpoints()