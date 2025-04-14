"""
Renk düzeltme betiği - Direkt yaklaşım.

Bu betik, ürünlerin attributes alanını direkt düzenleyerek renk bilgisini ekler.

python manage.py shell < fix_color_direct.py
"""

import json
import logging
import os
import sys

# Set up Django environment
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from django.db.models import Q
from trendyol.models import TrendyolProduct

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_colors_directly():
    """Veritabanında doğrudan tüm ürünlere renk bilgisi ekler"""
    # Renk özniteliği ID'si (Trendyol API'de standart bir değer)
    COLOR_ATTRIBUTE_ID = 348
    
    # Trendyol'da bulunan yaygın renk ID'leri
    color_id_map = {
        'beyaz': 123986,
        'siyah': 123987,
        'mavi': 123988,
        'kırmızı': 123990,
        'pembe': 123991,
        'yeşil': 123992,
        'sarı': 123993,
        'mor': 123994,
        'gri': 123995,
        'kahverengi': 123996,
        'lacivert': 123999,
        'turuncu': 124002,
        'bej': 124003,
        'ekru': 123997,
        'krem': 124000
    }
    
    # Ürünleri al
    products = TrendyolProduct.objects.all()
    logger.info(f"Toplam {products.count()} ürün bulundu")
    
    processed = 0
    updated = 0
    already_has_color = 0
    errors = 0
    
    for product in products:
        try:
            processed += 1
            
            # Ürünün özniteliklerini al
            attributes = product.attributes
            
            # Öznitelikleri JSON'a çevir (eğer string ise)
            if isinstance(attributes, str):
                try:
                    attributes = json.loads(attributes)
                except json.JSONDecodeError:
                    attributes = []
                    
            # None ise boş liste yap
            if attributes is None:
                attributes = []
                
            # Liste değilse dönüştür
            if not isinstance(attributes, list):
                if isinstance(attributes, dict):
                    # Sözlüğü listeye dönüştür
                    attr_list = []
                    for k, v in attributes.items():
                        attr_list.append({
                            'attributeId': int(k) if k.isdigit() else k,
                            'attributeValueId': v
                        })
                    attributes = attr_list
                else:
                    attributes = []
            
            # Renk özniteliği var mı kontrol et
            has_color = False
            for attr in attributes:
                if attr.get('attributeId') == COLOR_ATTRIBUTE_ID:
                    has_color = True
                    already_has_color += 1
                    break
                    
            # Eğer renk özniteliği yoksa ekle
            if not has_color:
                # Üründen rengi belirle
                found_color = None
                product_title = product.title.lower() if product.title else ""
                
                for color_name, color_id in color_id_map.items():
                    if color_name in product_title:
                        found_color = color_id
                        break
                        
                # Renk bulunamadıysa varsayılan bir renk kullan
                if not found_color:
                    found_color = color_id_map['beyaz']  # Beyaz renk varsayılan
                    
                # Renk özniteliğini ekle
                attributes.append({
                    'attributeId': COLOR_ATTRIBUTE_ID,
                    'attributeValueId': found_color
                })
                
                # Ürünü güncelle
                product.attributes = attributes
                product.save()
                updated += 1
                
                logger.info(f"Ürün ID:{product.id} - Başlık: {product.title} için renk eklendi")
                
        except Exception as e:
            errors += 1
            logger.error(f"Ürün ID:{product.id} işlenirken hata: {str(e)}")
            
        # Her 10 ürünü işledikten sonra ilerleme bilgisi
        if processed % 10 == 0:
            logger.info(f"İşlenen: {processed}, Güncellenen: {updated}, Zaten renk sahibi: {already_has_color}, Hatalar: {errors}")
    
    # Final istatistikler
    logger.info(f"İşlem tamamlandı. Toplam {processed} ürün işlendi")
    logger.info(f"Güncellenen: {updated}, Zaten renk sahibi: {already_has_color}, Hatalar: {errors}")

if __name__ == "__main__":
    fix_colors_directly()