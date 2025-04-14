"""
Basit kategori bulmak için yardımcı fonksiyonlar.
"""
import logging
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Varsayılan kategoriler
DEFAULT_CATEGORIES = {
    "kadın": 1,  # Kadın Giyim
    "erkek": 2,  # Erkek Giyim
    "çocuk": 3,  # Çocuk Giyim
    "ayakkabı": 383,  # Ayakkabı
    "çanta": 361,  # Çanta
    "saat": 220,  # Saat & Aksesuar
    "takı": 208,  # Takı & Mücevher
    "elektronik": 58,  # Elektronik
    "ev": 104,  # Ev & Yaşam
    "kitap": 26,  # Kitap & Kırtasiye
    "oyuncak": 28,  # Oyuncak
    "spor": 107,  # Spor & Outdoor
    "kozmetik": 113,  # Kozmetik & Kişisel Bakım
    "süpermarket": 41,  # Süpermarket
    "kıyafet": 1,  # Varsayılan olarak Kadın giyim
    "tişört": 385,  # Tişört
    "pantolon": 387,  # Pantolon
    "elbise": 53,  # Elbise
    "gömlek": 388,  # Gömlek
    "mont": 389,  # Mont, Kaban vb.
    "pijama": 726,  # Pijama
    "iç giyim": 717,  # İç Giyim
    "jean": 395,  # Jean
}

# Kadın kategorileri
WOMEN_CATEGORIES = {
    "tişört": 385,
    "pantolon": 387,
    "elbise": 53,
    "gömlek": 388,
    "mont": 389,
    "pijama": 726,
    "iç giyim": 717,
    "jean": 395,
}

# Erkek kategorileri
MEN_CATEGORIES = {
    "tişört": 397,
    "pantolon": 399,
    "gömlek": 400,
    "mont": 401,
    "pijama": 761,
    "iç giyim": 752,
    "jean": 407,
}

# Çocuk kategorileri
CHILDREN_CATEGORIES = {
    "tişört": 441,
    "pantolon": 443,
    "elbise": 446,
    "pijama": 939,
    "iç giyim": 920,
    "jean": 448,
}

# LCW kategorilerini Trendyol kategorilerine eşleştir
LCW_TO_TRENDYOL = {
    "kadın": 1,  # Kadın
    "erkek": 2,  # Erkek
    "kız çocuk": 60,  # Kız Çocuk
    "erkek çocuk": 286,  # Erkek Çocuk
    "bebek": 3,  # Bebek
    "ayakkabı": 383,  # Ayakkabı
}


def find_best_category(text: str) -> Optional[int]:
    """
    Verilen metne en uygun kategoriyi bul
    """
    if not text:
        return None
    
    text = text.lower()
    
    # Önce tam eşleşme kontrolü
    for key, category_id in LCW_TO_TRENDYOL.items():
        if key in text:
            logger.info(f'Kategori bulundu: "{key}" -> {category_id}')
            return category_id
    
    # Giyim türünü belirle
    gender_type = None
    if any(word in text for word in ["kadın", "bayan", "kız"]):
        gender_type = "kadın"
    elif any(word in text for word in ["erkek", "bay"]):
        gender_type = "erkek"
    elif any(word in text for word in ["çocuk", "kız çocuk", "erkek çocuk"]):
        gender_type = "çocuk"
    
    # Giyim türüne göre kategori seç
    if gender_type == "kadın":
        for key, category_id in WOMEN_CATEGORIES.items():
            if key in text:
                logger.info(f'Kadın kategorisi bulundu: "{key}" -> {category_id}')
                return category_id
        return 1  # Varsayılan olarak Kadın giyim
    
    elif gender_type == "erkek":
        for key, category_id in MEN_CATEGORIES.items():
            if key in text:
                logger.info(f'Erkek kategorisi bulundu: "{key}" -> {category_id}')
                return category_id
        return 2  # Varsayılan olarak Erkek giyim
    
    elif gender_type == "çocuk":
        for key, category_id in CHILDREN_CATEGORIES.items():
            if key in text:
                logger.info(f'Çocuk kategorisi bulundu: "{key}" -> {category_id}')
                return category_id
        return 3  # Varsayılan olarak Çocuk giyim
    
    # Giyim türü belirlenemezse, genel kategorilerde ara
    for key, category_id in DEFAULT_CATEGORIES.items():
        if key in text:
            logger.info(f'Genel kategori bulundu: "{key}" -> {category_id}')
            return category_id
    
    # Hiçbir eşleşme bulunamazsa varsayılan kategori olarak Kadın Giyim
    logger.warning(f'Kategori bulunamadı: "{text}", varsayılan kategori kullanılıyor (1: Kadın Giyim)')
    return 1