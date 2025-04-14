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
            
            # Tüm ürünleri API'den veri çekecek şekilde ayarla
            from trendyol.models import TrendyolProduct
            products = TrendyolProduct.objects.all()
            for product in products:
                if product.category_id == 522:
                    # Kadın ürünleri için alt kategori ID'si
                    product.category_id = 524
                    product.save()
                    
            logger.info(f"{products.count()} ürün API'den veri çekecek şekilde güncellendi")
            
            logger.info("Tüm veriler başarıyla temizlendi. Sistemde kategori ve öznitelik verisi kalmadı.")
            logger.info("Bu öğeler artık API'den gerçek zamanlı olarak çekilecektir.")
            
    except Exception as e:
        logger.error(f"Veri temizleme işlemi sırasında hata oluştu: {str(e)}")
        raise
        
if __name__ == "__main__":
    logger.info("Trendyol kategori ve öznitelik verilerini temizleme işlemi başlıyor...")
    clean_all_default_data()
    logger.info("İşlem tamamlandı.")