"""
Renk öznitelikleri düzeltme betiği.

Bu betik, string olarak kaydedilen renk özniteliklerini 
sayısal ID'lere dönüştürür ve tüm ürünlere standart formatta uygular.

python fix_color_values.py
"""

import os
import sys
import json
import logging
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct
from loguru import logger

# Renk özniteliği ID'si (Trendyol API'de standart bir değer)
COLOR_ATTRIBUTE_ID = 348

# Trendyol'da bulunan yaygın renk ID'leri ve isimleri
color_map = {
    # Türkçe renk adı: ID
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
    'krem': 124000,
    
    # İngilizce karşılıklar da ekleyelim
    'white': 123986,
    'black': 123987,
    'blue': 123988, 
    'navy': 123999,
    'red': 123990,
    'pink': 123991,
    'green': 123992,
    'yellow': 123993,
    'purple': 123994,
    'gray': 123995,
    'grey': 123995,
    'brown': 123996,
    'orange': 124002,
    'beige': 124003,
    'cream': 124000
}

def fix_color_values():
    """String formatında kaydedilen renk özniteliklerini sayısal ID'lere dönüştür"""
    products = TrendyolProduct.objects.all()
    logger.info(f"Toplam {products.count()} ürün bulundu")
    
    processed = 0
    updated = 0
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
                    attr_list = []
                    for k, v in attributes.items():
                        attr_list.append({
                            'attributeId': int(k) if k.isdigit() else k,
                            'attributeValueId': v
                        })
                    attributes = attr_list
                else:
                    attributes = []
            
            # Değişiklik olup olmadığını takip et
            update_needed = False
            
            # String/metin türünde renk özniteliklerini ara ve güncelle
            new_attributes = []
            for attr in attributes:
                # Bu bir renk özniteliği mi kontrol et
                if attr.get('attributeId') == 'color' or attr.get('attributeId') == COLOR_ATTRIBUTE_ID:
                    # Değer string mi kontrol et
                    value = attr.get('attributeValueId')
                    if isinstance(value, str):
                        value_lower = value.lower()
                        # Color map'te bu renk var mı?
                        if value_lower in color_map:
                            # Sayısal ID ile güncelle
                            numeric_id = color_map[value_lower]
                            # Yeni bilgileri ekle
                            new_attributes.append({
                                'attributeId': COLOR_ATTRIBUTE_ID,
                                'attributeValueId': numeric_id
                            })
                            logger.info(f"Ürün ID:{product.id} - Renk '{value}' -> ID:{numeric_id} olarak güncellendi")
                            update_needed = True
                        else:
                            # Eşleşme bulunamadı, varsayılan siyah kullan
                            new_attributes.append({
                                'attributeId': COLOR_ATTRIBUTE_ID,
                                'attributeValueId': color_map['siyah']
                            })
                            logger.warning(f"Ürün ID:{product.id} - Renk '{value}' için eşleşme bulunamadı, varsayılan siyah kullanıldı")
                            update_needed = True
                    else:
                        # Zaten sayısal ID formatındaysa olduğu gibi bırak
                        new_attributes.append({
                            'attributeId': COLOR_ATTRIBUTE_ID,
                            'attributeValueId': value
                        })
                else:
                    # Renk özniteliği değilse, olduğu gibi ekle
                    new_attributes.append(attr)
            
            # Renk özniteliği yoksa ekleyelim
            has_color = any(attr.get('attributeId') == COLOR_ATTRIBUTE_ID for attr in new_attributes)
            if not has_color:
                # Ürün başlığından veya açıklamasından renk tahmini yap
                product_title = product.title.lower() if product.title else ""
                
                color_found = None
                for color_name, color_id in color_map.items():
                    if color_name in product_title:
                        color_found = color_id
                        break
                
                if not color_found:
                    # Renk bulunamadıysa varsayılan siyah kullan
                    color_found = color_map['siyah']
                
                new_attributes.append({
                    'attributeId': COLOR_ATTRIBUTE_ID,
                    'attributeValueId': color_found
                })
                
                logger.info(f"Ürün ID:{product.id} - Renk özniteliği eklendi: {color_found}")
                update_needed = True
            
            # Ürünü güncelle
            if update_needed:
                product.attributes = new_attributes
                product.save()
                updated += 1
                
        except Exception as e:
            errors += 1
            logger.error(f"Ürün ID:{product.id} işlenirken hata: {str(e)}")
            
        # Her 10 ürünü işledikten sonra ilerleme bilgisi
        if processed % 10 == 0:
            logger.info(f"İşlenen: {processed}, Güncellenen: {updated}, Hatalar: {errors}")
    
    # Final istatistikler
    logger.info(f"İşlem tamamlandı. Toplam {processed} ürün işlendi")
    logger.info(f"Güncellenen: {updated}, Hatalar: {errors}")

if __name__ == "__main__":
    logger.info("Renk değerleri düzeltme işlemi başlatılıyor...")
    fix_color_values()
    logger.info("İşlem tamamlandı")