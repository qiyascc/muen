"""
Sabit öznitelik (attribute) değerleri ekleyen betik.

Bu betik, Trendyol API'sinden öznitelikleri alamadığımız durumlar için
bilinen/varsayılan renk ve diğer öznitelikleri ürünlere ekler.

python add_default_attributes.py
"""

import os
import sys
import json
import logging
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct
from loguru import logger

# Sabit öznitelik değerleri
# Özellikle Renk (348) özniteliği zorunlu

# Renk özniteliği ID'si
COLOR_ATTRIBUTE_ID = 348  

# Trendyol'da bulunan yaygın renk ID'leri ve isimleri
COLOR_MAP = {
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
}

# Cinsiyet özniteliği ID'si ve değerleri
GENDER_ATTRIBUTE_ID = 652
GENDER_MAP = {
    'kadın': 652,
    'erkek': 653,
    'unisex': 654,
    'kız çocuk': 655,
    'erkek çocuk': 656,
}

# Materyal özniteliği ID'si
MATERIAL_ATTRIBUTE_ID = 347
MATERIAL_VALUES = {
    'pamuk': 686234  # Pamuk/Cotton
}

# Beden özniteliği ID'si
SIZE_ATTRIBUTE_ID = 346
SIZE_MAP = {
    'S': 342771,
    'M': 342772,
    'L': 342773,
    'XL': 342774,
    'XXL': 342775
}

def determine_color_from_title(title):
    """Ürün başlığına göre renk ID'si belirler"""
    title = title.lower()
    
    for color_name, color_id in COLOR_MAP.items():
        if color_name in title:
            return color_id
            
    # Varsayılan olarak siyah
    return COLOR_MAP['siyah']

def determine_gender_from_title(title):
    """Ürün başlığına göre cinsiyet ID'si belirler"""
    title = title.lower()
    
    if 'kadın' in title:
        return GENDER_MAP['kadın']
    elif 'erkek çocuk' in title:
        return GENDER_MAP['erkek çocuk']
    elif 'kız çocuk' in title:
        return GENDER_MAP['kız çocuk']
    elif 'erkek' in title:
        return GENDER_MAP['erkek']
    elif 'unisex' in title:
        return GENDER_MAP['unisex']
        
    # Kadın ürünleri daha yaygın olduğu için varsayılan olarak kadın
    return GENDER_MAP['kadın']

def add_default_attributes():
    """Tüm ürünlere sabit öznitelikler ekle"""
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
            
            # String öznitelikleri temizle
            new_attributes = []
            for attr in attributes:
                if isinstance(attr, dict):
                    # Sayısal ID'lere çevir
                    attr_id = attr.get('attributeId')
                    if attr_id == 'color' or attr_id == 'renk':
                        attr_id = COLOR_ATTRIBUTE_ID
                    
                    if isinstance(attr_id, str) and attr_id.isdigit():
                        attr_id = int(attr_id)
                        
                    new_attributes.append({
                        'attributeId': attr_id,
                        'attributeValueId': attr.get('attributeValueId')
                    })
            
            # Temizlenmiş öznitelikleri kullan
            attributes = new_attributes
            
            # Şimdi gerekli öznitelikleri kontrol et ve ekle
            update_needed = False
            
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
                update_needed = True
                logger.info(f"Ürün ID:{product.id} - {product.title} için renk eklendi")
                
            # Cinsiyet özniteliği var mı kontrol et - Kadın Giyim kategorisi için gerekli
            if product.category_id in [524]:  # Kadın Üst Giyim
                has_gender = False
                for attr in attributes:
                    if attr.get('attributeId') == GENDER_ATTRIBUTE_ID:
                        has_gender = True
                        break
                        
                if not has_gender:
                    gender_id = determine_gender_from_title(product.title)
                    attributes.append({
                        'attributeId': GENDER_ATTRIBUTE_ID,
                        'attributeValueId': gender_id
                    })
                    update_needed = True
                    logger.info(f"Ürün ID:{product.id} - {product.title} için cinsiyet eklendi")
            
            # Materyal özniteliği var mı kontrol et - Bazı kategoriler için gerekli
            if product.category_id in [523, 524, 675]:  # Giyim kategorileri
                has_material = False
                for attr in attributes:
                    if attr.get('attributeId') == MATERIAL_ATTRIBUTE_ID:
                        has_material = True
                        break
                        
                if not has_material:
                    # Varsayılan pamuk
                    attributes.append({
                        'attributeId': MATERIAL_ATTRIBUTE_ID,
                        'attributeValueId': MATERIAL_VALUES['pamuk']
                    })
                    update_needed = True
                    logger.info(f"Ürün ID:{product.id} - {product.title} için materyal eklendi")
            
            # Ürünü güncelle
            if update_needed:
                product.attributes = attributes
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

def reset_failed_products():
    """Önceden başarısız olmuş ürünleri sıfırla"""
    from django.db.models import Q
    
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
    logger.info("Sabit öznitelik ekleme işlemi başlatılıyor...")
    add_default_attributes()
    logger.info("Başarısız ürünleri sıfırlama işlemi başlatılıyor...")
    reset_failed_products()
    logger.info("İşlem tamamlandı.")