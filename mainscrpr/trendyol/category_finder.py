"""
Trendyol Category Finder

This module provides the TrendyolCategoryFinder class that helps with:
1. Finding the best matching Trendyol category for a product
2. Managing required and optional attributes for categories
3. Providing default attributes for certain product types

This is an enhanced version that focuses on:
- Reliability and error handling
- Proper attribute management
- Default attribute values for common categories

The module is designed to work with both basic and advanced search strategies
depending on the available libraries.
"""

import json
import logging
import re
from functools import lru_cache
from typing import Dict, List, Any, Optional, Tuple, Set
import difflib

# DEFAULT_REQUIRED_ATTRIBUTES tanımlama
DEFAULT_REQUIRED_ATTRIBUTES = {
    # Giyim kategorileri için zorunlu öznitelikler
    'clothing': [
        {"attributeId": 338, "attributeValueId": 7189},  # Cinsiyet: Kadın
        {"attributeId": 47, "attributeValueId": 8201},   # Menşei: Türkiye
        {"attributeId": 60, "attributeValueId": 902},    # Yaş Grubu: Yetişkin
    ]
}

from .api_client import TrendyolApi
logger = logging.getLogger(__name__)

class TrendyolCategoryFinder:
    """Handles category discovery and attribute management with dynamic API data"""
    
    def __init__(self, api_client):
        self.api = api_client
        self._category_cache = None
    
    @property
    def category_cache(self):
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self):
        """Fetch all categories from Trendyol API"""
        try:
            # categories.get_categories() kullan, doğrudan get() kullanmak yerine
            data = self.api.categories.get_categories()
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise Exception("Category loading failed. Check API credentials.")
    
    def get_category_attributes(self, category_id):
        """Get attributes for a category directly from API"""
        try:
            return self.api.categories.get_category_attributes(category_id)
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            return {"categoryAttributes": []}
    
    def find_best_category(self, search_term):
        """Find the most relevant category using API data"""
        try:
            categories = self.category_cache
            if not categories:
                raise ValueError("Empty category list from API")
            
            # Find all possible matches
            matches = self._find_all_matches(search_term, categories)
            
            if not matches:
                raise ValueError(f"No matches found for: {search_term}")
            
            return self._select_best_match(search_term, matches)['id']
            
        except Exception as e:
            logger.error(f"Category search failed: {str(e)}")
            raise
    
    def _find_all_matches(self, search_term, categories):
        """Recursively search for matching categories"""
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
        """Normalize text for matching"""
        return text.lower().translate(
            str.maketrans('çğıöşü', 'cgiosu')
        ).strip()
    
    def _is_match(self, search_term, category_name):
        """Check if category matches search term"""
        normalized_name = self._normalize(category_name)
        return (
            search_term in normalized_name or
            normalized_name in search_term
        )
    
    def _select_best_match(self, search_term, candidates):
        """Select best match using string similarity with difflib"""
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
        
        return sorted(candidates, key=lambda x: x['similarity'], reverse=True)[0]
    
    def get_required_attributes(self, category_id):
        """Get required attributes directly from API"""
        try:
            attrs = self.get_category_attributes(category_id)
            return [
                {
                    "attributeId": attr['attribute']['id'],
                    "attributeValueId": self._get_first_value(attr)
                }
                for attr in attrs.get('categoryAttributes', [])
                if attr['required']
            ]
        except Exception as e:
            logger.error(f"Attribute error: {str(e)}")
            return []
    
    def _get_first_value(self, attribute):
        """Get first allowed value for an attribute"""
        if attribute.get('allowCustom'):
            return "Custom Value"
        return attribute['attributeValues'][0]['id'] if attribute.get('attributeValues') else None