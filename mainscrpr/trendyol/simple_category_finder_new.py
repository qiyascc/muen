"""
Basit Trendyol kategori bulma modülü.

Bu modül, LCWaikiki kategorilerini Trendyol kategorileriyle eşleştirmek için
basit bir yöntem kullanır. Yapay zeka veya kompleks eşleştirme kullanmaz.
"""

import logging
from typing import Optional
from dataclasses import dataclass

from .models import TrendyolCategory
from . import api_client

logger = logging.getLogger(__name__)

# Kategori eşleştirme tablosu
# LC Waikiki kategori adı -> Trendyol kategori ID'si
CATEGORY_MAPPING = {
    "Erkek": 1033,  # Erkek Giyim
    "Kadın": 1032,  # Kadın Giyim
    "Erkek Çocuk": 1034,  # Erkek Çocuk Giyim
    "Kız Çocuk": 1035,  # Kız Çocuk Giyim
    "Bebek": 1036,  # Bebek Giyim
    "Ayakkabı": 1112,  # Ayakkabı
    "Aksesuar": 1037,  # Aksesuar
    "Spor Giyim": 1033,  # Spor Giyim (Erkek kategorisine)
    "Plaj Giyim": 1032,  # Plaj Giyim (Kadın kategorisine)
    # Daha fazla kategori eşleştirmesi eklenebilir
}

# Varsayılan kategori ID'si
DEFAULT_CATEGORY_ID = 1033  # Erkek Giyim

@dataclass
class CategoryResult:
    """Kategori sonuç sınıfı"""
    category_id: int
    category_name: str


def find_best_category_match(category_name: str) -> Optional[CategoryResult]:
    """
    LCWaikiki kategori adını Trendyol kategori ID'sine eşleştirir.
    
    Args:
        category_name: LCWaikiki kategori adı
        
    Returns:
        CategoryResult objesi veya eşleşme bulunamazsa None
    """
    if not category_name:
        return None
    
    # Kategoride tam eşleşme ara
    if category_name in CATEGORY_MAPPING:
        category_id = CATEGORY_MAPPING[category_name]
        return CategoryResult(category_id=category_id, category_name=category_name)
    
    # Alt dize eşleşmesi dene
    for lcw_category, trendyol_id in CATEGORY_MAPPING.items():
        if lcw_category.lower() in category_name.lower():
            return CategoryResult(category_id=trendyol_id, category_name=lcw_category)
    
    # Veritabanından kontrolü dene
    try:
        db_category = TrendyolCategory.objects.filter(name__icontains=category_name).first()
        if db_category:
            return CategoryResult(
                category_id=db_category.category_id,
                category_name=db_category.name
            )
    except Exception as e:
        logger.error(f"Veritabanı kategori araması sırasında hata: {str(e)}")
    
    # Hiçbir eşleşme bulunamazsa varsayılan kategoriyi kullan
    logger.warning(f"'{category_name}' için kategori eşleşmesi bulunamadı. Varsayılan kategori kullanılıyor.")
    return CategoryResult(category_id=DEFAULT_CATEGORY_ID, category_name="Erkek Giyim")


def load_categories_from_api():
    """
    Trendyol API'sinden tüm kategorileri yükler ve veritabanına kaydeder.
    """
    try:
        client = api_client.get_api_client()
        if not client:
            logger.error("API client oluşturulamadı")
            return
        
        response = client.categories.get_categories()
        if not response or 'error' in response:
            logger.error(f"Kategori yükleme hatası: {response.get('message', 'Bilinmeyen hata')}")
            return
        
        categories = response.get('categories', [])
        
        # Kategorileri düz bir listede topla
        flat_categories = []
        _flatten_categories(categories, flat_categories)
        
        # Veritabanına kaydet
        saved_count = 0
        for cat in flat_categories:
            try:
                TrendyolCategory.objects.update_or_create(
                    category_id=cat['id'],
                    defaults={
                        'name': cat['name'],
                        'parent_id': cat.get('parentId')
                    }
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Kategori kaydedilirken hata: {cat['name']} - {str(e)}")
        
        logger.info(f"{saved_count}/{len(flat_categories)} kategori başarıyla kaydedildi.")
        
    except Exception as e:
        logger.error(f"Kategori yükleme işlemi sırasında hata: {str(e)}")


def _flatten_categories(categories, result):
    """
    Kategori ağacını düz bir listeye dönüştürür
    """
    for cat in categories:
        result.append({
            'id': cat['id'],
            'name': cat['name'],
            'parentId': cat.get('parentId')
        })
        
        if 'subCategories' in cat and cat['subCategories']:
            _flatten_categories(cat['subCategories'], result)


def get_attributes_for_category(category_id):
    """
    Belirli bir kategori için öznitelik listesi döndürür
    """
    client = api_client.get_api_client()
    if not client:
        logger.error("API client oluşturulamadı")
        return None
    
    response = client.categories.get_category_attributes(category_id)
    if 'error' in response:
        logger.error(f"Öznitelik yükleme hatası: {response.get('message', 'Bilinmeyen hata')}")
        return None
    
    return response