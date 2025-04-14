"""
Renk düzeltme betiği - Direkt yaklaşım.

Bu betik, ürünlerin attributes alanını direkt düzenleyerek renk bilgisini ekler.

python manage.py shell < fix_color_direct.py
"""

import logging
import time
import json
import re
import django
import os
import sys
from django.db import connection
from django.db.models import Q
from trendyol.models import TrendyolProduct, TrendyolCategory, TrendyolAPIConfig
from trendyol.improved_api_client import get_api_client, TrendyolCategoryFinder

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('fix_color_direct')

def fix_colors_directly():
    """Veritabanında doğrudan tüm ürünlere renk bilgisi ekler"""
    
    # API client'ı başlat
    client = get_api_client()
    if not client:
        logger.error("API client not available")
        return False
    
    # Category finder'ı başlat
    category_finder = TrendyolCategoryFinder(client)
    
    # Henüz gönderilmemiş veya hata almış ürünleri bul
    products = TrendyolProduct.objects.filter(
        Q(batch_status='pending') | 
        Q(batch_status='failed') |
        Q(attributes=[]) |
        Q(attributes__isnull=True)
    )
    
    logger.info(f"Found {products.count()} products to fix")
    
    fixed_count = 0
    error_count = 0
    
    for product in products:
        try:
            logger.info(f"Processing product {product.id}: {product.title}")
            
            # Ürünün kategori ID'sini kontrol et
            if not product.category_id:
                logger.warning(f"Product {product.id} has no category_id, skipping")
                continue
            
            # Kategori özniteliklerini al
            attributes = category_finder.get_required_attributes(product.category_id)
            
            if not attributes:
                logger.warning(f"No attributes found for category {product.category_id}")
                continue
            
            # Ürün renk özniteliklerini API'den alınan güncel değerlerle güncelle
            product.attributes = attributes
            product.save()
            
            logger.info(f"Updated product {product.id} with {len(attributes)} attributes")
            fixed_count += 1
            
        except Exception as e:
            logger.error(f"Error updating product {product.id}: {str(e)}")
            error_count += 1
    
    logger.info(f"Fixed {fixed_count} products, encountered {error_count} errors")
    return True

if __name__ == "__main__":
    # When running with python manage.py shell < script.py
    # the __name__ == "__main__" condition is not checked
    # So we call the function directly
    print("Starting color fix process...")
    fix_colors_directly()
    print("Color fix completed.")