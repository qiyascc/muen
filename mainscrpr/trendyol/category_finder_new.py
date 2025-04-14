"""
Trendyol Kategori Bulucu

Bu modül, Trendyol API'sinden gelen kategorileri eşleştirmek için kullanılan
TrendyolCategoryFinder sınıfını sağlar.

Özellikler:
1. Kategori özniteliklerinin doğru şekilde alınması ve yönetilmesi
2. Basit string eşleştirmesi ile kategori bulma
3. API'den gelen kategorileri önbelleğe alma

Bu dosya, mevcut API istemcisiyle çalışacak şekilde tasarlanmıştır.
"""

import logging
import json
import re
from functools import lru_cache
from typing import Dict, List, Any, Optional
import difflib  # For basic string matching

logger = logging.getLogger(__name__)


class TrendyolCategoryFinder:
    """
    Basit kategori bulucu sınıfı.
    
    Bu sınıf, ürün adı veya kategorisine göre en uygun Trendyol kategori ID'sini bulmak için
    basit string eşleştirmesi kullanır.
    """
    
    def __init__(self, api_client):
        """
        TrendyolCategoryFinder sınıfını başlat.
        
        Args:
            api_client: Trendyol API istemcisi (TrendyolApi sınıfı)
        """
        self.api = api_client
        self._category_cache = None
    
    @property
    def category_cache(self):
        """Kategorileri önbelleğe al ve döndür"""
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self):
        """Tüm kategorileri Trendyol API'den getir"""
        try:
            # Use the categories API from the client
            data = self.api.categories.get_categories()
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise Exception("Category loading failed. Check API credentials.")
    
    def get_category_attributes(self, category_id):
        """Belirli bir kategori için öznitelikleri API'den getir"""
        try:
            # API istemcisinin categories.get_category_attributes metodunu kullan
            return self.api.categories.get_category_attributes(category_id)
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            return {"categoryAttributes": []}
    
    def find_best_category(self, search_term):
        """Verilen arama terimi için en uygun kategoriyi bul"""
        try:
            categories = self.category_cache
            if not categories:
                raise ValueError("Empty category list from API")
            
            # Sadece basit string eşleştirmesi kullan
            matches = self._find_all_matches(search_term, categories)
            if not matches:
                raise ValueError(f"No matches found for: {search_term}")
            return self._select_best_match(search_term, matches)['id']
            
        except Exception as e:
            logger.error(f"Category search failed: {str(e)}")
            # If we can't find a suitable category, return a safe default
            logger.warning("Returning default category ID as fallback")
            return 385  # Default to Women's Clothing - Jacket as a safe fallback
    
    def _collect_leaf_categories(self, categories, result):
        """Alt kategorisi olmayan tüm kategorileri topla"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def _find_all_matches(self, search_term, categories):
        """Temel string eşleştirmesi ile tüm olası eşleşmeleri bul"""
        matches = []
        normalized_term = self._normalize(search_term)
        
        def search_tree(category_tree):
            for cat in category_tree:
                if self._is_match(normalized_term, cat['name']):
                    matches.append(cat)
                if cat.get('subCategories'):
                    search_tree(cat['subCategories'])
        
        search_tree(categories)
        return matches
    
    def _normalize(self, text):
        """String normalizasyonu (Türkçe karakterlerin dönüşümü ve küçük harfe çevirme)"""
        return text.lower().translate(
            str.maketrans('çğıöşü', 'cgiosu')
        ).strip()
    
    def _is_match(self, search_term, category_name):
        """İki string arasında eşleşme kontrolü"""
        normalized_name = self._normalize(category_name)
        return (
            search_term in normalized_name or
            normalized_name in search_term
        )
    
    def _select_best_match(self, search_term, candidates):
        """Difflib kullanarak en iyi eşleşmeyi seç (temel fallback)"""
        normalized_search = self._normalize(search_term)
        
        for candidate in candidates:
            normalized_name = self._normalize(candidate['name'])
            # Calculate string similarity ratio (0.0 - 1.0)
            candidate['similarity'] = difflib.SequenceMatcher(
                None, normalized_search, normalized_name
            ).ratio()
            
            # Bonus points for exact substring matches
            if normalized_search in normalized_name:
                candidate['similarity'] += 0.2
            if normalized_name in normalized_search:
                candidate['similarity'] += 0.1
                
            # Cap at 1.0
            candidate['similarity'] = min(1.0, candidate['similarity'])
        
        best_match = sorted(candidates, key=lambda x: x['similarity'], reverse=True)[0]
        logger.info(f"Best match for '{search_term}': {best_match['name']} (Score: {best_match['similarity']:.4f})")
        return best_match
    
    def get_required_attributes(self, category_id):
        """Belirli bir kategorinin tüm özniteliklerini API'den getir"""
        try:
            attrs = self.get_category_attributes(category_id)
            attributes = []
            
            # Process all category attributes and log details
            logger.info(f"Processing {len(attrs.get('categoryAttributes', []))} attributes for category {category_id}")
            
            for attr in attrs.get('categoryAttributes', []):
                # Skip attributes without ID
                if not attr.get('attribute') or not attr['attribute'].get('id'):
                    logger.warning(f"Skipping attribute without ID: {attr}")
                    continue
                    
                # Get attribute details
                attribute_id = attr['attribute']['id']
                attribute_name = attr['attribute'].get('name', 'Unknown')
                
                logger.info(f"Processing attribute: {attribute_name} (ID: {attribute_id})")
                
                # Check if this is a 'color' attribute and log it
                if attribute_name.lower() in ['renk', 'color']:
                    logger.info(f"Found color attribute with ID {attribute_id}")
                
                # Skip if no values are available and custom is not allowed
                if not attr.get('attributeValues') and not attr.get('allowCustom'):
                    logger.info(f"Skipping attribute {attribute_name} with no values")
                    continue
                    
                # Get a suitable value
                attribute_value_id = None
                attribute_value_name = None
                
                # If there are attribute values, use the first one
                if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                    attribute_value_id = attr['attributeValues'][0]['id']
                    attribute_value_name = attr['attributeValues'][0].get('name', 'Unknown')
                    logger.info(f"Using attribute value: {attribute_value_name} (ID: {attribute_value_id})")
                
                # If we have a valid attribute ID and value ID, add to the list
                if attribute_id and attribute_value_id:
                    attributes.append({
                        "attributeId": attribute_id,
                        "attributeValueId": attribute_value_id
                    })
                    logger.info(f"Added attribute: {attribute_name}={attribute_value_name}")
            
            # Log summary of attributes
            logger.info(f"Returning {len(attributes)} attributes for category {category_id}")
            return attributes
            
        except Exception as e:
            logger.error(f"Error getting required attributes: {str(e)}")
            return []