"""
Veritabanındaki default/yerel kategori ve öznitelikleri temizleyen script.

Bu script, tüm kategori ve öznitelik bilgilerini veritabanından temizler
böylece herşey API'den gerçek zamanlı olarak alınacaktır.

python manage.py shell < clean_default_data.py
"""

import os
import sys
import logging

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Import models
from django.db import connection
from trendyol.models import TrendyolBrand, TrendyolCategory, TrendyolProduct

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def clean_all_default_data():
    """Tüm default/önceden kaydedilmiş verileri temizle"""
    try:
        # Kategorileri temizle
        categories_count = TrendyolCategory.objects.count()
        TrendyolCategory.objects.all().delete()
        logger.info(f"Deleted {categories_count} categories")
        
        # Markaları temizle
        brands_count = TrendyolBrand.objects.count()
        TrendyolBrand.objects.all().delete()
        logger.info(f"Deleted {brands_count} brands")
        
        # Ürünleri temizleme - sadece öznitelikleri temizle
        products_count = TrendyolProduct.objects.count()
        TrendyolProduct.objects.update(attributes=[])
        logger.info(f"Reset attributes for {products_count} products")
        
        logger.info("Successfully cleaned all default/cached data")
        
        # Veritabanı boyutunu kontrol et
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            db_size = cursor.fetchone()[0]
            logger.info(f"Current database size: {db_size}")
        
        return True
    except Exception as e:
        logger.error(f"Error cleaning default data: {str(e)}")
        return False

if __name__ == "__main__":
    # Bu script direkt çalıştırıldığında veya Django shell'den import edildiğinde çalışır
    logger.info("Starting data cleanup...")
    clean_all_default_data()
    logger.info("Data cleanup complete")