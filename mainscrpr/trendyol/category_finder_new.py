"""
Yeni Trendyol Category Finder

Bu modül, Trendyol API'sinden gelen kategorileri eşleştirmek için kullanılan
TrendyolCategoryFinder sınıfının gelişmiş bir versiyonunu sağlar.

Özellikler:
1. Semantic search ile daha doğru kategori eşleştirmesi (sentence-transformers kütüphanesi kullanılarak)
2. Kategori özniteliklerinin doğru şekilde alınması ve yönetilmesi
3. Fallback mekanizmaları ile kütüphane yoksa basit string eşleştirmesi yapma

Bu dosya, mevcut API istemcisiyle çalışacak şekilde tasarlanmıştır.
"""

import logging
import json
from functools import lru_cache
from typing import Dict, List, Any, Optional

# Try to import sentence-transformers for advanced semantic similarity
try:
    from sentence_transformers import SentenceTransformer, util
    from PyMultiDictionary import MultiDictionary
    ADVANCED_SEARCH_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("Advanced semantic search enabled with sentence-transformers")
except ImportError:
    ADVANCED_SEARCH_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("sentence-transformers not available, using basic search")
    import difflib  # Fallback to difflib for basic string matching


class TrendyolCategoryFinder:
    """
    Gelişmiş kategori bulucu sınıfı.
    
    Bu sınıf, ürün adı veya kategorisine göre en uygun Trendyol kategori ID'sini bulmak için
    gelişmiş semantik arama veya temel string eşleştirmesi kullanır.
    
    Sentence-transformers kütüphanesi mevcutsa semantik arama kullanılır, 
    değilse difflib ile temel string eşleştirmesine düşer.
    """
    
    def __init__(self, api_client):
        """
        TrendyolCategoryFinder sınıfını başlat.
        
        Args:
            api_client: Trendyol API istemcisi (TrendyolApi sınıfı)
        """
        self.api = api_client
        self._category_cache = None
        
        # Try to initialize sentence-transformers if available
        if ADVANCED_SEARCH_AVAILABLE:
            try:
                # Use multilingual model for Turkish
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                self.dictionary = MultiDictionary()
                logger.info("Sentence Transformer model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to initialize semantic model: {str(e)}")
                # Fall back to basic search
                self.model = None
                self.dictionary = None
        else:
            self.model = None
            self.dictionary = None
    
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
            
            # Use advanced semantic search if available
            if ADVANCED_SEARCH_AVAILABLE and self.model is not None:
                return self._find_best_category_semantic(search_term, categories)
            else:
                # Fall back to basic string matching
                matches = self._find_all_matches(search_term, categories)
                if not matches:
                    raise ValueError(f"No matches found for: {search_term}")
                return self._select_best_match(search_term, matches)['id']
            
        except Exception as e:
            logger.error(f"Category search failed: {str(e)}")
            # If we can't find a suitable category, return a safe default
            logger.warning("Returning default category ID as fallback")
            return 385  # Default to Women's Clothing - Jacket as a safe fallback
    
    def _find_best_category_semantic(self, search_term, categories):
        """Sentence-transformers kullanarak semantik benzerlikle en iyi kategoriyi bul"""
        try:
            # Get expanded search terms with synonyms if possible
            search_terms = {search_term.lower()}
            try:
                if self.dictionary:
                    synonyms = self.dictionary.synonym('tr', search_term.lower())
                    search_terms.update(synonyms[:5])  # Limit to 5 synonyms to avoid noise
            except Exception as e:
                logger.debug(f"Could not expand search terms: {str(e)}")
            
            # Collect all leaf categories
            leaf_categories = []
            self._collect_leaf_categories(categories, leaf_categories)
            
            # Find matches using all search terms
            matches = []
            for term in search_terms:
                for cat in leaf_categories:
                    # Compute semantic similarity
                    if self.model:
                        try:
                            search_embedding = self.model.encode(term, convert_to_tensor=True)
                            cat_embedding = self.model.encode(cat['name'], convert_to_tensor=True)
                            similarity = util.cos_sim(search_embedding, cat_embedding).item()
                            cat['similarity'] = similarity
                            matches.append(cat.copy())
                        except Exception as e:
                            logger.error(f"Semantic similarity error: {str(e)}")
                            # Fall back to string similarity
                            cat['similarity'] = difflib.SequenceMatcher(None, term, cat['name']).ratio()
                            matches.append(cat.copy())
            
            # Sort by similarity and select best match
            if matches:
                matches_sorted = sorted(matches, key=lambda x: x['similarity'], reverse=True)
                
                # Log top matches for debugging
                logger.info(f"Top matches for '{search_term}':")
                for i, m in enumerate(matches_sorted[:3], 1):
                    logger.info(f"{i}. {m['name']} (Score: {m['similarity']:.4f}, ID: {m['id']})")
                
                return matches_sorted[0]['id']
            else:
                # If semantic search fails, fall back to basic search
                logger.warning("Semantic search found no matches, falling back to basic search")
                matches = self._find_all_matches(search_term, categories)
                if not matches:
                    raise ValueError(f"No matches found for: {search_term}")
                return self._select_best_match(search_term, matches)['id']
                
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            # Fall back to basic search
            matches = self._find_all_matches(search_term, categories)
            if not matches:
                raise ValueError(f"No matches found for: {search_term}")
            return self._select_best_match(search_term, matches)['id']
    
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
            
            # İlk önce zorunlu (required) olanları işle
            required_attrs = []
            non_required_attrs = []
            
            for attr in attrs.get('categoryAttributes', []):
                if not attr['attribute'].get('id'):
                    continue
                    
                # Attribute değerleri yoksa ve özel değer de izin verilmiyorsa atla
                if not attr.get('attributeValues') and not attr.get('allowCustom'):
                    continue
                    
                attribute_id = attr['attribute']['id']
                
                # Uygun bir değer bul
                attribute_value_id = None
                
                # Eğer attribute değerleri varsa ilkini kullan
                if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                    attribute_value_id = attr['attributeValues'][0]['id']
                
                # Eğer geçerli bir attribute ID ve value ID varsa listeye ekle
                if attribute_id and attribute_value_id:
                    attribute_data = {
                        "attributeId": attribute_id, 
                        "attributeValueId": attribute_value_id
                    }
                    
                    # Zorunlu olanları önce ekle
                    if attr.get('required'):
                        required_attrs.append(attribute_data)
                    else:
                        non_required_attrs.append(attribute_data)
            
            # Önce zorunlu sonra diğer özellikler
            attributes = required_attrs + non_required_attrs
            
            return attributes
            
        except Exception as e:
            logger.error(f"Error getting required attributes: {str(e)}")
            return []