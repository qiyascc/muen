"""
Veritabanındaki default/yerel kategori ve öznitelikleri temizleyen script.

Bu script, tüm kategori ve öznitelik bilgilerini veritabanından temizler
böylece herşey API'den gerçek zamanlı olarak alınacaktır.

python manage.py shell < clean_default_data.py
"""

import os
import logging

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from django.db import transaction
from trendyol.models import TrendyolCategory

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_all_default_data():
    """Tüm default/önceden kaydedilmiş verileri temizle"""
    try:
        with transaction.atomic():
            # Kategorileri temizle
            category_count = TrendyolCategory.objects.count()
            TrendyolCategory.objects.all().delete()
            logger.info(f"{category_count} adet kategori veritabanından silindi")
            
            # Öznitelikleri temizle
            attribute_count = TrendyolAttribute.objects.count()
            TrendyolAttribute.objects.all().delete()
            logger.info(f"{attribute_count} adet öznitelik veritabanından silindi")
            
            # Öznitelik değerlerini temizle
            attribute_value_count = TrendyolAttributeValue.objects.count()
            TrendyolAttributeValue.objects.all().delete()
            logger.info(f"{attribute_value_count} adet öznitelik değeri veritabanından silindi")
            
            logger.info("Tüm veriler başarıyla temizlendi. Sistemde kategori ve öznitelik verisi kalmadı.")
            logger.info("Bu öğeler artık API'den gerçek zamanlı olarak çekilecektir.")
            
    except Exception as e:
        logger.error(f"Veri temizleme işlemi sırasında hata oluştu: {str(e)}")
        raise
        
if __name__ == "__main__":
    logger.info("Trendyol kategori ve öznitelik verilerini temizleme işlemi başlıyor...")
    clean_all_default_data()
    logger.info("İşlem tamamlandı.")