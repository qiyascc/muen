"""
Improved Trendyol Category Finder

This module provides an enhanced TrendyolCategoryFinder that:
1. Does not require local category storage
2. Uses direct API calls for all category operations
3. Handles attributes flexibly without requiring mandatory fields
4. Falls back gracefully when advanced libraries are unavailable
"""

import json
import logging
import re
import difflib
import uuid
from functools import lru_cache
from typing import Dict, List, Any, Optional, Tuple, Set
from urllib.parse import quote

# Advanced imports attempt
try:
    from sentence_transformers import SentenceTransformer, util
    from PyMultiDictionary import MultiDictionary
    ADVANCED_SEARCH_AVAILABLE = True
except ImportError:
    ADVANCED_SEARCH_AVAILABLE = False

logger = logging.getLogger(__name__)

class TrendyolCategoryFinderImproved:
    """Enhanced category finder without local storage requirements"""
    
    def __init__(self, api_client):
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
        self.advanced_search_available = ADVANCED_SEARCH_AVAILABLE
        
        # Try to initialize sentence-transformers if available
        if self.advanced_search_available:
            try:
                # Çok dilli model kullan (Türkçe için daha iyi)
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                self.dictionary = MultiDictionary()
                logger.info("Advanced semantic search enabled")
            except Exception as e:
                logger.error(f"Failed to initialize advanced search: {str(e)}")
                self.model = None
                self.dictionary = None
                self.advanced_search_available = False
        else:
            logger.info("Using basic string matching for category search")
            self.model = None
            self.dictionary = None
    
    @property
    def category_cache(self):
        """Lazy-load and cache categories"""
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self):
        """Fetch all categories from API"""
        try:
            endpoint = "product/product-categories"
            response = self.api.make_request('GET', endpoint)
            if not response or 'categories' not in response:
                logger.error(f"Invalid category response: {response}")
                return []
            return response.get('categories', [])
        except Exception as e:
            logger.error(f"Category fetch failed: {str(e)}")
            return []
    
    @lru_cache(maxsize=100)
    def get_category_attributes(self, category_id):
        """Get attributes for a specific category with caching"""
        if category_id in self._attribute_cache:
            return self._attribute_cache[category_id]
        
        try:
            endpoint = f"product/product-categories/{category_id}/attributes"
            response = self.api.make_request('GET', endpoint)
            
            if response and 'categoryAttributes' in response:
                self._attribute_cache[category_id] = response
                return response
            
            logger.warning(f"No attributes found for category {category_id}")
            return {"categoryAttributes": []}
        except Exception as e:
            logger.error(f"Attribute fetch failed for category {category_id}: {str(e)}")
            return {"categoryAttributes": []}
    
    def find_best_category(self, search_term):
        """Find the best matching category using available methods"""
        if not search_term:
            raise ValueError("Empty search term")
        
        try:
            # Start with keyword-based matching for common categories
            keyword_match = self._find_by_keywords(search_term)
            if keyword_match:
                logger.info(f"Found category by keyword: {keyword_match}")
                return keyword_match
            
            # Try advanced semantic search if available
            if self.model is not None:
                try:
                    category_id = self._find_by_semantic_search(search_term)
                    if category_id:
                        return category_id
                except Exception as e:
                    logger.warning(f"Semantic search failed: {str(e)}")
            
            # Fall back to basic string matching
            all_matches = self._find_all_matches(search_term)
            if all_matches:
                return self._select_best_match(search_term, all_matches)['id']
            
            # Last resort: get leaf categories and find closest match
            leaf_categories = self._get_all_leaf_categories()
            if leaf_categories:
                return self._select_best_match(search_term, leaf_categories)['id']
            
            raise ValueError(f"No category found for: {search_term}")
            
        except Exception as e:
            logger.error(f"Category search failed: {str(e)}")
            # Fall back to a default category if all else fails
            return 1
    
    def _find_by_keywords(self, search_term):
        """Match common categories by keywords"""
        keyword_map = {
            'kadin': 41,  # Kadın Giyim (Women's Clothing)
            'kadın': 41,  # Kadın Giyim (Women's Clothing)
            'women': 41,  # Kadın Giyim (Women's Clothing) - English
            "women's": 41,  # Kadın Giyim (Women's Clothing) - English
            'çocuk': 674,  # Çocuk Gereçleri (Children's Items)
            'cocuk': 674,  # Çocuk Gereçleri (Children's Items)
            'child': 674,  # Çocuk Gereçleri (Children's Items) - English
            'children': 674,  # Çocuk Gereçleri (Children's Items) - English
            'bebek': 2164,  # Bebek Hediyelik (Baby Items)
            'baby': 2164,  # Bebek Hediyelik (Baby Items) - English
            'ayakkabi': 403,  # Ayakkabı (Shoes)
            'ayakkabı': 403,  # Ayakkabı (Shoes)
            'shoe': 403,  # Ayakkabı (Shoes) - English
            'shoes': 403,  # Ayakkabı (Shoes) - English
            'aksesuar': 368,  # Aksesuar (Accessories)
            'accessory': 368,  # Aksesuar (Accessories) - English
            'accessories': 368,  # Aksesuar (Accessories) - English
            'tisort': 384,  # T-shirt
            'tişört': 384,  # T-shirt
            't-shirt': 384,  # T-shirt - With dash
            'tshirt': 384,  # T-shirt - Without dash
            't shirt': 384,  # T-shirt - With space
            'pantolon': 383,  # Pants
            'pant': 383,  # Pants - English
            'pants': 383,  # Pants - English
            'jean': 383,  # Jeans - English
            'jeans': 383,  # Jeans - English
            'gömlek': 385,  # Shirt
            'gomlek': 385,  # Shirt
            'shirt': 385,  # Shirt - English
            'elbise': 1032,  # Dress
            'dress': 1032,  # Dress - English
            'bluz': 1027,  # Blouse
            'blouse': 1027  # Blouse - English
        }
        
        # Normalize search text
        search_text = re.sub(r'[^\w\s]', ' ', search_term.lower())
        search_text = ' ' + re.sub(r'\s+', ' ', search_text) + ' '
        
        # Check for each keyword
        for keyword, category_id in keyword_map.items():
            # Search with word boundaries
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, search_text):
                return category_id
        
        return None
    
    def _find_by_semantic_search(self, search_term):
        """Find category using semantic search"""
        if not self.model:
            return None
            
        try:
            # Get expanded search terms with synonyms if available
            search_terms = {search_term.lower()}
            try:
                if self.dictionary:
                    synonyms = self.dictionary.synonym('tr', search_term.lower())
                    if synonyms:
                        search_terms.update(synonyms[:3])  # Limit to avoid noise
            except Exception:
                pass
                
            # Get all leaf categories
            leaf_categories = self._get_all_leaf_categories()
            if not leaf_categories:
                return None
                
            # Compute similarities
            top_matches = []
            for term in search_terms:
                try:
                    term_embedding = self.model.encode(term, convert_to_tensor=True)
                    
                    for cat in leaf_categories:
                        cat_name = cat['name']
                        cat_embedding = self.model.encode(cat_name, convert_to_tensor=True)
                        similarity = float(util.cos_sim(term_embedding, cat_embedding).item())
                        
                        top_matches.append({
                            'id': cat['id'],
                            'name': cat_name,
                            'similarity': similarity
                        })
                except Exception as e:
                    logger.debug(f"Error encoding: {str(e)}")
                    
            # Sort and return best match
            if top_matches:
                top_matches.sort(key=lambda x: x['similarity'], reverse=True)
                logger.info(f"Top semantic match: {top_matches[0]['name']} ({top_matches[0]['similarity']:.4f})")
                return top_matches[0]['id']
                
        except Exception as e:
            logger.error(f"Semantic search error: {str(e)}")
            
        return None
    
    def _find_all_matches(self, search_term):
        """Find all matching categories using basic string matching"""
        matches = []
        normalized_term = self._normalize_text(search_term)
        
        def search_categories(categories):
            for cat in categories:
                normalized_name = self._normalize_text(cat['name'])
                if (normalized_term in normalized_name or 
                    normalized_name in normalized_term):
                    matches.append(cat)
                
                if 'subCategories' in cat and cat['subCategories']:
                    search_categories(cat['subCategories'])
        
        search_categories(self.category_cache)
        return matches
    
    def _get_all_leaf_categories(self):
        """Get all leaf categories (categories without children)"""
        leaf_categories = []
        
        def collect_leaves(categories):
            for cat in categories:
                if not cat.get('subCategories'):
                    leaf_categories.append(cat)
                else:
                    collect_leaves(cat['subCategories'])
        
        collect_leaves(self.category_cache)
        return leaf_categories
    
    def _normalize_text(self, text):
        """Normalize text for matching"""
        if not text:
            return ""
        # Convert Turkish characters and lowercase
        return text.lower().translate(
            str.maketrans('çğıöşüâîûÇĞİÖŞÜÂÎÛ', 'cgiosuaiuCGIOSUAIU')
        ).strip()
    
    def _select_best_match(self, search_term, candidates):
        """Select best match using string similarity"""
        if not candidates:
            return None
            
        normalized_term = self._normalize_text(search_term)
        
        for candidate in candidates:
            normalized_name = self._normalize_text(candidate['name'])
            similarity = difflib.SequenceMatcher(None, normalized_term, normalized_name).ratio()
            
            # Bonus for exact matches
            if normalized_term == normalized_name:
                similarity += 0.5
            elif normalized_term in normalized_name:
                similarity += 0.3
            elif normalized_name in normalized_term:
                similarity += 0.2
                
            candidate['similarity'] = min(1.0, similarity)
        
        # Sort by similarity score
        sorted_candidates = sorted(candidates, key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Best match for '{search_term}': {sorted_candidates[0]['name']} " 
                   f"(Score: {sorted_candidates[0]['similarity']:.4f})")
                   
        return sorted_candidates[0]
    
    def get_required_attributes(self, category_id):
        """Get required attributes with proper ID format"""
        try:
            attrs_data = self.get_category_attributes(category_id)
            required_attrs = []
            
            for attr in attrs_data.get('categoryAttributes', []):
                if attr.get('required'):
                    if not attr.get('attributeValues'):
                        continue
                        
                    # Get first valid attribute value
                    attr_value = attr['attributeValues'][0]['id']
                    
                    required_attrs.append({
                        "attributeId": attr['attribute']['id'],
                        "attributeValueId": attr_value
                    })
            
            return required_attrs
            
        except Exception as e:
            logger.error(f"Error getting required attributes: {str(e)}")
            return []
    
    def get_all_attributes(self, category_id):
        """Get all attribute details for a category"""
        try:
            attrs_data = self.get_category_attributes(category_id)
            return attrs_data.get('categoryAttributes', [])
        except Exception as e:
            logger.error(f"Error getting all attributes: {str(e)}")
            return []

    def get_color_attribute_info(self, category_id):
        """Get color attribute details for a category"""
        try:
            attrs_data = self.get_category_attributes(category_id)
            for attr in attrs_data.get('categoryAttributes', []):
                if attr['attribute']['name'].lower() == 'renk':
                    return attr
            return None
        except Exception as e:
            logger.error(f"Error getting color attribute: {str(e)}")
            return None
            
    def find_attribute_value_id(self, category_id, attribute_name, value_name):
        """Find attribute value ID for a given name"""
        try:
            attrs_data = self.get_category_attributes(category_id)
            
            for attr in attrs_data.get('categoryAttributes', []):
                if attr['attribute']['name'].lower() == attribute_name.lower():
                    for value in attr.get('attributeValues', []):
                        if value['name'].lower() == value_name.lower():
                            return value['id']
            
            return None
        except Exception as e:
            logger.error(f"Error finding attribute value: {str(e)}")
            return None