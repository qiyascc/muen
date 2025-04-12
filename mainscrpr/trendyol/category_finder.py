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
- Advanced semantic similarity with sentence-transformers (if available)

The module is designed to work with both basic and advanced search strategies
depending on the available libraries.
"""

import json
import logging
import re
from functools import lru_cache
from typing import Dict, List, Any, Optional, Tuple, Set
import difflib

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

class TrendyolCategoryFinder:
    """Handles category discovery and attribute management with dynamic API data"""
    
    def __init__(self, api_client):
        self.api = api_client
        self._category_cache = None
        
        # Try to initialize sentence-transformers if available
        if ADVANCED_SEARCH_AVAILABLE:
            try:
                # Use emrecan/bert-base-turkish-cased-mean-nli-stsb-tr for Turkish
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
        """Find the most relevant category using the best available method"""
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
            raise
    
    def _find_best_category_semantic(self, search_term, categories):
        """Find best category using semantic similarity with sentence-transformers"""
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
        """Recursively collect all leaf categories (no children)"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def _find_all_matches(self, search_term, categories):
        """Recursively search for matching categories (basic string matching)"""
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
        """Select best match using string similarity with difflib (basic fallback)"""
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