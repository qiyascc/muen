"""
New Trendyol API Client implementation based on the reference code.

This module provides a more reliable way to interact with the Trendyol API,
focusing on improved category finding and attribute management.
"""

import requests
import json
import logging
import re
import time
import base64
from urllib.parse import quote
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from functools import lru_cache

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

# Constants
TRENDYOL_API_BASE_URL = "https://apigw.trendyol.com"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

@dataclass
class APIConfig:
    """Configuration for Trendyol API"""
    api_key: str
    api_secret: str
    seller_id: str
    base_url: str = TRENDYOL_API_BASE_URL

class TrendyolAPI:
    """Base class for Trendyol API operations with retry mechanism"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.session = requests.Session()
        
        # Format the auth string and encode as Base64 for Basic Authentication
        auth_string = f"{self.config.api_key}:{self.config.api_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()
        
        self.session.headers.update({
            "Authorization": f"Basic {auth_encoded}",
            "User-Agent": f"{self.config.seller_id} - SelfIntegration",
            "Content-Type": "application/json"
        })
    
    def make_request(self, method: str, endpoint: str, data=None, params=None) -> requests.Response:
        """Generic request method with retry logic"""
        # Ensure endpoint starts with a slash
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        
        # Remove any duplicate /integration prefix from the endpoint
        if endpoint.startswith('/integration') and 'integration' in self.config.base_url:
            endpoint = endpoint.replace('/integration', '', 1)
        
        # Build the URL with proper formatting
        url = f"{self.config.base_url.rstrip('/')}{endpoint}"
        
        # Additional safeguard against duplicate integration paths
        url = url.replace('/integration/integration/', '/integration/')
        
        logger.info(f"Making request: {method} {url}")
        
        for attempt in range(MAX_RETRIES):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
                elif method.upper() == 'POST':
                    response = self.session.post(url, json=data, timeout=DEFAULT_TIMEOUT)
                elif method.upper() == 'PUT':
                    response = self.session.put(url, json=data, timeout=DEFAULT_TIMEOUT)
                elif method.upper() == 'DELETE':
                    response = self.session.delete(url, timeout=DEFAULT_TIMEOUT)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Log response details
                logger.info(f"Response status: {response.status_code}")
                if response.status_code >= 400:
                    logger.error(f"API error: {response.text}")
                
                return response
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                time.sleep(RETRY_DELAY * (attempt + 1))

class TrendyolCategoryFinder:
    """Handles category discovery and attribute management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
        
        # Try to initialize semantic search model
        self.model = None
        self.dictionary = None
        if ADVANCED_SEARCH_AVAILABLE:
            try:
                self.model = SentenceTransformer('emrecan/bert-base-turkish-cased-mean-nli-stsb-tr')
                self.dictionary = MultiDictionary()
                logger.info("Initialized semantic search components")
            except Exception as e:
                logger.error(f"Failed to initialize semantic search: {str(e)}")
    
    @property
    def category_cache(self) -> List[Dict]:
        """Lazy-loaded category cache"""
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self) -> List[Dict]:
        """Fetch all categories from Trendyol API"""
        try:
            response = self.api.make_request('GET', "product/product-categories")
            if response.status_code == 200:
                data = response.json()
                return data.get('categories', [])
            else:
                logger.error(f"Failed to fetch categories: {response.status_code} {response.text}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            return []
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id: int) -> Dict:
        """Get attributes for a specific category with caching"""
        try:
            response = self.api.make_request('GET', f"product/product-categories/{category_id}/attributes")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch attributes for category {category_id}: {response.status_code} {response.text}")
                return {}
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            return {}
    
    def find_best_category(self, search_term: str) -> Optional[int]:
        """Find the most relevant category for a given search term"""
        logger.info(f"Searching for best category match for: '{search_term}'")
        
        if not search_term:
            logger.warning("Empty search term provided")
            return None
            
        try:
            categories = self.category_cache
            if not categories:
                logger.warning("No categories available in cache")
                return None
            
            # Try to find exact matches first
            exact_matches = self._find_exact_matches(search_term, categories)
            if exact_matches:
                best_match = exact_matches[0]
                logger.info(f"Found exact match: {best_match['name']} (ID: {best_match['id']})")
                return best_match['id']
            
            # If no exact matches, use semantic search if available
            if ADVANCED_SEARCH_AVAILABLE and self.model:
                return self._find_best_category_semantic(search_term, categories)
            else:
                # Fallback to basic string matching
                return self._find_best_category_basic(search_term, categories)
                
        except Exception as e:
            logger.error(f"Error finding best category: {str(e)}")
            return None
    
    def _find_exact_matches(self, search_term: str, categories: List[Dict]) -> List[Dict]:
        """Find exact name matches in category tree"""
        matches = []
        self._recursive_exact_match(search_term.lower(), categories, matches)
        return matches
    
    def _recursive_exact_match(self, search_term: str, categories: List[Dict], matches: List[Dict]) -> None:
        """Recursively find exact matches in category tree"""
        for cat in categories:
            if search_term == cat['name'].lower():
                matches.append(cat)
            
            if cat.get('subCategories'):
                self._recursive_exact_match(search_term, cat['subCategories'], matches)
    
    def _find_best_category_semantic(self, search_term: str, categories: List[Dict]) -> Optional[int]:
        """Find best category using semantic similarity"""
        try:
            # Get all leaf categories
            leaf_categories = []
            self._collect_leaf_categories(categories, leaf_categories)
            
            # Get search term embedding
            search_embedding = self.model.encode(search_term, convert_to_tensor=True)
            
            # Get embeddings for all categories and compute similarity
            for cat in leaf_categories:
                cat_embedding = self.model.encode(cat['name'], convert_to_tensor=True)
                cat['similarity'] = util.cos_sim(search_embedding, cat_embedding).item()
            
            # Sort by similarity and get best match
            if leaf_categories:
                matches_sorted = sorted(leaf_categories, key=lambda x: x['similarity'], reverse=True)
                
                # Log top matches for debugging
                logger.info(f"Top matches for '{search_term}':")
                for i, m in enumerate(matches_sorted[:3], 1):
                    logger.info(f"{i}. {m['name']} (Score: {m['similarity']:.4f}, ID: {m['id']})")
                
                best_match = matches_sorted[0]
                logger.info(f"Best semantic match: {best_match['name']} (Score: {best_match['similarity']:.4f}, ID: {best_match['id']})")
                return best_match['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Semantic search error: {str(e)}")
            # Fall back to basic search on error
            return self._find_best_category_basic(search_term, categories)
    
    def _find_best_category_basic(self, search_term: str, categories: List[Dict]) -> Optional[int]:
        """Find best category using basic string matching"""
        leaf_categories = []
        self._collect_leaf_categories(categories, leaf_categories)
        
        if not leaf_categories:
            return None
        
        normalized_search = search_term.lower()
        best_match = None
        best_score = 0
        
        for cat in leaf_categories:
            normalized_name = cat['name'].lower()
            # Use SequenceMatcher for string similarity
            score = difflib.SequenceMatcher(None, normalized_search, normalized_name).ratio()
            
            # Bonus points for substring matches
            if normalized_search in normalized_name:
                score += 0.2
            if normalized_name in normalized_search:
                score += 0.1
            
            # Cap at 1.0
            score = min(1.0, score)
            
            if score > best_score:
                best_score = score
                best_match = cat
        
        if best_match:
            logger.info(f"Best basic match: {best_match['name']} (Score: {best_score:.4f}, ID: {best_match['id']})")
            return best_match['id']
            
        return None
    
    def _collect_leaf_categories(self, categories: List[Dict], result: List[Dict]) -> None:
        """Recursively collect leaf categories"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def get_required_attributes(self, category_id: int) -> List[Dict]:
        """Get required attributes for a specific category"""
        try:
            attrs = self.get_category_attributes(category_id)
            attributes = []
            
            # Process category attributes
            logger.info(f"Processing {len(attrs.get('categoryAttributes', []))} attributes for category {category_id}")
            
            for attr in attrs.get('categoryAttributes', []):
                # Skip attributes without ID
                if not attr.get('attribute') or not attr['attribute'].get('id'):
                    logger.warning(f"Skipping attribute without ID")
                    continue
                
                # Get attribute details
                attribute_id = attr['attribute']['id']
                attribute_name = attr['attribute'].get('name', 'Unknown')
                
                # Check if attribute is required and log it
                is_required = attr.get('required', False)
                logger.info(f"Processing attribute: {attribute_name} (ID: {attribute_id}, Required: {is_required})")
                
                # Only add required attributes
                if not is_required:
                    logger.info(f"Skipping non-required attribute: {attribute_name}")
                    continue
                
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

def get_api_client_from_config(api_key, api_secret, seller_id, base_url=TRENDYOL_API_BASE_URL):
    """Create a TrendyolAPI client from configuration parameters"""
    config = APIConfig(
        api_key=api_key,
        api_secret=api_secret,
        seller_id=seller_id,
        base_url=base_url
    )
    return TrendyolAPI(config)

def find_category_for_product(api_client, product_name, category_name=None):
    """Find the best category ID for a product"""
    finder = TrendyolCategoryFinder(api_client)
    search_term = category_name if category_name else product_name
    return finder.find_best_category(search_term)

def get_required_attributes(api_client, category_id):
    """Get required attributes for a specific category"""
    finder = TrendyolCategoryFinder(api_client)
    return finder.get_required_attributes(category_id)