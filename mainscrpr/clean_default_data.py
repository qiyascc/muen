"""
Veritabanındaki default/yerel kategori ve öznitelikleri temizleyen script.

Bu script, tüm kategori ve öznitelik bilgilerini veritabanından temizler
böylece herşey API'den gerçek zamanlı olarak alınacaktır.

python manage.py shell < clean_default_data.py
"""

import logging
import time
import django
import os
import sys
from django.db import connection
from trendyol.models import TrendyolCategory, TrendyolBrand

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('clean_default_data')

def clean_all_default_data():
    """Tüm default/önceden kaydedilmiş verileri temizle"""
    
    # Trendyol kategorilerini temizle
    try:
        count = TrendyolCategory.objects.all().delete()[0]
        logger.info(f"Deleted {count} category records")
    except Exception as e:
        logger.error(f"Error deleting categories: {str(e)}")
    
    # Trendyol markalarını temizle
    try:
        count = TrendyolBrand.objects.all().delete()[0]
        logger.info(f"Deleted {count} brand records")
    except Exception as e:
        logger.error(f"Error deleting brands: {str(e)}")
    
    # Diğer referans tablolarını temizle
    tables_to_clean = [
        # List other reference tables if needed
    ]
    
    for table in tables_to_clean:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table}")
                logger.info(f"Cleaned table {table}")
        except Exception as e:
            logger.error(f"Error cleaning table {table}: {str(e)}")
    
    logger.info("All default data has been cleaned from the database")
    logger.info("The system will now fetch fresh data from the API when needed")

if __name__ == "__main__":
    # When running with python manage.py shell < script.py
    # the __name__ == "__main__" condition is not checked
    # So we call the function directly
    print("Starting default data cleanup...")
    clean_all_default_data()
    print("Default data cleanup completed.")