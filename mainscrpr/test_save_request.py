"""
Test Trendyol API request saving feature.

This script creates a sample product and sends it to Trendyol API.
The request payload will be saved to requests/trendyol/product_<stock_code>.json

Run this script with: python manage.py shell < test_save_request.py
"""

import os
import sys
import logging
import json
import pathlib
from datetime import datetime

# Setup Django environment
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from django.utils import timezone
from trendyol_app.models import TrendyolAPIConfig, TrendyolProduct
from trendyol_app.services import TrendyolProductManager, TrendyolAPI

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trendyol_test')

def test_save_product_request():
    """
    Test saving Trendyol API product requests to JSON file
    """
    logger.info("Testing product request saving...")
    
    # Create a dummy product
    test_product = TrendyolProduct(
        barcode="TEST123456789",
        title="Test Ürün - Kayıt Testi",
        product_main_id="TEST-PROD-12345",
        brand_name="Test Marka",
        category_name="Test Kategori",
        quantity=10,
        stock_code="TEST-STOCK-1234",
        price=100.0,
        sale_price=90.0,
        description="Bu bir test ürünüdür.",
        image_url="https://example.com/image.jpg",
        vat_rate=10,
        currency_type="TRY"
    )
    
    # Get API config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("No active API config found")
        return
    
    # Initialize API client and product manager
    api_client = TrendyolAPI(config)
    product_manager = TrendyolProductManager(api_client)
    
    # Create a sample product data
    product_data = {
        'items': [{
            'barcode': test_product.barcode,
            'title': test_product.title,
            'productMainId': test_product.product_main_id,
            'brandName': test_product.brand_name,
            'categoryName': test_product.category_name,
            'quantity': test_product.quantity,
            'stockCode': test_product.stock_code,
            'dimensionalWeight': 1,
            'description': test_product.description,
            'currencyType': test_product.currency_type,
            'listPrice': float(test_product.price),
            'salePrice': float(test_product.sale_price),
            'vatRate': test_product.vat_rate,
            'cargoCompanyId': 10,
            'images': [
                {
                    'url': test_product.image_url
                }
            ],
            'attributes': [],
            'categoryId': 1001
        }]
    }
    
    # Call the save method directly
    try:
        product_manager._save_product_request(product_data, test_product.stock_code)
        
        # Check if file was created
        file_path = pathlib.Path(f"requests/trendyol/product_{test_product.stock_code}.json")
        if file_path.exists():
            logger.info(f"Successfully saved request data to {file_path}")
            
            # Read the saved file
            with open(file_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                
            logger.info(f"Timestamp: {saved_data.get('timestamp')}")
            logger.info(f"Product title: {saved_data.get('data', {}).get('items', [{}])[0].get('title')}")
        else:
            logger.error(f"Failed to find saved file at {file_path}")
            
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
    
    logger.info("Test completed")
    
if __name__ == "__main__":
    test_save_product_request()
    
# Execute if run as script
test_save_product_request()