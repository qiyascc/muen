"""
Trendyol Category Finder

Bu modül, Trendyol API'sinden gelen kategorileri eşleştirmek için kullanılan
TrendyolCategoryFinder sınıfını içerir.

Özellikler:
1. Semantic search ile kategori eşleştirmesi (sentence-transformers kullanılarak)
2. Kategori özniteliklerinin API'den alınması ve yönetilmesi
3. Temel string eşleştirmesi için fallback mekanizması

Bu dosya, mevcut API istemcisiyle çalışacak şekilde tasarlanmıştır.
"""

import logging
import json
from functools import lru_cache
from typing import Dict, List, Any, Optional

# Try to import sentence-transformers for semantic similarity
try:
    from sentence_transformers import SentenceTransformer, util
    from PyMultiDictionary import MultiDictionary
    ADVANCED_SEARCH_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("Semantic search enabled with sentence-transformers")
except ImportError:
    ADVANCED_SEARCH_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("sentence-transformers not available, using basic search")
    import difflib  # Fallback to difflib for basic string matching


class TrendyolCategoryFinder:
    """
    Trendyol için kategori bulucu sınıfı.
    
    Bu sınıf, ürün adı veya kategorisine göre en uygun Trendyol kategori ID'sini bulmak için
    semantik arama veya temel string eşleştirmesi kullanır.
    """
    
    def __init__(self, api_client):
        """
        TrendyolCategoryFinder sınıfını başlat.
        
        Args:
            api_client: Trendyol API istemcisi
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
            data = self.api.get("product/product-categories")
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise Exception("Failed to load categories. Please check your API credentials.")
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id):
        """Belirli bir kategori için öznitelikleri API'den getir"""
        try:
            data = self.api.get(f"product/product-categories/{category_id}/attributes")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            return {"categoryAttributes": []}
    
    def find_best_category(self, search_term):
        """Verilen arama terimi için en uygun kategoriyi bul"""
        try:
            categories = self.category_cache
            if not categories:
                raise ValueError("Empty category list received from API")
            
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
            logger.error(f"Category search failed for '{search_term}': {str(e)}")
            # If we can't find a suitable category, return a safe default
            logger.warning("Returning default category ID as fallback")
            return 385  # Default to a safe fallback category
    
    def _find_best_category_semantic(self, search_term, categories):
        """Semantik benzerlik ile en iyi kategoriyi bul"""
        try:
            # Expand search terms with synonyms if possible
            search_terms = {search_term.lower()}
            try:
                if self.dictionary:
                    synonyms = self.dictionary.synonym('tr', search_term.lower())
                    search_terms.update(synonyms[:5])  # Limit to 5 synonyms
            except Exception as e:
                logger.debug(f"Could not expand search terms: {str(e)}")
            
            all_matches = self._find_all_possible_matches(search_term, categories)
            
            # Check for exact match first
            for match in all_matches:
                if search_term.lower() == match['name'].lower():
                    logger.info(f"Found exact match: {match['name']} (ID: {match['id']})")
                    return match['id']
            
            # Get all leaf categories if no direct matches
            if not all_matches:
                leaf_categories = []
                self._collect_leaf_categories(categories, leaf_categories)
                
                if leaf_categories:
                    return self._select_best_match_semantic(search_term, leaf_categories)['id']
                else:
                    raise ValueError(f"No categories found to match with '{search_term}'")
            
            # Otherwise select best match from found matches
            return self._select_best_match_semantic(search_term, all_matches)['id']
                
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            # Fall back to basic search
            matches = self._find_all_matches(search_term, categories)
            if not matches:
                raise ValueError(f"No matches found for: {search_term}")
            return self._select_best_match(search_term, matches)['id']
    
    def _find_all_possible_matches(self, search_term, categories):
        """Tüm olası eşleşmeleri bul (eş anlamlılar dahil)"""
        search_terms = {search_term.lower()}
        
        try:
            if self.dictionary:
                synonyms = self.dictionary.synonym('tr', search_term.lower())
                search_terms.update(synonyms[:5])
        except Exception as e:
            logger.debug(f"Couldn't fetch synonyms: {str(e)}")
        
        matches = []
        for term in search_terms:
            matches.extend(self._find_matches_for_term(term, categories))
        
        # Remove duplicates while preserving order
        seen_ids = set()
        return [m for m in matches if not (m['id'] in seen_ids or seen_ids.add(m['id']))]
    
    def _find_matches_for_term(self, term, categories):
        """Kategori ağacında eşleşmeleri bulma"""
        matches = []
        term_lower = term.lower()
        
        for cat in categories:
            cat_name_lower = cat['name'].lower()
            
            if term_lower == cat_name_lower or term_lower in cat_name_lower:
                # Only include leaf categories
                if not cat.get('subCategories'):
                    matches.append(cat)
            
            # Recursive search in subcategories
            if cat.get('subCategories'):
                matches.extend(self._find_matches_for_term(term, cat['subCategories']))
        
        return matches
    
    def _collect_leaf_categories(self, categories, result):
        """Alt kategorisi olmayan tüm kategorileri topla"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def _select_best_match_semantic(self, search_term, candidates):
        """Semantik benzerlik ile en iyi eşleşmeyi seç"""
        if not self.model:
            return self._select_best_match(search_term, candidates)
            
        search_embedding = self.model.encode(search_term, convert_to_tensor=True)
        
        for candidate in candidates:
            try:
                candidate_embedding = self.model.encode(candidate['name'], convert_to_tensor=True)
                candidate['similarity'] = util.cos_sim(search_embedding, candidate_embedding).item()
            except Exception as e:
                logger.error(f"Error computing similarity: {str(e)}")
                # Fallback to string similarity
                candidate['similarity'] = self._string_similarity(search_term, candidate['name'])
        
        sorted_candidates = sorted(candidates, key=lambda x: x['similarity'], reverse=True)
        
        # Log top matches for debugging
        logger.info(f"Top 3 matches for '{search_term}':")
        for i, candidate in enumerate(sorted_candidates[:3], 1):
            logger.info(f"{i}. {candidate['name']} (Similarity: {candidate['similarity']:.2f})")
        
        return sorted_candidates[0]
    
    def _find_all_matches(self, search_term, categories):
        """Temel string eşleştirmesi ile tüm olası eşleşmeleri bul"""
        matches = []
        normalized_term = search_term.lower()
        
        def search_tree(category_tree):
            for cat in category_tree:
                cat_name = cat['name'].lower()
                if normalized_term in cat_name or cat_name in normalized_term:
                    matches.append(cat)
                if cat.get('subCategories'):
                    search_tree(cat['subCategories'])
        
        search_tree(categories)
        return matches
    
    def _select_best_match(self, search_term, candidates):
        """String benzerliği ile en iyi eşleşmeyi seç"""
        normalized_search = search_term.lower()
        
        for candidate in candidates:
            candidate['similarity'] = self._string_similarity(normalized_search, candidate['name'].lower())
        
        best_match = sorted(candidates, key=lambda x: x['similarity'], reverse=True)[0]
        logger.info(f"Best match for '{search_term}': {best_match['name']} (Score: {best_match['similarity']:.4f})")
        return best_match
    
    def _string_similarity(self, s1, s2):
        """İki string arasındaki benzerliği hesapla"""
        # Use difflib for string similarity
        similarity = difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
        
        # Bonus points for exact substring matches
        if s1.lower() in s2.lower():
            similarity += 0.2
        if s2.lower() in s1.lower():
            similarity += 0.1
            
        # Cap at 1.0
        return min(1.0, similarity)
    
    def get_required_attributes_for_category(self, category_id):
        """Belirli bir kategori için gerekli öznitelikleri API'den getir"""
        try:
            attrs = self.get_category_attributes(category_id)
            attributes = []
            
            logger.info(f"Processing attributes for category {category_id}")
            
            for attr in attrs.get('categoryAttributes', []):
                # Skip attributes without valid data
                if not attr.get('attribute') or not attr['attribute'].get('id'):
                    continue
                    
                attribute_id = attr['attribute']['id']
                attribute_name = attr['attribute'].get('name', 'Unknown')
                
                # Special handling for color attribute
                is_color_attr = attribute_name.lower() in ['renk', 'color']
                if is_color_attr:
                    logger.info(f"Found color attribute with ID {attribute_id}")
                
                attribute = {
                    "attributeId": attribute_id,
                    "attributeName": attribute_name
                }
                
                # If there are attribute values and custom values not allowed, use the first one
                if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                    if not attr.get('allowCustom'):
                        attribute["attributeValueId"] = attr['attributeValues'][0]['id']
                        attribute["attributeValue"] = attr['attributeValues'][0]['name']
                    else:
                        attribute["customAttributeValue"] = f"Sample {attribute_name}"
                else:
                    attribute["customAttributeValue"] = ""
                
                attributes.append(attribute)
            
            logger.info(f"Found {len(attributes)} attributes for category {category_id}")
            return attributes
            
        except Exception as e:
            logger.error(f"Error getting attributes for category {category_id}: {str(e)}")
            return []