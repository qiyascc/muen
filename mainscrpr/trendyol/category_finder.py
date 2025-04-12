"""
Trendyol Kategori Bulucu

Bu modül, Trendyol kategorilerini bulmak ve yönetmek için sınıflar içerir.
"""

import logging
import re
from functools import lru_cache
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# Trendyol'da yaygın olarak kullanılan zorunlu özellikler
DEFAULT_REQUIRED_ATTRIBUTES = {
    "Gender": {
        "id": 338,
        "values": {
            "Kadın": 7189,
            "Erkek": 7090,
            "Unisex": 7202,
            "Kız Çocuk": 7518,
            "Erkek Çocuk": 7519
        }
    },
    "Origin": {
        "id": 47,
        "values": {
            "Türkiye": 8201,
            "Çin": 8199,
            "İtalya": 5339
        }
    },
    "Color": {
        "id": 348,
        "values": {
            "Beyaz": 1012, 
            "Siyah": 1001,
            "Mavi": 1003,
            "Kırmızı": 1006,
            "Pembe": 1007,
            "Yeşil": 1009,
            "Sarı": 1010,
            "Lacivert": 1013,
            "Gri": 1065,
            "Kahverengi": 1004,
            "Turuncu": 1011,
            "Mor": 1008,
            "Ekru": 1011,
            "Bej": 1002
        }
    },
    "Size": {
        "id": 347,
        "values": {
            "XS": 630,
            "S": 631,
            "M": 632,
            "L": 633,
            "XL": 634,
            "XXL": 635,
            "3XL": 2300,
            "4XL": 2302,
            "5XL": 2310,
            "36": 647,
            "38": 648,
            "40": 649,
            "42": 650,
            "44": 651,
            "46": 652
        }
    },
    "Age Group": {
        "id": 60,
        "values": {
            "Bebek": 904,
            "Çocuk": 903,
            "Yetişkin": 902
        }
    }
}

class TrendyolCategoryFinder:
    """
    Trendyol kategori bulma işlemlerini yöneten sınıf.
    
    Bu sınıf, ürün başlıklarından Trendyol kategori ID'lerini bulmak için kullanılır.
    Basitleştirilmiş versiyon sadece temel metin eşleştirme kullanır - tam sürüm sentence-transformers gibi
    gelişmiş kütüphanelere ihtiyaç duyar.
    """
    
    def __init__(self, api_client):
        """
        TrendyolCategoryFinder sınıfını başlatır.
        
        Args:
            api_client: Trendyol API client nesnesi
        """
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
        
    @property
    def category_cache(self):
        """Tüm kategorileri döndürür, gerekirse API'den çeker"""
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self):
        """Trendyol API'sinden tüm kategorileri çeker"""
        try:
            data = self.api.make_request("GET", "product-categories")
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            return []
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id):
        """
        Belirli bir kategori için öznitelikleri alır (önbelleğe alınmış).
        
        Args:
            category_id: Trendyol kategori ID'si
            
        Returns:
            Kategori öznitelikleri listesi
        """
        if category_id in self._attribute_cache:
            return self._attribute_cache[category_id]
            
        try:
            endpoint = f"product-categories/{category_id}/attributes"
            data = self.api.make_request("GET", endpoint)
            self._attribute_cache[category_id] = data
            return data
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            return []
    
    def normalize_text(self, text):
        """
        Metni normalleştirir: küçük harfe çevirir, gereksiz boşlukları kaldırır.
        
        Args:
            text: Normalleştirilecek metin
            
        Returns:
            Normalleştirilmiş metin
        """
        if not text:
            return ""
        # Küçük harfe çevir
        text = text.lower()
        # Gereksiz boşlukları temizle
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def find_best_category(self, product_title, default_category_id=1001):
        """
        Ürün başlığına göre en uygun Trendyol kategorisini bulur.
        
        Args:
            product_title: Ürün başlığı
            default_category_id: Kategori bulunamazsa kullanılacak varsayılan kategori ID'si
            
        Returns:
            Trendyol kategori ID'si (int)
        """
        if not product_title:
            return default_category_id
            
        try:
            categories = self.category_cache
            if not categories:
                logger.warning("No categories available, using default category")
                return default_category_id
                
            # Temel kelime eşleştirme yapılır
            product_title = self.normalize_text(product_title)
            
            # İlk direkt eşleşmeleri arayalım
            direct_matches = self._find_all_direct_matches(product_title, categories)
            if direct_matches:
                # Eşleşmeler arasında en doğrudan olanını seçelim
                best_match = max(direct_matches, key=lambda x: self._calculate_match_score(product_title, x))
                logger.info(f"Direct category match: '{best_match['name']}' (ID: {best_match['id']}) for '{product_title}'")
                return best_match['id']
            
            # Her şey başarısız olursa, varsayılan kategoriye dönülür
            logger.warning(f"No category match found for '{product_title}', using default category {default_category_id}")
            return default_category_id
            
        except Exception as e:
            logger.error(f"Error finding category for '{product_title}': {str(e)}")
            return default_category_id
    
    def _find_all_direct_matches(self, product_title, categories, path=None):
        """
        Tüm kategoriler içinde direkt eşleşmeleri arar.
        
        Args:
            product_title: Normalleştirilmiş ürün başlığı
            categories: Aranacak kategoriler listesi
            path: Şu anki kategori yolu (iç kullanım için)
            
        Returns:
            Eşleşen kategoriler listesi
        """
        if path is None:
            path = []
            
        matches = []
        
        for category in categories:
            current_path = path + [category['name']]
            category_name = self.normalize_text(category['name'])
            
            # Tam veya kısmi eşleşme kontrolü
            if category_name in product_title or product_title in category_name:
                # Yaprak kategorileri tercih et (alt kategorisi olmayanlar)
                if not category.get('subCategories'):
                    matches.append(category)
            
            # Alt kategorilerde de ara
            if category.get('subCategories'):
                sub_matches = self._find_all_direct_matches(
                    product_title, category['subCategories'], current_path
                )
                matches.extend(sub_matches)
        
        return matches
    
    def _calculate_match_score(self, product_title, category):
        """
        Ürün başlığı ve kategori arasındaki eşleşme skorunu hesaplar.
        
        Args:
            product_title: Ürün başlığı
            category: Kategori bilgisi
            
        Returns:
            Eşleşme skoru (daha yüksek = daha iyi eşleşme)
        """
        category_name = self.normalize_text(category['name'])
        
        # Tam eşleşme en yüksek puanı alır
        if category_name == product_title:
            return 1000
            
        # Kategori, ürün başlığında geçiyorsa iyi bir eşleşmedir
        if category_name in product_title:
            # Daha uzun kategori adları daha spesifiktir, daha yüksek puan alır
            return 500 + len(category_name)
            
        # Ürün başlığı, kategori adında geçiyorsa orta düzeyde bir eşleşmedir
        if product_title in category_name:
            return 200 + len(product_title)
            
        # Kısmi kelime eşleşmeleri
        product_words = set(product_title.split())
        category_words = set(category_name.split())
        common_words = product_words.intersection(category_words)
        
        return len(common_words) * 100


def get_required_attributes_for_category(category_id, api_client=None, default_attrs=None):
    """
    Kategori için zorunlu öznitelikleri alır.
    
    Args:
        category_id: Trendyol kategori ID'si
        api_client: Trendyol API client nesnesi (opsiyonel)
        default_attrs: Varsayılan öznitelikler listesi (opsiyonel)
        
    Returns:
        Zorunlu öznitelikler listesi
    """
    print(f"[DEBUG-ATTR] Zorunlu özellikler alınıyor: Kategori ID={category_id}")
    
    if default_attrs is None:
        default_attrs = []
        
    try:
        if api_client:
            finder = TrendyolCategoryFinder(api_client)
            attributes_data = finder.get_category_attributes(category_id)
            
            required_attrs = []
            for attr in attributes_data:
                if attr.get('required', False) and 'id' in attr and 'allowedValues' in attr and attr['allowedValues']:
                    # İlk izin verilen değeri kullan
                    first_value = attr['allowedValues'][0]
                    if 'id' in first_value:
                        required_attrs.append({
                            'attributeId': attr['id'],
                            'attributeValueId': first_value['id']
                        })
            
            print(f"[DEBUG-ATTR] Temel kategori özellikleri alındı: {required_attrs}")
            if required_attrs:
                print(f"[DEBUG-ATTR] Bulunan zorunlu özellikler: {required_attrs}")
                return required_attrs
            
    except Exception as e:
        logger.error(f"Error getting required attributes for category {category_id}: {str(e)}")
    
    # API'den alınamazsa, varsayılan öznitelikleri kullan
    return default_attrs