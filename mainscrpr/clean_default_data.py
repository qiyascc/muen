"""
Veritabanındaki default/yerel kategori ve öznitelikleri temizleyen script.

Bu script, tüm kategori ve öznitelik bilgilerini veritabanından temizler
böylece herşey API'den gerçek zamanlı olarak alınacaktır.

python manage.py shell < clean_default_data.py
"""

import os
import sys
import logging

# Django ayarlarını yükle
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from django.db import connection

# Trendyol modellerini import et
from trendyol.models import TrendyolCategory, TrendyolCategoryAttribute

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def clean_trendyol_categories():
    """Tüm Trendyol kategorilerini veritabanından temizle"""
    try:
        count = TrendyolCategory.objects.all().count()
        TrendyolCategory.objects.all().delete()
        logger.info(f"Tüm Trendyol kategorileri silindi ({count} kategoriler)")
    except Exception as e:
        logger.error(f"Kategori temizleme işlemi sırasında hata: {str(e)}")

def clean_trendyol_attributes():
    """Tüm Trendyol kategori özniteliklerini veritabanından temizle"""
    try:
        count = TrendyolCategoryAttribute.objects.all().count()
        TrendyolCategoryAttribute.objects.all().delete()
        logger.info(f"Tüm Trendyol kategori öznitelikleri silindi ({count} öznitelikler)")
    except Exception as e:
        logger.error(f"Öznitelik temizleme işlemi sırasında hata: {str(e)}")

def check_existing_data():
    """Veritabanında kalan önbellek verilerini kontrol et"""
    category_count = TrendyolCategory.objects.all().count()
    attribute_count = TrendyolCategoryAttribute.objects.all().count()
    
    logger.info(f"Mevcut veri durumu:")
    logger.info(f"- Trendyol kategorileri: {category_count}")
    logger.info(f"- Trendyol kategori öznitelikleri: {attribute_count}")
    
    return category_count == 0 and attribute_count == 0

def clean_all_default_data():
    """Tüm default/önceden kaydedilmiş verileri temizle"""
    logger.info("Tüm önbellek verilerini temizleme işlemi başlatılıyor...")
    
    # İlk olarak mevcut veri durumunu kontrol et
    logger.info("Mevcut veri durumu kontrol ediliyor...")
    check_existing_data()
    
    # Kategori ve öznitelikleri temizle
    clean_trendyol_categories()
    clean_trendyol_attributes()
    
    # Temizleme sonrası veri durumunu kontrol et
    success = check_existing_data()
    
    if success:
        logger.info("Tüm önbellek verileri başarıyla temizlendi!")
        logger.info("Artık tüm kategori ve öznitelik verileri API'den gerçek zamanlı olarak alınacak.")
    else:
        logger.warning("Bazı veriler temizlenemedi. Lütfen veritabanını manuel olarak kontrol edin.")

if __name__ == "__main__":
    clean_all_default_data()