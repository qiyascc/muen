import requests
import json
from urllib.parse import quote
from sentence_transformers import SentenceTransformer, util
from collections import defaultdict
import uuid
from PyMultiDictionary import MultiDictionary
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
import logging
from functools import lru_cache
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trendyol_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TRENDYOL_API_BASE_URL = "https://apigw.trendyol.com/integration/"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

@dataclass
class APIConfig:
    api_key: str
    seller_id: str
    base_url: str = TRENDYOL_API_BASE_URL

@dataclass
class ProductData:
    barcode: str
    title: str
    product_main_id: str
    brand_name: str
    category_name: str
    quantity: int
    stock_code: str
    price: float
    sale_price: float
    description: str
    image_url: str
    vat_rate: int = 10
    cargo_company_id: int = 10
    currency_type: str = "TRY"
    dimensional_weight: int = 1

class TrendyolAPI:
    """Base class for Trendyol API operations with retry mechanism"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {self.config.api_key}",
            "User-Agent": f"{self.config.seller_id} - SelfIntegration",
            "Content-Type": "application/json"
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Generic request method with retry logic"""
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                time.sleep(RETRY_DELAY * (attempt + 1))
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Dict) -> Dict:
        return self._make_request('POST', endpoint, json=data)

class TrendyolCategoryFinder:
    """Handles category discovery and attribute management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.model = SentenceTransformer('emrecan/bert-base-turkish-cased-mean-nli-stsb-tr')
        self.dictionary = MultiDictionary()
        self._category_cache = None
        self._attribute_cache = {}
    
    @property
    def category_cache(self) -> List[Dict]:
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self) -> List[Dict]:
        """Fetch all categories from Trendyol API"""
        try:
            data = self.api.get("product/product-categories")
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise Exception("Failed to load categories. Please check your API credentials and try again.")
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id: int) -> Dict:
        """Get attributes for a specific category with caching"""
        try:
            data = self.api.get(f"product/product-categories/{category_id}/attributes")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            raise Exception(f"Failed to load attributes for category {category_id}")
    
    def find_best_category(self, search_term: str) -> int:
        """Find the most relevant category for a given search term"""
        try:
            categories = self.category_cache
            if not categories:
                raise ValueError("Empty category list received from API")
            
            all_matches = self._find_all_possible_matches(search_term, categories)
            
            if exact_match := self._find_exact_match(search_term, all_matches):
                return exact_match
            
            if all_matches:
                return self._select_best_match(search_term, all_matches)['id']
            
            leaf_categories = self._get_all_leaf_categories(categories)
            if leaf_categories:
                return self._select_best_match(search_term, leaf_categories)['id']
            
            suggestions = self._get_category_suggestions(search_term, categories)
            raise ValueError(f"No exact match found. Closest categories:\n{suggestions}")
            
        except Exception as e:
            logger.error(f"Category search failed for '{search_term}': {str(e)}")
            raise
    
    def _find_all_possible_matches(self, search_term: str, categories: List[Dict]) -> List[Dict]:
        """Find all possible matches including synonyms"""
        search_terms = {search_term.lower()}
        
        try:
            synonyms = self.dictionary.synonym('tr', search_term.lower())
            search_terms.update(synonyms[:5])
        except Exception as e:
            logger.debug(f"Couldn't fetch synonyms: {str(e)}")
        
        matches = []
        for term in search_terms:
            matches.extend(self._find_matches_for_term(term, categories))
        
        seen_ids = set()
        return [m for m in matches if not (m['id'] in seen_ids or seen_ids.add(m['id']))]
    
    def _find_matches_for_term(self, term: str, categories: List[Dict]) -> List[Dict]:
        """Recursively find matches in category tree"""
        matches = []
        term_lower = term.lower()
        
        for cat in categories:
            cat_name_lower = cat['name'].lower()
            
            if term_lower == cat_name_lower or term_lower in cat_name_lower:
                if not cat.get('subCategories'):
                    matches.append(cat)
            
            if cat.get('subCategories'):
                matches.extend(self._find_matches_for_term(term, cat['subCategories']))
        
        return matches
    
    def _find_exact_match(self, search_term: str, matches: List[Dict]) -> Optional[int]:
        """Check for exact name matches"""
        search_term_lower = search_term.lower()
        for match in matches:
            if search_term_lower == match['name'].lower():
                return match['id']
        return None
    
    def _select_best_match(self, search_term: str, candidates: List[Dict]) -> Dict:
        """Select best match using semantic similarity"""
        search_embedding = self.model.encode(search_term, convert_to_tensor=True)
        
        for candidate in candidates:
            candidate_embedding = self.model.encode(candidate['name'], convert_to_tensor=True)
            candidate['similarity'] = util.cos_sim(search_embedding, candidate_embedding).item()
        
        candidates_sorted = sorted(candidates, key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Top 3 matches for '{search_term}':")
        for i, candidate in enumerate(candidates_sorted[:3], 1):
            logger.info(f"{i}. {candidate['name']} (Similarity: {candidate['similarity']:.2f})")
        
        return candidates_sorted[0]
    
    def _get_all_leaf_categories(self, categories: List[Dict]) -> List[Dict]:
        """Get all leaf categories (categories without children)"""
        leaf_categories = []
        self._collect_leaf_categories(categories, leaf_categories)
        return leaf_categories
    
    def _collect_leaf_categories(self, categories: List[Dict], result: List[Dict]) -> None:
        """Recursively collect leaf categories"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def _get_category_suggestions(self, search_term: str, categories: List[Dict], top_n: int = 3) -> str:
        """Generate user-friendly suggestions"""
        leaf_categories = self._get_all_leaf_categories(categories)
        
        search_embedding = self.model.encode(search_term, convert_to_tensor=True)
        for cat in leaf_categories:
            cat_embedding = self.model.encode(cat['name'], convert_to_tensor=True)
            cat['similarity'] = util.cos_sim(search_embedding, cat_embedding).item()
        
        sorted_cats = sorted(leaf_categories, key=lambda x: x['similarity'], reverse=True)
        
        suggestions = []
        for i, cat in enumerate(sorted_cats[:top_n], 1):
            suggestions.append(f"{i}. {cat['name']} (Similarity: {cat['similarity']:.2f}, ID: {cat['id']})")
        
        return "\n".join(suggestions)

class TrendyolProductManager:
    """Handles product creation and management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.category_finder = TrendyolCategoryFinder(api_client)