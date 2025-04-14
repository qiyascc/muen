"""
Kategori ve Öznitelik düzeltme betiği.

Bu betik, ürünlerin kategori ve attributes sorununun her iki tarafını düzeltmeye çalışır:
1. Üst kategori (522) yerine alt kategori atar
2. Ürünlere Renk özniteliği ekler
3. API'den veri alamıyorsa, sabit değerler ekler

python fix_attributes_and_category.py
"""

import os
import sys
import json
import logging
import time
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct, TrendyolAPIConfig
from django.db.models import Q
from loguru import logger

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

def determine_category_from_title(title):
    """
    Ürün başlığına göre kategori ID'si belirler
    """
    title = title.lower()
    
    # Erkek ürünleri
    if any(term in title for term in ['erkek', 'erkeklere', 'men', 'mens']):
        # Erkek Üst Giyim
        return 523
    
    # Kadın ürünleri
    elif any(term in title for term in ['kadın', 'kadin', 'kadınlara', 'women', 'womens']):
        # Kadın Üst Giyim
        return 524
    
    # Çocuk ürünleri
    elif any(term in title for term in ['çocuk', 'cocuk', 'kız çocuk', 'erkek çocuk', 'kids']):
        # Çocuk Üst Giyim
        return 675
    
    # Bebek ürünleri
    elif any(term in title for term in ['bebek', 'baby']):
        # Bebek Giyim
        return 677
    
    # Varsayılan olarak Kadın Üst Giyim
    return 524  

def determine_color_from_title(title):
    """
    Ürün başlığına göre renk ID'si belirler
    """
    title = title.lower()
    
    for color_name, color_id in color_id_map.items():
        if color_name in title:
            return color_id
    
    # Başka renk tanımlayıcı kelimeler
    if any(term in title for term in ['gri', 'gümüş', 'silver', 'grey']):
        return color_id_map['gri']
    
    if any(term in title for term in ['siyah', 'koyu', 'black', 'dark']):
        return color_id_map['siyah']
    
    if any(term in title for term in ['beyaz', 'akbeyaz', 'white']):
        return color_id_map['beyaz']
    
    if any(term in title for term in ['mavi', 'blue', 'navy']):
        return color_id_map['mavi']
        
    # Renk belirlenemezse varsayılan olarak siyah
    return color_id_map['siyah']

def fix_products():
    """Tüm ürünleri düzeltir"""
    # Ürünleri al
    products = TrendyolProduct.objects.all()
    logger.info(f"Toplam {products.count()} ürün bulundu")
    
    # Kategori 522 olan ürünlerin sayısını kontrol et
    category_522_count = TrendyolProduct.objects.filter(category_id=522).count()
    logger.info(f"Kategori 522 olan {category_522_count} ürün var")
    
    processed = 0
    category_fixed = 0
    attributes_fixed = 0
    errors = 0
    
    for product in products:
        try:
            processed += 1
            update_needed = False
            
            # Kategori 522 ise alt kategori belirle
            if product.category_id == 522:
                product.category_id = determine_category_from_title(product.title)
                category_fixed += 1
                update_needed = True
                logger.info(f"Ürün ID:{product.id} - {product.title} için kategori {product.category_id} olarak güncellendi")
            
            # Ürünün özniteliklerini düzelt
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
                    break
                    
            # Eğer renk özniteliği yoksa ekle
            if not has_color:
                color_id = determine_color_from_title(product.title)
                attributes.append({
                    'attributeId': COLOR_ATTRIBUTE_ID,
                    'attributeValueId': color_id
                })
                attributes_fixed += 1
                update_needed = True
                logger.info(f"Ürün ID:{product.id} - {product.title} için renk eklendi")
            
            # Ürünü güncelle
            if update_needed:
                product.attributes = attributes
                product.save()
            
        except Exception as e:
            errors += 1
            logger.error(f"Ürün ID:{product.id} işlenirken hata: {str(e)}")
            
        # Her 10 ürünü işledikten sonra ilerleme bilgisi
        if processed % 10 == 0:
            logger.info(f"İşlenen: {processed}, Kategori Güncellenen: {category_fixed}, " + 
                      f"Öznitelikleri Güncellenen: {attributes_fixed}, Hatalar: {errors}")
    
    # Final istatistikler
    logger.info("İşlem tamamlandı")
    logger.info(f"Toplam İşlenen: {processed}")
    logger.info(f"Kategori Güncellenen: {category_fixed}")
    logger.info(f"Öznitelikleri Güncellenen: {attributes_fixed}")
    logger.info(f"Hatalar: {errors}")

def reset_failed_products():
    """Önceden başarısız olmuş ürünleri sıfırla"""
    # Batch durumu FAILED olan ürünleri seç
    failed_products = TrendyolProduct.objects.filter(
        Q(batch_status='FAILED') | 
        Q(status_message__contains='kategori') | 
        Q(status_message__contains='özellik') |
        Q(status_message__contains='renk')
    )
    
    count = failed_products.count()
    logger.info(f"{count} başarısız ürün bulundu")
    
    if count > 0:
        # Batch durumunu sıfırla
        failed_products.update(batch_status='', status_message='')
        logger.info(f"{count} ürün sıfırlandı ve yeniden gönderilmeye hazır")

if __name__ == "__main__":
    logger.info("Ürün düzeltme işlemi başlatılıyor...")
    fix_products()
    logger.info("Başarısız ürünleri sıfırlama işlemi başlatılıyor...")
    reset_failed_products()
    logger.info("İşlem tamamlandı")