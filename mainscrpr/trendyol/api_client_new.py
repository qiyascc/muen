import requests
import json
import time
import re
import uuid
import copy
from urllib.parse import quote
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from functools import lru_cache
import logging
from decimal import Decimal

try:
    from django.utils import timezone
except ImportError:
    import datetime
    timezone = datetime.datetime
from .models import TrendyolProduct, TrendyolBrand, TrendyolCategory, TrendyolAPIConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trendyol_integration.log'),
        logging.StreamHandler()
    ])
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
    # Endpoint işlenmeden önce debug logu
    print(f"[DEBUG-API] make_request çağrısı. Orijinal endpoint: {endpoint}")

    url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    print(f"[DEBUG-API] Oluşturulan URL: {url}")

    kwargs.setdefault('timeout', DEFAULT_TIMEOUT)

    for attempt in range(MAX_RETRIES):
      try:
        print(f"[DEBUG-API] SON İSTEK: {method} {url}")
        print(f"[DEBUG-API] İSTEK HEADERS: {self.session.headers}")

        # Debug request payload for POST requests
        if method == 'POST' and 'json' in kwargs:
          print(
              f"[DEBUG-API] İSTEK PAYLOAD: {json.dumps(kwargs.get('json', {}), indent=2, ensure_ascii=False)}"
          )

        response = self.session.request(method, url, **kwargs)

        # Debug response details
        print(f"[DEBUG-API] YANIT KODU: {response.status_code}")
        print(f"[DEBUG-API] YANIT HEADERS: {dict(response.headers)}")

        # Print response content (truncated if too long)
        resp_text = response.text[:1000] + '...' if len(
            response.text) > 1000 else response.text
        print(f"[DEBUG-API] YANIT İÇERİĞİ: {resp_text}")

        # More detailed error logging
        if response.status_code >= 400:
          print(f"[DEBUG-API] HATA DETAYI: Kod {response.status_code}")
          try:
            if 'application/json' in response.headers.get('Content-Type', ''):
              error_data = response.json()
              print(
                  f"[DEBUG-API] JSON HATA DETAYI: {json.dumps(error_data, indent=2, ensure_ascii=False)}"
              )
          except Exception as e:
            print(f"[DEBUG-API] JSON çözümlenemedi: {str(e)}")

        response.raise_for_status()

        # Handle empty response
        if not response.text:
          return {}

        # Try to parse JSON
        try:
          return response.json()
        except json.JSONDecodeError as e:
          logger.error(f"Failed to parse JSON response: {str(e)}")
          return {"error": "Invalid JSON response", "text": response.text}

      except requests.exceptions.RequestException as e:
        if attempt == MAX_RETRIES - 1:
          logger.error(
              f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
          # Return empty dict instead of raising exception
          return {"error": f"Request failed: {str(e)}"}

        logger.warning(f"Attempt {attempt + 1} failed, retrying...")
        time.sleep(RETRY_DELAY * (attempt + 1))

  def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
    return self._make_request('GET', endpoint, params=params)

  def post(self, endpoint: str, data: Dict) -> Dict:
    # Debug logging for request body
    print(
        f"[DEBUG-API] POST isteği gövdesi (JSON): {json.dumps(data, indent=2, ensure_ascii=False)}"
    )
    return self._make_request('POST', endpoint, json=data)


class TrendyolCategoryFinder:
  """Handles category discovery and attribute management"""

  def __init__(self, api_client: TrendyolAPI):
    self.api = api_client
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
      raise Exception(
          "Failed to load categories. Please check your API credentials and try again."
      )

  @lru_cache(maxsize=128)
  def get_category_attributes(self, category_id: int) -> Dict:
    """Get attributes for a specific category with caching"""
    try:
      data = self.api.get(
          f"product/product-categories/{category_id}/attributes")
      return data
    except Exception as e:
      logger.error(
          f"Failed to fetch attributes for category {category_id}: {str(e)}")
      raise Exception(f"Failed to load attributes for category {category_id}")

  def find_best_category(self, search_term: str, product_title: str = None, deep_search: bool = True, fallback: bool = True) -> int:
    """
    Find the most relevant category for a given search term using multiple strategies including OpenAI assistance
    
    The process is as follows:
    1. First try using classic matching strategies to find up to 30 potentially matching categories
    2. If OpenAI is available, use it to select the best match from these categories
    3. If OpenAI's confidence is high enough (>0.85), use its recommendation
    4. Otherwise, fall back to the traditional matching algorithm
    
    Args:
        search_term: Primary category term to search for
        product_title: Optional product title to consider for better matching (especially for 'Set & Takım' detection)
        deep_search: Whether to use advanced search strategies
        fallback: Whether to return best match if no exact match found
    """
    try:
      categories = self.category_cache
      if not categories:
        raise ValueError("Empty category list received from API")

      # Store all potential matches with their scores for the OpenAI recommendation
      potential_matches = []
      
      # Special handling for common category matches with specific terms
      if product_title:
        # Convert to lowercase for easier matching
        product_title_lower = product_title.lower().strip()
        
        # Detect "Set" or "Takım" products - look for specific patterns
        if ("2'li" in product_title_lower or "ikili" in product_title_lower or 
            "3'lü" in product_title_lower or "üçlü" in product_title_lower or
            "takım" in product_title_lower or "set" in product_title_lower):
            
            # For children products with set/takım, prioritize finding the right children set category
            if "çocuk" in product_title_lower:
                # Look for child set categories
                for cat in self._get_all_leaf_categories(categories):
                    cat_name_lower = cat['name'].lower()
                    if ("çocuk" in cat_name_lower and 
                        ("set" in cat_name_lower or "takım" in cat_name_lower)):
                        # Further specialize between boy/girl if possible
                        if "erkek" in product_title_lower and "erkek" in cat_name_lower:
                            logger.info(f"Found specialized boy set category: {cat['name']} (ID: {cat['id']})")
                            # Add to potential matches with high score
                            potential_matches.append({
                                'category': cat,
                                'score': 0.95,
                                'match_type': 'specialized_set'
                            })
                        elif "kız" in product_title_lower and "kız" in cat_name_lower:
                            logger.info(f"Found specialized girl set category: {cat['name']} (ID: {cat['id']})")
                            # Add to potential matches with high score
                            potential_matches.append({
                                'category': cat,
                                'score': 0.95,
                                'match_type': 'specialized_set'
                            })
                        # Keep as general match if no gender match found
                        logger.info(f"Found general children set category: {cat['name']} (ID: {cat['id']})")
                        # Add to potential matches with slightly lower score
                        potential_matches.append({
                            'category': cat,
                            'score': 0.9,
                            'match_type': 'general_set'
                        })
        
        # Special case for tshirt vs tisort spelling variations (common Turkish product)
        if "tişört" in product_title_lower or "t-shirt" in product_title_lower:
            search_term_with_tshirt = search_term.lower().replace("tişört", "t-shirt")
            search_term_with_tisort = search_term.lower().replace("t-shirt", "tişört")
            
            # Try both spellings when searching for categories
            for cat in self._get_all_leaf_categories(categories):
                cat_name_lower = cat['name'].lower()
                if search_term_with_tshirt in cat_name_lower or search_term_with_tisort in cat_name_lower:
                    logger.info(f"Found t-shirt/tişört category match: {cat['name']} (ID: {cat['id']})")
                    # Add to potential matches with high score
                    potential_matches.append({
                        'category': cat,
                        'score': 0.9,
                        'match_type': 'tshirt_variant'
                    })
      
      # Strategy 1: Try for exact match first (case insensitive)
      leaf_categories = self._get_all_leaf_categories(categories)
      search_term_lower = search_term.lower().strip()
      
      # Try exact match
      for cat in leaf_categories:
        cat_name_lower = cat['name'].lower()
        if search_term_lower == cat_name_lower:
          logger.info(f"Found exact match category: {cat['name']} (ID: {cat['id']})")
          # Since this is an exact match, use it directly
          return cat['id']
          
        # Collect similarity scores for all categories
        similarity = self._calculate_similarity(search_term_lower, cat_name_lower)
        
        # If we have a product title, increase score for relevant category matches
        if product_title:
            # Check how many words from the product title appear in this category
            product_words = [w for w in product_title.lower().split() if len(w) > 2]
            cat_words = cat_name_lower.split()
            
            title_match_score = 0
            matched_title_words = []
            
            # Count product title words that match this category
            for word in product_words:
                if word in cat_name_lower:
                    title_match_score += 1
                    matched_title_words.append(word)
            
            # If category has good match with product title, boost similarity
            if title_match_score > 1 or (title_match_score == 1 and len(matched_title_words) > 0 and len(matched_title_words[0]) > 4):
                # Boost by percentage of matching words (max 50% boost)
                boost_factor = min(0.5, title_match_score / len(product_words))
                adjusted_similarity = similarity * (1 + boost_factor)
                
                # Log the boosted similarity
                logger.info(f"Boosted category {cat['name']} similarity from {similarity:.2f} to {adjusted_similarity:.2f} based on product title")
                similarity = adjusted_similarity
        
        # Add to potential matches
        potential_matches.append({
            'category': cat,
            'score': similarity,
            'match_type': 'similarity'
        })
      
      # Strategy 2: Try substring match - if the search term is fully contained in category name
      for cat in leaf_categories:
        cat_name_lower = cat['name'].lower()
        if search_term_lower in cat_name_lower:
          logger.info(f"Found substring match category: {cat['name']} (ID: {cat['id']})")
          # Add to potential matches with high score
          potential_matches.append({
              'category': cat,
              'score': 0.85,
              'match_type': 'substring'
          })
      
      # Strategy 3: Try if category name is contained in search term (reverse inclusion)
      for cat in leaf_categories:
        cat_name_lower = cat['name'].lower()
        if cat_name_lower in search_term_lower and len(cat_name_lower) > 3:  # Prevent matching very short names
          logger.info(f"Found reverse inclusion match: {cat['name']} (ID: {cat['id']})")
          # Add to potential matches with slightly lower score
          potential_matches.append({
              'category': cat,
              'score': 0.8,
              'match_type': 'reverse_inclusion'
          })
      
      # Strategy 4: Try partial match - each word in search term is contained in category
      if deep_search:
        search_words = [w for w in search_term_lower.split() if len(w) > 2]  # Filter out very short words
        
        for cat in leaf_categories:
          cat_name_lower = cat['name'].lower()
          match_score = 0
          
          # Count how many words from search term appear in this category
          for word in search_words:
            if word in cat_name_lower:
              match_score += 1
          
          # Calculate what percentage of search words matched
          match_percentage = match_score / len(search_words) if search_words else 0
          
          # If we have a product title, check for significant product title words in the category name
          if product_title:
            product_words = [w for w in product_title.lower().split() if len(w) > 3]  # Only significant words
            important_words = ["erkek", "kadın", "çocuk", "kız", "bebek", "takım", "set", "tişört", "t-shirt", "pantolon", "şort"]
            
            title_match_score = 0
            for word in product_words:
                if word in cat_name_lower:
                    # Give more weight to important classifier words
                    title_match_score += 1 if word not in important_words else 2
            
            # Boost score based on product title matches
            if title_match_score > 0:
                # Add a bonus to the match percentage (scaled by the number of matches)
                match_percentage += 0.1 * title_match_score
          
          # Save this match info if it has some value
          if match_percentage > 0:
              potential_matches.append({
                  'category': cat,
                  'score': match_percentage,
                  'match_type': 'word_match',
                  'matched_words': match_score
              })
      
      # Additional strategies to collect more potential matches
      
      # Strategy 5: Try individual words but in all categories (not just leaf)
      all_categories = []
      self._collect_all_categories(categories, all_categories)
      
      # Define search_words here if not already defined
      if not 'search_words' in locals():
        search_words = [w for w in search_term_lower.split() if len(w) > 2]
        
      if deep_search and ' ' in search_term:
        for word in search_words:
          if len(word) > 3:  # Only try with meaningful words
            # Search this word in all categories (including non-leaf)
            for cat in all_categories:
              cat_name_lower = cat['name'].lower()
              if word == cat_name_lower or (len(word) > 4 and word in cat_name_lower):
                logger.info(f"Found word match in category tree: '{word}' in {cat['name']} (ID: {cat['id']})")
                # If it's a leaf category, add it to potential matches
                if not cat.get('subCategories'):
                  potential_matches.append({
                      'category': cat,
                      'score': 0.7,
                      'match_type': 'word_match_tree'
                  })
                # If not leaf, get first leaf subcategory
                else:
                  leaf = self._get_first_leaf_subcategory(cat)
                  if leaf:
                    logger.info(f"Using leaf subcategory: {leaf['name']} (ID: {leaf['id']})")
                    potential_matches.append({
                        'category': leaf,
                        'score': 0.65,
                        'match_type': 'word_match_tree_leaf'
                    })
      
      # Strategy 6: Try removing stopwords and search again to add more potential matches
      stopwords = {'ve', 'ile', 'için', 'bir', 'bu', 'da', 'de', 'den', 'dan', 'i̇çin', 'the', 'and', 'for', 'with', 'a', 'an'}
      filtered_words = [w for w in search_term_lower.split() if w not in stopwords and len(w) > 2]
      
      if len(filtered_words) > 0 and len(filtered_words) < len(search_term_lower.split()):
        filtered_term = ' '.join(filtered_words)
        if filtered_term != search_term_lower:
          logger.info(f"Trying with stopwords removed: '{filtered_term}'")
          
          # Look for matches with the filtered term
          for cat in leaf_categories:
            cat_name_lower = cat['name'].lower()
            if filtered_term in cat_name_lower or cat_name_lower in filtered_term:
              potential_matches.append({
                  'category': cat,
                  'score': 0.75,
                  'match_type': 'stopwords_removed'
              })
      
      # Strategy 7: Try with partial words for additional matches
      if deep_search and ' ' in search_term:
        words = search_term_lower.split()
        
        # Try different combinations of words
        for i in range(len(words) - 1, 0, -1):
          # Try prefix (start of term)
          prefix = ' '.join(words[:i])
          logger.info(f"Trying with prefix: '{prefix}'")
          
          # Try suffix (end of term)
          suffix = ' '.join(words[-i:])
          logger.info(f"Trying with suffix: '{suffix}'")
          
          # Add partial matches to the potential matches list
          for cat in leaf_categories:
            cat_name_lower = cat['name'].lower()
            if prefix in cat_name_lower:
              potential_matches.append({
                  'category': cat,
                  'score': 0.6,
                  'match_type': 'prefix'
              })
            if suffix in cat_name_lower:
              potential_matches.append({
                  'category': cat,
                  'score': 0.55,
                  'match_type': 'suffix'
              })
      
      # Remove duplicates in potential matches by keeping the highest score for each category
      unique_categories = {}
      for match in potential_matches:
        cat_id = match['category']['id']
        if cat_id not in unique_categories or match['score'] > unique_categories[cat_id]['score']:
          unique_categories[cat_id] = match
      
      # Convert back to list and sort by score
      unique_potential_matches = list(unique_categories.values())
      sorted_matches = sorted(unique_potential_matches, key=lambda m: m['score'], reverse=True)
      
      # Limit to top 60 potential matches as requested
      top_matches = sorted_matches[:60]
      
      # Log our top potential matches
      logger.info(f"Found {len(top_matches)} potential category matches for '{search_term}'")
      for i, match in enumerate(top_matches[:5]):  # Log top 5
        logger.info(f"  {i+1}. {match['category']['name']} (ID: {match['category']['id']}) "
                   f"with score {match['score']:.2f}, match type: {match['match_type']}")
      
      # Check if we can use OpenAI for better matching
      try:
        from trendyol.openai_helper import OpenAICategoryMatcher
        openai_matcher = OpenAICategoryMatcher()
        
        # Use OpenAI to find the best match among our top 60 potential matches
        openai_result = openai_matcher.find_best_category_match(
            search_term=search_term,
            product_title=product_title or "",
            categories=[m['category'] for m in top_matches]
        )
        
        # If OpenAI found a match with high confidence (>0.85), use it
        if openai_result and openai_result['score'] > 0.85:
          logger.info(f"Using OpenAI-recommended category: {openai_result['name']} (ID: {openai_result['id']}) "
                     f"with confidence {openai_result['score']:.2f}")
          return openai_result['id']
        elif openai_result:
          logger.info(f"OpenAI recommendation: {openai_result['name']} (ID: {openai_result['id']}) "
                     f"with confidence {openai_result['score']:.2f} (below threshold, using traditional algorithm)")
      except Exception as e:
        logger.warning(f"Error using OpenAI for category matching: {str(e)}")
      
      # If OpenAI wasn't available or confidence was too low, use our traditional approach
      # Check if we have any good matches from our earlier strategies
      if top_matches:
        best_match = top_matches[0]  # Take the highest scoring match
        logger.info(f"Using best traditional match: {best_match['category']['name']} (ID: {best_match['category']['id']}) "
                   f"with score {best_match['score']:.2f}, match type: {best_match['match_type']}")
        return best_match['category']['id']
      
      # If we still couldn't find a match, log and throw error
      logger.warning(f"No category found for '{search_term}'. Available categories at top level:")
      for i, cat in enumerate(categories[:10]):  # Log first 10 top-level categories
        logger.warning(f"  {i+1}. {cat['name']} (ID: {cat['id']})")
      
      raise ValueError(f"No matching category found for: {search_term}")

    except Exception as e:
      logger.error(f"Category search failed for '{search_term}': {str(e)}")
      raise
  
  def _calculate_similarity(self, term1: str, term2: str) -> float:
    """
    Calculate simple similarity score between two strings
    Using character overlap and length similarity
    """
    # Jaccard similarity for character sets
    set1, set2 = set(term1), set(term2)
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    char_similarity = intersection / union if union > 0 else 0
    
    # Length similarity
    max_len = max(len(term1), len(term2))
    len_diff = abs(len(term1) - len(term2))
    len_similarity = 1 - (len_diff / max_len) if max_len > 0 else 0
    
    # Combined similarity - weighted more towards character overlap
    return 0.7 * char_similarity + 0.3 * len_similarity
  
  def _collect_all_categories(self, categories: List[Dict], result: List[Dict]) -> None:
    """Collect all categories (both leaf and non-leaf)"""
    for cat in categories:
      result.append(cat)
      if cat.get('subCategories'):
        self._collect_all_categories(cat['subCategories'], result)
  
  def _get_first_leaf_subcategory(self, category: Dict) -> Optional[Dict]:
    """Get the first leaf subcategory from a category"""
    if not category.get('subCategories'):
      return category
    
    for subcat in category['subCategories']:
      if not subcat.get('subCategories'):
        return subcat
      
      # Recursively search deeper
      leaf = self._get_first_leaf_subcategory(subcat)
      if leaf:
        return leaf
    
    return None

  def _get_all_leaf_categories(self, categories: List[Dict]) -> List[Dict]:
    """Get all leaf categories (categories without children)"""
    leaf_categories = []
    self._collect_leaf_categories(categories, leaf_categories)
    return leaf_categories

  def _collect_leaf_categories(self, categories: List[Dict],
                               result: List[Dict]) -> None:
    """Recursively collect leaf categories"""
    for cat in categories:
      if not cat.get('subCategories'):
        result.append(cat)
      else:
        self._collect_leaf_categories(cat['subCategories'], result)


# Global special attribute handling
# Tanımlı özel öznitelikleri tutan global değişken
SPECIAL_ATTRIBUTES = {
    'kumaş': ['kumaş', 'fabric', 'material', 'malzeme', 'içerik', 'content'],
    'kalıp': ['kalıp', 'kesim', 'fit', 'pattern', 'form', 'tip'],
    'renk': ['renk', 'color', 'colour', 'renkli', 'rengi'],
    'cinsiyet': ['cinsiyet', 'gender', 'sex', 'cinsiyeti'],
    'yaş': ['yaş', 'age', 'yas', 'grubu', 'yaş grubu', 'aralığı', 'yaş aralığı'],
    'beden': ['beden', 'size', 'boy', 'boyut', 'ölçü', 'ebat']
}

# Ortak öznitelik değerleri - yapay zeka analizi için eşleştirme tablosu
COMMON_ATTRIBUTE_VALUES = {
    'cinsiyet': {
        'erkek': ['erkek', 'erkek çocuk', 'erkek bebek', 'male', 'boy', 'men', 'erkekler'],
        'kadın': ['kadın', 'kadın çocuk', 'kız', 'kız çocuk', 'kız bebek', 'female', 'girl', 'women'],
        'unisex': ['unisex', 'nötr', 'neutral', 'hem erkek hem kız', 'karma', 'hepsi']
    },
    'yaş': {
        'bebek': ['bebek', 'baby', 'infant', '0-24 ay', '0-2 yaş', 'yeni doğan', 'newborn'],
        'çocuk': ['çocuk', 'child', 'kid', '2-14 yaş', 'okul çağı', 'ilkokul', 'ortaokul'],
        'yetişkin': ['yetişkin', 'adult', 'grown-up', 'büyük', '18+ yaş'],
        'genç': ['genç', 'teen', 'teenager', 'youth', 'adolescent', 'lise']
    }
}

class TrendyolProductManager:
  """Handles product creation and management"""

  def __init__(self, api_client: TrendyolAPI):
    self.api = api_client
    self.category_finder = TrendyolCategoryFinder(api_client)
    
  def _extract_structured_info_from_description(self, product_description: str) -> Dict[str, str]:
    """
    Extract structured key-value information from product descriptions.
    
    This function looks for structured patterns like:
    - Key: Value
    - Key - Value
    - Key = Value
    - Key (Value)
    - And other common patterns in product descriptions
    
    Returns a dictionary of extracted attribute keys and values.
    """
    if not product_description:
        return {}
        
    # Initialize result dictionary
    result = {}
    
    # Clean and normalize description
    desc = product_description.lower()
    # Remove HTML tags
    desc = re.sub(r'<[^>]+>', ' ', desc)
    
    # Extract key-value pairs with different patterns
    # Pattern 1: Key: Value
    kv_pairs = re.findall(r'(\w+[\w\s]*?):\s*([\w\s\-\.\,\%]+?)(?:\n|<br>|$|,\s*\w+:)', desc)
    for key, value in kv_pairs:
        key = key.strip()
        value = value.strip()
        if key and value and len(key) > 2 and len(value) > 1:
            result[key] = value
            
    # Pattern 2: Key = Value
    kv_pairs = re.findall(r'(\w+[\w\s]*?)\s*=\s*([\w\s\-\.\,\%]+?)(?:\n|<br>|$|,\s*\w+\s*=)', desc)
    for key, value in kv_pairs:
        key = key.strip()
        value = value.strip()
        if key and value and len(key) > 2 and len(value) > 1:
            result[key] = value
    
    # Pattern 3: Key - Value
    kv_pairs = re.findall(r'(\w+[\w\s]*?)\s*-\s*([\w\s\-\.\,\%]+?)(?:\n|<br>|$|,\s*\w+\s*-)', desc)
    for key, value in kv_pairs:
        key = key.strip()
        value = value.strip()
        if key and value and len(key) > 2 and len(value) > 1:
            result[key] = value
    
    # Look for color-related information specifically
    colors = re.findall(r'renk\s*[:-]?\s*([\w\s]+?)(?:\n|<br>|$|,)', desc)
    if colors:
        result['renk'] = colors[0].strip()
    
    # Look for material-related information
    materials = re.findall(r'(?:kumaş|materyal|malzeme)\s*[:-]?\s*([\w\s\%]+?)(?:\n|<br>|$|,)', desc)
    if materials:
        result['malzeme'] = materials[0].strip()
    
    # Look for patterns like "100% Pamuk" or "60% Polyester"
    fabric_pcts = re.findall(r'(\d+)[%\s]+([\w]+)', desc)
    fabric_composition = []
    for pct, fabric in fabric_pcts:
        if fabric.strip() in ['pamuk', 'polyester', 'elastan', 'viskon', 'keten', 'yün', 'akrilik', 'polyamid']:
            fabric_composition.append(f"{pct}% {fabric.strip().capitalize()}")
    
    if fabric_composition:
        result['kumaş'] = ', '.join(fabric_composition)
    
    # Look for gender information
    gender_terms = {
        'erkek': ['erkek', 'erkekler için', 'erkek giyim'],
        'kadın': ['kadın', 'kadınlar için', 'kadın giyim', 'bayan'],
        'unisex': ['unisex', 'her ikisi için'],
        'kız çocuk': ['kız çocuk', 'kız çocukları için'],
        'erkek çocuk': ['erkek çocuk', 'erkek çocukları için'],
        'bebek': ['bebek', 'bebek ürünü', 'bebekler için']
    }
    
    for gender, terms in gender_terms.items():
        if any(term in desc for term in terms):
            result['cinsiyet'] = gender
            break
    
    # Special parsing for product type/model
    if 'set' in desc or 'takım' in desc:
        result['model'] = 'Set Takım'
        
    if 'tişört' in desc:
        result['ürün'] = 'Tişört'
    elif 'pantolon' in desc:
        result['ürün'] = 'Pantolon'
    elif 'gömlek' in desc:
        result['ürün'] = 'Gömlek'
    elif 'elbise' in desc:
        result['ürün'] = 'Elbise'
    elif 'ceket' in desc:
        result['ürün'] = 'Ceket'
    elif 'ayakkabı' in desc:
        result['ürün'] = 'Ayakkabı'
    
    # Print debug info
    if result:
        print(f"[DEBUG-API] Açıklamadan çıkarılan yapılandırılmış bilgiler: {json.dumps(result, ensure_ascii=False)}")
    
    return result

  def get_brand_id(self, brand_name: str) -> int:
    """Find brand ID by name"""
    encoded_name = quote(brand_name)
    try:
      brands = self.api.get(f"product/brands/by-name?name={encoded_name}")
      if isinstance(brands, list) and brands:
        return brands[0]['id']
      # If LC Waikiki not found, use default ID 7651
      if 'LCW' in brand_name or 'LC Waikiki' in brand_name:
        logger.warning(
            f"Brand not found: {brand_name}, using default LC Waikiki ID: 7651"
        )
        return 7651

      raise ValueError(f"Brand not found: {brand_name}")
    except Exception as e:
      logger.error(f"Brand search failed for '{brand_name}': {str(e)}")
      raise

  def create_product(self, product_data: ProductData) -> str:
    """Create a new product on Trendyol"""
    try:
      category_id = self.category_finder.find_best_category(
          product_data.category_name, product_title=product_data.title)
      brand_id = self.get_brand_id(product_data.brand_name)
      
      # İlk önce boş öznitelik listesi ile göndermeyi deneyelim
      # Try sending with empty attributes list first to see which ones are actually required
      initial_attributes = []
      
      logger.info("Submitting product with empty attributes to discover required attributes...")
      payload = self._build_product_payload(product_data, category_id,
                                            brand_id, initial_attributes)
      
      logger.info("Submitting product creation request...")
      response = self.api.post(
          f"product/sellers/{self.api.config.seller_id}/products", payload)
      
      batch_id = response.get('batchRequestId')
      
      if batch_id:
          # Log the batch ID for reference
          logger.info(f"Product submitted with batch ID: {batch_id}")
          print(f"[DEBUG-API] Ürün boş özniteliklerle gönderildi. Batch ID: {batch_id}")
          print(f"[DEBUG-API] Batch durumunu kontrol etmek için: {batch_id}")
      
      return batch_id
    except Exception as e:
      logger.error(f"Product creation failed: {str(e)}")
      raise

  def check_batch_status(self, batch_id: str) -> Dict:
    """Check the status of a batch operation"""
    try:
      response = self.api.get(
          f"product/sellers/{self.api.config.seller_id}/products/batch-requests/{batch_id}"
      )
      
      # Log detailed status info for debugging
      status = response.get('status', 'UNKNOWN')
      items = response.get('items', [])
      print(f"[DEBUG-API] Batch {batch_id} durumu: {status}")
      
      if items:
          for idx, item in enumerate(items):
              item_status = item.get('status')
              failure_reasons = item.get('failureReasons', [])
              if item_status == 'FAILED' and failure_reasons:
                  print(f"[DEBUG-API] Ürün {idx+1} hata nedenleri:")
                  for reason in failure_reasons:
                      print(f"[DEBUG-API]   - {reason}")
      
      return response
    except Exception as e:
      logger.error(f"Failed to check batch status: {str(e)}")
      raise
      
  def get_required_attributes_from_error(self, batch_id: str) -> List[str]:
    """
    Batch ID'den gelen hata mesajlarını analiz ederek gerekli öznitelikleri belirler
    
    Örnek hata mesajı: "Zorunlu kategori özellik bilgisi eksiktir. Eksik alan: Boy"
    """
    try:
        # Batch durumunu kontrol et
        batch_status = self.check_batch_status(batch_id)
        items = batch_status.get('items', [])
        
        # Gerekli öznitelik isimlerini topla
        required_attributes = []
        
        for item in items:
            failure_reasons = item.get('failureReasons', [])
            
            for reason in failure_reasons:
                # Eksik öznitelik hatalarını ara
                match = re.search(r'Zorunlu kategori özellik bilgisi eksiktir\. Eksik alan: (.+)$', reason)
                if match:
                    attr_name = match.group(1).strip()
                    if attr_name not in required_attributes:
                        required_attributes.append(attr_name)
                        print(f"[DEBUG-API] Tespit edilen zorunlu öznitelik: {attr_name}")
        
        return required_attributes
    except Exception as e:
        logger.error(f"Error analyzing batch errors: {str(e)}")
        print(f"[DEBUG-API] Batch hata analizi hatası: {str(e)}")
        return []

  def _build_product_payload(self, product: ProductData, category_id: int,
                             brand_id: int, attributes: List[Dict]) -> Dict:
    """Construct the complete product payload"""
    return {
        "items": [{
            "barcode": product.barcode,
            "title": product.title,
            "productMainId": product.product_main_id,
            "brandId": brand_id,
            "categoryId": category_id,
            "quantity": product.quantity,
            "stockCode": product.stock_code,
            "dimensionalWeight": product.dimensional_weight,
            "description": product.description,
            "currencyType": product.currency_type,
            "listPrice": product.price,
            "salePrice": product.sale_price,
            "vatRate": product.vat_rate,
            # "cargoCompanyId": product.cargo_company_id,
            "images": [{
                "url": product.image_url
            }],
            "attributes": attributes
        }]
    }

  def _get_attributes_for_category(self, category_id: int, product_description: str = None, product_title: str = None) -> List[Dict]:
    """
    Generate attributes for a category based on API data, product title and description.
    
    This function uses advanced pattern matching as well as OpenAI GPT-4o AI
    to select the most accurate attribute values from the available options.
    """
    attributes = []
    try:
      category_attrs = self.category_finder.get_category_attributes(
          category_id)

      # Debug log the full category attributes
      print(
          f"[DEBUG-API] Kategori {category_id} için özellikler: {json.dumps(category_attrs, indent=2, ensure_ascii=False)[:1000]}..."
      )

      # Look specifically for color attribute as it's often required
      color_attr = None
      required_attrs = []
      
      # Extract structured information from description
      # Extract key-value pairs from the product description 
      desc_info = {}
      if product_description:
          # Extract structured information from product description
          desc_info = self._extract_structured_info_from_description(product_description)
      
      # Extract description keywords - create a normalized version for matching
      # This will be used to try to match attribute values from the description
      desc_keywords = []
      desc_phrases = []
      if product_description:
        # Clean and normalize the description
        clean_desc = product_description.lower()
        # Remove common HTML tags
        clean_desc = re.sub(r'<[^>]+>', ' ', clean_desc)
        # Extract all potential keywords for single-word matching
        desc_keywords = [w.strip() for w in re.findall(r'\b\w+\b', clean_desc) if len(w.strip()) > 2]
        
        # Extract phrases (2-3 consecutive words) for better matching
        words = [w.strip() for w in re.findall(r'\b\w+\b', clean_desc) if len(w.strip()) > 1]
        for i in range(len(words)-1):
            desc_phrases.append(f"{words[i]} {words[i+1]}")
        for i in range(len(words)-2):
            desc_phrases.append(f"{words[i]} {words[i+1]} {words[i+2]}")
        
        print(f"[DEBUG-API] Açıklamadan çıkarılan anahtar kelimeler: {', '.join(desc_keywords[:20])}...")
        print(f"[DEBUG-API] Açıklamadan çıkarılan anahtar ifadeler: {', '.join(desc_phrases[:10])}...")

      # First pass - identify required attributes
      for attr in category_attrs.get('categoryAttributes', []):
        attr_name = attr['attribute']['name']
        attr_id = attr['attribute']['id']
        is_required = attr.get('required', False)

        if is_required:
          required_attrs.append(f"{attr_name} (ID: {attr_id})")

        # Check if this is a color attribute (important for Trendyol)
        if attr_name.lower() in ['renk', 'color', 'colour']:
          color_attr = attr
          print(
              f"[DEBUG-API] Renk özelliği bulundu: {attr_name} (ID: {attr_id})"
          )

      # Log required attributes
      if required_attrs:
        print(f"[DEBUG-API] Zorunlu özellikler: {', '.join(required_attrs)}")

      # Process only first 8 attributes
      attr_count = 0
      for attr in category_attrs.get('categoryAttributes', []):
        # Only process the first 8 attributes as requested
        if attr_count >= 8:
          print(f"[DEBUG-API] Sadece ilk 8 öznitelik işleniyor, kalan {len(category_attrs.get('categoryAttributes', [])) - 8} öznitelik atlandı.")
          break
        attr_count += 1
        # Skip if no attribute values and custom values not allowed
        if not attr.get('attributeValues') and not attr.get('allowCustom'):
          continue

        attribute = {
            "attributeId": attr['attribute']['id'],
            "attributeName": attr['attribute']['name']
        }
        
        # Try to find a matching attribute value from the structured data or description
        matched_value = None
        attr_name_lower = attr['attribute']['name'].lower()
        
        # Özel işleme - Kumaş ve Kalıp için "Belirtilmemiş" değeri seçme
        # Check if this is a fabric (kumaş) or pattern/fit (kalıp) attribute
        is_fabric_attribute = any(keyword in attr_name_lower for keyword in SPECIAL_ATTRIBUTES['kumaş'])
        is_pattern_attribute = any(keyword in attr_name_lower for keyword in SPECIAL_ATTRIBUTES['kalıp'])
        
        # If this is a special attribute, look for "Belirtilmemiş" or similar option
        if is_fabric_attribute or is_pattern_attribute:
            if attr.get('attributeValues'):
                for val in attr['attributeValues']:
                    # Look for "Belirtilmemiş" or similar option
                    if val['name'].lower() in ['belirtilmemiş', 'belirtilmemis', 'bilinmiyor', 'other', 'diğer']:
                        matched_value = val
                        print(f"[DEBUG-API] Özel işleme: {attr['attribute']['name']} için 'Belirtilmemiş' değeri seçildi (ID: {val['id']})")
                        break
        
        # First check the structured data extracted from the description
        if desc_info:
            # Try to match attribute name with extracted keys
            for key, value in desc_info.items():
                # Check if any key in the extracted info matches this attribute
                if (key.lower() == attr_name_lower or 
                    (len(key) > 3 and key.lower() in attr_name_lower) or 
                    (len(attr_name_lower) > 3 and attr_name_lower in key.lower())):
                    
                    # Found a matching key, now see if the value matches any attribute value
                    if attr.get('attributeValues'):
                        for val in attr['attributeValues']:
                            val_name = val['name'].lower()
                            extracted_value = value.lower()
                            
                            # Check direct value match
                            if (val_name == extracted_value or 
                                (len(val_name) > 3 and val_name in extracted_value) or 
                                (len(extracted_value) > 3 and extracted_value in val_name)):
                                
                                matched_value = val
                                print(f"[DEBUG-API] Yapılandırılmış veri eşleşmesi: {attr['attribute']['name']} = {val['name']} (anahtar: {key})")
                                break
                    
                    # If custom values allowed, use extracted value directly
                    if not matched_value and attr.get('allowCustom'):
                        attribute["customAttributeValue"] = value
                        print(f"[DEBUG-API] Özel öznitelik kullanıldı: {attr['attribute']['name']} = {value}")
                        # Skip the rest of the matching
                        break
        
        # If no match in structured data and we have attribute values, try full description
        if not matched_value and attr.get('attributeValues') and product_description:
          attr_values = attr['attributeValues']
          
          # Sort attribute values by name length (descending) to prefer more specific matches
          attr_values_sorted = sorted(attr_values, key=lambda v: len(v['name']), reverse=True)
          
          # First try exact match in the description
          for val in attr_values_sorted:
            val_name = val['name'].lower()
            if val_name in product_description.lower():
              matched_value = val
              print(f"[DEBUG-API] Açıklamada tam eşleşme bulundu: {attr['attribute']['name']} = {val['name']}")
              break
          
          # Next try match in the extracted phrases (for better context)
          if not matched_value and desc_phrases:
            for val in attr_values_sorted:
              val_name = val['name'].lower()
              
              # Check if any phrase contains this value name
              matching_phrases = [phrase for phrase in desc_phrases if val_name in phrase]
              if matching_phrases:
                matched_value = val
                print(f"[DEBUG-API] İfade eşleşmesi bulundu: {attr['attribute']['name']} = {val['name']} (ifade: {matching_phrases[0]})")
                break
          
          # If still no match, try word matches from our keywords
          if not matched_value and desc_keywords:
            for val in attr_values_sorted:
              val_name = val['name'].lower()
              val_words = re.findall(r'\b\w+\b', val_name)
              
              # Calculate match score based on how many words match
              match_score = 0
              matched_words = []
              
              for word in val_words:
                if len(word) > 3 and word.lower() in desc_keywords:
                  match_score += 1
                  matched_words.append(word)
              
              # If we found matches that cover at least 50% of the attribute value words
              if match_score > 0 and match_score >= max(1, 0.5 * len(val_words)):
                matched_value = val
                print(f"[DEBUG-API] Açıklamada kelime eşleşmesi bulundu: {attr['attribute']['name']} = {val['name']} (kelimeler: {', '.join(matched_words)})")
                break
        
        # Special handling for Model/Type attributes - check for Set/Takım patterns
        if attr['attribute']['name'].lower() in ['model', 'model tip', 'tip', 'tür', 'type'] and not matched_value:
          if product_description:
            # Look for set/takım related terms in the product description
            set_terms = ["set", "takım", "2'li", "3'lü", "ikili", "üçlü", "takımı"]
            desc_lower = product_description.lower()
            
            # Check if any set term is in the description
            if any(term in desc_lower for term in set_terms):
              # Find an attribute value that matches set/takım
              for val in attr['attributeValues']:
                val_name = val['name'].lower()
                if any(term in val_name for term in ["set", "takım"]):
                  matched_value = val
                  print(f"[DEBUG-API] Set/Takım özel eşleştirmesi: {attr['attribute']['name']} = {val['name']}")
                  break
        
        # Use the matched value if found, otherwise use the first available value
        if matched_value:
          attribute["attributeValueId"] = matched_value['id']
          attribute["attributeValue"] = matched_value['name']
        elif attr.get('attributeValues') and len(attr['attributeValues']) > 0:
          if not attr['allowCustom']:
            attribute["attributeValueId"] = attr['attributeValues'][0]['id']
            attribute["attributeValue"] = attr['attributeValues'][0]['name']
          else:
            attribute["customAttributeValue"] = f"Sample {attr['attribute']['name']}"
        elif attr.get('allowCustom'):
          attribute["customAttributeValue"] = f"Sample {attr['attribute']['name']}"
        else:
          continue

        attributes.append(attribute)

      # Add special handling for color if it's required but not found
      if color_attr and not any(
          a.get('attributeName', '').lower() in ['renk', 'color', 'colour']
          for a in attributes):
        print(
            "[DEBUG-API] Renk özelliği zorunlu fakat eklenmemiş. Manuel olarak ekleniyor."
        )
        color_attribute = {
            "attributeId": color_attr['attribute']['id'],
            "attributeName": color_attr['attribute']['name']
        }

        # Try to find color in the structured information from description first
        color_found = False
        if desc_info and 'renk' in desc_info and color_attr.get('attributeValues'):
            color_values = color_attr['attributeValues']
            color_value_from_desc = desc_info['renk'].lower()
            
            # Look for a direct match with the extracted color value
            for color_val in color_values:
                color_name = color_val['name'].lower()
                
                # Check if color names match or are contained within each other
                if (color_name == color_value_from_desc or 
                    (len(color_name) > 3 and color_name in color_value_from_desc) or 
                    (len(color_value_from_desc) > 3 and color_value_from_desc in color_name)):
                    
                    color_attribute["attributeValueId"] = color_val['id']
                    color_attribute["attributeValue"] = color_val['name']
                    print(f"[DEBUG-API] Yapılandırılmış veri renk eşleşmesi: {color_val['name']} (çıkarılan: {color_value_from_desc})")
                    color_found = True
                    break
        
        # If color not found in structured info, try to find color in the product description
        if not color_found and product_description and color_attr.get('attributeValues'):
          color_values = color_attr['attributeValues']
          # Sort by name length (descending) to match more specific colors first
          color_values_sorted = sorted(color_values, key=lambda v: len(v['name']), reverse=True)
          
          # First try exact color match
          for color_val in color_values_sorted:
            color_name = color_val['name'].lower()
            if color_name in product_description.lower():
              color_attribute["attributeValueId"] = color_val['id']
              color_attribute["attributeValue"] = color_val['name']
              print(f"[DEBUG-API] Açıklamada tam renk eşleşmesi bulundu: {color_val['name']}")
              color_found = True
              break
          
          # Next try match in the extracted phrases (for better context)
          if not color_found and desc_phrases:
            for color_val in color_values_sorted:
              color_name = color_val['name'].lower()
              
              # Check if any phrase contains this color name
              matching_phrases = [phrase for phrase in desc_phrases if color_name in phrase]
              if matching_phrases:
                color_attribute["attributeValueId"] = color_val['id']
                color_attribute["attributeValue"] = color_val['name']
                print(f"[DEBUG-API] İfade eşleşmesi ile renk bulundu: {color_val['name']} (ifade: {matching_phrases[0]})")
                color_found = True
                break
              
          # If exact match not found, try word-by-word matching
          if not color_found and desc_keywords:
            best_match = None
            best_match_score = 0
            
            for color_val in color_values_sorted:
              color_name = color_val['name'].lower()
              color_words = [w for w in re.findall(r'\b\w+\b', color_name) if len(w) > 2]
              
              # Calculate match score
              match_score = 0
              for word in color_words:
                if word in desc_keywords:
                  match_score += 1
              
              # If this is the best match so far, save it
              if match_score > 0 and match_score > best_match_score:
                best_match = color_val
                best_match_score = match_score
            
            # Use the best match if found
            if best_match:
              color_attribute["attributeValueId"] = best_match['id']
              color_attribute["attributeValue"] = best_match['name']
              print(f"[DEBUG-API] Açıklamada kelime-bazlı renk eşleşmesi bulundu: {best_match['name']} (skor: {best_match_score})")
              color_found = True
        
        # If no color found in description, use first available
        if not color_attribute.get("attributeValueId") and color_attr.get('attributeValues') and len(
            color_attr['attributeValues']) > 0:
          color_attribute["attributeValueId"] = color_attr['attributeValues'][0]['id']
          color_attribute["attributeValue"] = color_attr['attributeValues'][0]['name']
        elif not color_attribute.get("attributeValueId"):
          color_attribute["customAttributeValue"] = "Karışık Renkli"

        attributes.append(color_attribute)

      # Try to improve attributes with GPT-4o AI if available
      try:
        from trendyol.openai_helper import OpenAIAttributeMatcher
        openai_matcher = OpenAIAttributeMatcher()
        
        if openai_matcher.is_available() and product_title and product_description:
          print("[DEBUG-API] OpenAI attribute matcher aktif, GPT-4o ile öznitelik eşleştirme yapılıyor...")
          
          # İlk önce kategori özniteliklerini belirle
          print(f"[DEBUG-API] Kategori öznitelikleri (toplam: {len(category_attrs.get('categoryAttributes', []))})")
          required_attr_names = []
          for attr in category_attrs.get('categoryAttributes', []):
              if attr.get('required', False):
                  attr_name = attr.get('attribute', {}).get('name', '')
                  required_attr_names.append(attr_name)
          
          print(f"[DEBUG-API] Zorunlu öznitelikler: {', '.join(required_attr_names)}")
          
          # Ürün açıklamasındaki yapılandırılmış verileri çıkar
          structured_info = {}
          if product_description:
              structured_info = self._extract_structured_info_from_description(product_description)
              if structured_info:
                  print(f"[DEBUG-API] Açıklamadan çıkarılan yapılandırılmış bilgiler:")
                  for key, value in structured_info.items():
                      print(f"[DEBUG-API]   - {key}: {value}")
          
          # Use OpenAI to find the best attribute matches based on title and description
          # Use only the first 8 attributes
          category_attributes = category_attrs.get('categoryAttributes', [])
          if len(category_attributes) > 8:
              print(f"[DEBUG-API] Sadece ilk 8 öznitelik OpenAI'ye gönderiliyor, kalan {len(category_attributes) - 8} öznitelik atlandı.")
              category_attributes = category_attributes[:8]
              
          openai_attributes = openai_matcher.match_attributes(
              product_title=product_title,
              product_description=product_description,
              category_attributes=category_attributes
          )
          
          if openai_attributes:
            # Replace existing attributes with those returned by OpenAI
            # but preserve any that OpenAI didn't handle
            
            # Create a dictionary of attributes by ID for easy lookup
            attributes_by_id = {a.get("attributeId"): a for a in attributes}
            
            # Add all attributes from OpenAI
            for openai_attr in openai_attributes:
              attr_id = openai_attr.get("attributeId")
              if attr_id:
                # Remove the existing attribute if present
                if attr_id in attributes_by_id:
                  attributes.remove(attributes_by_id[attr_id])
                  
                # Add the OpenAI attribute
                attributes.append(openai_attr)
                attr_name = openai_attr.get('attributeName', '')
                attr_value = openai_attr.get('attributeValue', '') or openai_attr.get('customAttributeValue', '')
                print(f"[DEBUG-API] OpenAI attribute eşleştirme: {attr_name} = {attr_value}")
            
            print(f"[DEBUG-API] OpenAI ile {len(openai_attributes)} öznitelik eşleştirildi.")
      except Exception as e:
        logger.warning(f"OpenAI attribute matching failed: {str(e)}. Using traditional matching instead.")
        print(f"[DEBUG-API] OpenAI öznitelik eşleştirme başarısız: {str(e)}. Geleneksel yöntem kullanılıyor.")
      
      # Debug log the final attributes
      print(
          f"[DEBUG-API] Oluşturulan özellikler: {json.dumps(attributes, indent=2, ensure_ascii=False)}"
      )

      return attributes
    except Exception as e:
      logger.error(
          f"Failed to get attributes for category {category_id}: {str(e)}")
      print(f"[DEBUG-API] Kategori özellikleri alınırken hata: {str(e)}")
      # Throw error to prevent using fallback attributes, as per requirement
      raise


def get_api_config_from_db() -> APIConfig:
  """Get API configuration from database"""
  config = TrendyolAPIConfig.objects.filter(is_active=True).first()
  if not config:
    raise ValueError("No active Trendyol API configuration found")

  return APIConfig(api_key=config.api_key,
                   seller_id=config.seller_id,
                   base_url=config.base_url)


def get_api_client() -> TrendyolAPI:
  """Get a TrendyolAPI client instance"""
  config = get_api_config_from_db()
  return TrendyolAPI(config)


def get_product_manager() -> TrendyolProductManager:
  """Get a TrendyolProductManager instance"""
  api_client = get_api_client()
  return TrendyolProductManager(api_client)


def lcwaikiki_to_trendyol_product(lcw_product, variant_data=None) -> Optional[TrendyolProduct]:
  """
    Convert an LCWaikiki product to a Trendyol product.
    Returns the created or updated Trendyol product instance.
    
    Args:
        lcw_product: The LCWaikiki product to convert
        variant_data: Optional dictionary with variant-specific data (size, stock quantity)
            Example: {'size': 'M', 'stock': 10}
    
    This version ensures we fetch all required data from API and throws
    errors if data isn't available.
    """
  # Process variant data if provided
  is_variant = False
  variant_size = None
  variant_stock = None
  
  if variant_data:
      is_variant = True
      variant_size = variant_data.get('size')
      variant_stock = variant_data.get('stock')
      logger.info(f"Processing variant: Size={variant_size}, Stock={variant_stock}")
  if not lcw_product:
    return None

  try:
    # We already set these variables above - no need to set them again
    # is_variant = variant_data is not None
    # variant_size = variant_data.get('size') if is_variant else None
    # variant_stock = variant_data.get('stock') if is_variant else None
    
    # For variants, look for an existing variant with the same size
    if is_variant:
      trendyol_product = TrendyolProduct.objects.filter(
          lcwaikiki_product=lcw_product,
          variant_key=variant_size).first()
    else:
      # For main product, just look for any existing product
      trendyol_product = TrendyolProduct.objects.filter(
          lcwaikiki_product=lcw_product).first()

    # Keep product code as is, including any hyphens or spaces
    product_code = lcw_product.product_code
    if not product_code:
      # If no product code, create a fallback
      product_code = f"LCW{lcw_product.id}"
      
    # Create a global counter for MUSTAFA pattern if it doesn't exist
    # Using global variables to avoid function attribute issues
    global _product_counter
    if '_product_counter' not in globals():
        global _product_counter
        _product_counter = 0
      
    # Generate a unique barcode with MUSTAFA pattern
    # Every 7 products will start with M, U, S, T, A, F, A respectively
    mustafa_letters = ['M', 'U', 'S', 'T', 'A', 'F', 'A']
    letter_index = _product_counter % 7
    first_letter = mustafa_letters[letter_index]
    
    # Increment the counter for next product
    _product_counter += 1
    
    # Generate random alphanumeric string (12 chars) for the rest of the barcode
    import random
    import string
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    
    # Create the barcode with the pattern
    barcode = f"{first_letter}{random_chars}"
    
    # Ensure barcode is alphanumeric and meets Trendyol requirements
    barcode = re.sub(r'[^a-zA-Z0-9]', '', barcode)
    # Cap length to avoid potential issues with very long barcodes
    barcode = barcode[:32]

    # Get the price with proper discount handling
    price = lcw_product.price or Decimal('0.00')
    if lcw_product.discount_ratio and lcw_product.discount_ratio > 0:
      # Apply discount if available
      discount = (price * lcw_product.discount_ratio) / 100
      sale_price = price - discount
    else:
      sale_price = price

    # Get product images from the images field (JSONField that contains a list of image URLs)
    images = []
    if hasattr(lcw_product, 'images') and lcw_product.images:
      # If it's already a list, use it directly
      if isinstance(lcw_product.images, list):
        images = lcw_product.images
      # If it's a string (serialized JSON), parse it
      elif isinstance(lcw_product.images, str):
        try:
          img_data = json.loads(lcw_product.images)
          if isinstance(img_data, list):
            images = img_data
        except Exception as e:
          logger.warning(
              f"Failed to parse images for product {lcw_product.id}: {str(e)}")
      # Handle case when the images field contains a dictionary with image URLs
      elif isinstance(lcw_product.images,
                      dict) and 'urls' in lcw_product.images:
        img_urls = lcw_product.images.get('urls', [])
        if isinstance(img_urls, list):
          images = img_urls

    # Use first image as primary if available
    if not images and hasattr(lcw_product, 'url'):
      # If no images found but we have the product URL, use a default image or placeholder
      logger.warning(
          f"No images found for product {lcw_product.id}, using placeholder")
      images = [lcw_product.url]  # Use product URL as a reference

    # Ensure all image URLs are properly formatted
    for i in range(len(images)):
      img = images[i]
      if img.startswith('//'):
        images[i] = f"https:{img}"
      elif not img.startswith('http'):
        images[i] = f"https://{img}"

    # If no images found, throw an error as per requirement
    if not images:
      raise ValueError(f"No valid images found for product {lcw_product.id}")

    # Get quantity from product or use specific variant quantity if provided
    quantity = 0
    
    # If variant data is provided with stock information, use that
    if is_variant and variant_stock is not None:
        quantity = variant_stock
        logger.info(f"Using variant-specific stock quantity: {quantity} for size {variant_size}")
    # Otherwise get stock from the product
    elif hasattr(lcw_product, 'get_total_stock'):
      try:
        stock = lcw_product.get_total_stock()
        if stock and stock > 0:
          quantity = stock
      except Exception as e:
        logger.warning(
            f"Error getting total stock for product {lcw_product.id}: {str(e)}"
        )

    # If quantity is 0, throw an error as per requirement
    if quantity == 0:
      raise ValueError(f"Zero stock quantity for product {lcw_product.id}")

    # Get API client for next operations
    api_client = get_api_client()
    product_manager = TrendyolProductManager(api_client)

    # Find the appropriate brand ID in the Trendyol system
    brand_id = None
    try:
      # Try to get LC Waikiki brand ID from API
      brand_id = product_manager.get_brand_id("LC Waikiki")
      logger.info(f"Found brand ID: {brand_id}")
    except Exception as e:
      # If API fails, try to get from database
      lcw_brand = TrendyolBrand.objects.filter(name__icontains="LCW",
                                               is_active=True).first()
      if lcw_brand:
        brand_id = lcw_brand.brand_id
        logger.info(
            f"Found brand from database: {lcw_brand.name} (ID: {brand_id})")
      else:
        # Use default LC Waikiki ID
        brand_id = 7651
        logger.warning(f"Using default LC Waikiki brand ID: {brand_id}")

    # Find category information
    category_id = None
    category_name = lcw_product.category or ""

    # If product already has a category, use it
    if trendyol_product and trendyol_product.category_id:
      category_id = trendyol_product.category_id
    else:
      # Try to find category from API
      try:
        if category_name:
          # Use both category name and product title for better matching
          category_id = product_manager.category_finder.find_best_category(
              category_name, product_title=lcw_product.title)
          logger.info(f"Found category ID: {category_id} for '{category_name}' (Product: '{lcw_product.title}')")
      except Exception as e:
        logger.error(
            f"Error finding category for product {lcw_product.id}: {str(e)}")
        # If category finding fails, throw error as per requirement
        raise ValueError(
            f"Could not find appropriate category for product: {category_name}"
        )

    # Create or update Trendyol product
    if not trendyol_product:
      # Create a new Trendyol product
      # If this is a variant, adjust the title to include the size
      title = lcw_product.title or "LC Waikiki Product"
      if is_variant and variant_size:
          # Add size to the title if not already present
          if variant_size not in title:
              title = f"{title} - {variant_size}"
              
      trendyol_product = TrendyolProduct.objects.create(
          title=title,
          description=lcw_product.description or title or "LC Waikiki Product Description",
          barcode=barcode,
          product_main_id=product_code or barcode,
          stock_code=product_code or barcode,
          brand_name="LCW",
          brand_id=brand_id,
          category_name=category_name,
          category_id=category_id,
          pim_category_id=category_id,  # Use same as category_id initially
          price=price,
          quantity=quantity,
          image_url=images[0],
          additional_images=images[1:] if len(images) > 1 else [],
          attributes=[],  # We'll fetch from API when sending to Trendyol
          lcwaikiki_product=lcw_product,
          variant_key=variant_size,  # Store the variant key (size)
          batch_status='pending',
          status_message="Created from LCWaikiki product",
          currency_type="TRY",  # Turkish Lira
          vat_rate=10  # Default VAT rate in Turkey
      )
      logger.info(
          f"Created new Trendyol product from LCW product {lcw_product.id} with barcode {barcode}"
      )
    else:
      # Update existing Trendyol product with latest LCWaikiki data
      # Update title including the variant
      title = lcw_product.title or trendyol_product.title or "LC Waikiki Product"
      if is_variant and variant_size and variant_size not in title:
          title = f"{title} - {variant_size}"
      
      trendyol_product.title = title
      trendyol_product.description = lcw_product.description or title or trendyol_product.description or "LC Waikiki Product Description"
      trendyol_product.price = price
      trendyol_product.quantity = quantity
      trendyol_product.brand_id = brand_id or trendyol_product.brand_id
      trendyol_product.category_id = category_id or trendyol_product.category_id
      trendyol_product.pim_category_id = category_id or trendyol_product.pim_category_id
      
      # Update variant_key if necessary
      if is_variant and variant_size:
          trendyol_product.variant_key = variant_size

      # We'll fetch attributes from API when sending to Trendyol
      if not trendyol_product.attributes:
        trendyol_product.attributes = []

      # Only update barcode if it's not already been used with Trendyol
      if not trendyol_product.trendyol_id and not trendyol_product.batch_status == 'completed':
        trendyol_product.barcode = barcode
        trendyol_product.product_main_id = product_code or barcode
        trendyol_product.stock_code = product_code or barcode

      # Update images if available
      if images:
        trendyol_product.image_url = images[0]
        trendyol_product.additional_images = images[1:] if len(
            images) > 1 else []

      trendyol_product.save()
      logger.info(
          f"Updated Trendyol product {trendyol_product.id} from LCW product {lcw_product.id}"
      )

    return trendyol_product
  except Exception as e:
    logger.error(
        f"Error converting LCWaikiki product to Trendyol product: {str(e)}")
    logger.exception(e)  # Log full traceback for debugging
    raise  # Re-raise the exception as per requirement


def prepare_product_for_trendyol(trendyol_product: TrendyolProduct) -> Dict:
  """
    Prepare a Trendyol product for submission to the API.
    This includes fetching required attributes from the API.
    
    Returns a payload dictionary ready for submission to Trendyol API.
    Raises exceptions if required data is missing.
    """
  if not trendyol_product:
    raise ValueError("No product provided")

  if not trendyol_product.category_id:
    raise ValueError(f"Product {trendyol_product.id} has no category ID")

  if not trendyol_product.brand_id:
    raise ValueError(f"Product {trendyol_product.id} has no brand ID")

  # Clean up description - remove any "Satıcı:" text and related HTML
  description = trendyol_product.description
  if description:
    import re
    # Remove p tag containing "Satıcı:" text
    description = re.sub(r'<p[^>]*>.*?Satıcı:.*?</p>', '', description, flags=re.DOTALL)
    # Also remove just the b tag with "Satıcı:" if it exists
    description = re.sub(r'<b[^>]*>.*?Satıcı:.*?</b>', '', description, flags=re.DOTALL)
    # Add extra processing to extract more readable text
    # Remove all HTML tags but keep their content
    description_text = re.sub(r'<[^>]+>', ' ', description)
    # Normalize spaces
    description_text = re.sub(r'\s+', ' ', description_text).strip()
    print(f"[DEBUG-API] Açıklama temizlendi: {description[:200]}...")
    print(f"[DEBUG-API] Metin formatında açıklama: {description_text[:200]}...")
    
  # Clean up product title - normalize spaces
  title = trendyol_product.title
  if title:
    import re
    # Replace multiple spaces with a single space
    title = re.sub(r'\s+', ' ', title.strip())
    print(f"[DEBUG-API] Ürün adı temizlendi: '{title}'")
  else:
    title = trendyol_product.title

  # Get required attributes for the category, using description to match attributes
  product_manager = get_product_manager()
  attributes = product_manager._get_attributes_for_category(
      trendyol_product.category_id, description)
      
  # If this is a variant with size information, make sure it's included in the attributes
  if trendyol_product.variant_key:
      # Check if size attribute already exists
      size_attribute_exists = False
      for attr in attributes:
          if attr.get('attributeName', '').lower() in ['beden', 'size', 'numara', 'ölçü']:
              size_attribute_exists = True
              break
              
      # If no size attribute exists, try to add it
      if not size_attribute_exists:
          try:
              # Try to find size attribute in category attributes
              category_attrs = product_manager.category_finder.get_category_attributes(
                  trendyol_product.category_id)
                  
              for cat_attr in category_attrs.get('categoryAttributes', []):
                  attr_name = cat_attr['attribute']['name']
                  if attr_name.lower() in ['beden', 'size', 'numara', 'ölçü']:
                      # Found size attribute, now check if variant size exists in values
                      size_value_id = None
                      size_value_name = None
                      
                      for val in cat_attr.get('attributeValues', []):
                          if val['name'].lower() == trendyol_product.variant_key.lower():
                              size_value_id = val['id']
                              size_value_name = val['name']
                              break
                      
                      # Add size attribute
                      if size_value_id:
                          attributes.append({
                              "attributeId": cat_attr['attribute']['id'],
                              "attributeName": attr_name,
                              "attributeValueId": size_value_id,
                              "attributeValue": size_value_name
                          })
                      elif cat_attr.get('allowCustom'):
                          attributes.append({
                              "attributeId": cat_attr['attribute']['id'],
                              "attributeName": attr_name,
                              "customAttributeValue": trendyol_product.variant_key
                          })
                      
                      print(f"[DEBUG-API] Varyant boyutu eklendi: {attr_name} = {trendyol_product.variant_key}")
                      break
          except Exception as e:
              print(f"[DEBUG-API] Varyant boyutu eklerken hata: {str(e)}")

  # Construct the payload
  payload = {
      "barcode": trendyol_product.barcode,
      "title": title,  # Use cleaned title
      "productMainId": trendyol_product.product_main_id,
      "brandId": trendyol_product.brand_id,
      "categoryId": trendyol_product.category_id,
      "quantity": trendyol_product.quantity,
      "stockCode": trendyol_product.stock_code,
      "dimensionalWeight": 1,  # Default value
      "description": description,  # Use cleaned description
      "currencyType": trendyol_product.currency_type or "TRY",
      "listPrice": float(trendyol_product.price),
      "salePrice":
      float(trendyol_product.price),  # Use the same price if no discount
      "vatRate": trendyol_product.vat_rate or 10,
      "images": [{
          "url": trendyol_product.image_url
      }],
      "attributes": attributes
  }

  # Add additional images if available
  if trendyol_product.additional_images:
    for img in trendyol_product.additional_images:
      payload["images"].append({"url": img})
  print(payload)

  return payload


def analyze_and_determine_attribute(attr_name: str, product_data: Dict, category_attr_vals: List) -> Optional[Dict]:
  """
  Akıllı öznitelik analizi ile ürün bilgilerinden en uygun değeri belirleme
  
  Bu fonksiyon, ürün başlığı ve açıklamasını analiz ederek öznitelik için
  en uygun değeri akıllıca belirler. Örneğin renk, cinsiyet, yaş grubu gibi
  öznitelikleri otomatik olarak tespit eder.
  
  Args:
      attr_name: Öznitelik adı
      product_data: Ürün verilerini içeren sözlük
      category_attr_vals: Kategori için mevcut öznitelik değerleri
      
  Returns:
      Seçilen öznitelik değeri bilgisi veya None
  """
  attr_name_lower = attr_name.lower()
  product_title = product_data.get('title', '')
  product_description = product_data.get('description', '')
  
  # Birleşik metin - daha kapsamlı analiz için
  combined_text = f"{product_title} {product_description}".lower()
  
  print(f"[DEBUG-AI] {attr_name} özniteliği için değer belirleniyor")
  
  # Öznitelik kategorisini belirle
  attr_category = None
  for category, keywords in SPECIAL_ATTRIBUTES.items():
    if any(keyword in attr_name_lower for keyword in keywords):
      attr_category = category
      print(f"[DEBUG-AI] {attr_name} özniteliği '{category}' kategorisine ait")
      break
  
  # Eğer bu bir özel kategori özniteliği ise
  if attr_category:
    # RENK DEĞERİ BELİRLEME
    if attr_category == 'renk':
      # Yaygın Türkçe renkler
      turkish_colors = {
        'kırmızı': ['kırmızı', 'kirmizi', 'red', 'bordo'],
        'mavi': ['mavi', 'blue', 'lacivert', 'indigo', 'navy'],
        'yeşil': ['yeşil', 'yesil', 'green', 'haki', 'mint', 'fıstık yeşili'],
        'sarı': ['sarı', 'sari', 'yellow', 'hardal'],
        'siyah': ['siyah', 'black', 'koyu'],
        'beyaz': ['beyaz', 'white', 'krem', 'ekru', 'bej'],
        'gri': ['gri', 'gray', 'grey', 'antrasit'],
        'pembe': ['pembe', 'pink', 'fuşya', 'fusya'],
        'mor': ['mor', 'purple', 'violet', 'lila'],
        'turuncu': ['turuncu', 'orange', 'tarçın'],
        'kahverengi': ['kahverengi', 'kahve', 'brown', 'camel'],
      }
      
      # Renk değeri analizi
      detected_color = None
      best_match_score = 0
      
      # Metinde renk terimleri ara
      for base_color, color_terms in turkish_colors.items():
        for color_term in color_terms:
          if color_term in combined_text:
            # Daha spesifik eşleşme için çevreleyen metni kontrol et
            context_score = 3
            color_index = combined_text.find(color_term)
            if color_index > 0:
              before_text = combined_text[max(0, color_index-20):color_index]
              if 'renk' in before_text or 'renkli' in before_text:
                context_score += 2
            
            # Daha uzun renk terimleri daha spesifik olabilir
            length_score = min(len(color_term) / 4, 1.5)
            
            # Toplam skor
            current_score = context_score + length_score
            
            if current_score > best_match_score:
              best_match_score = current_score
              detected_color = base_color
              
      # Tespit edilen rengi yazdır
      if detected_color:
        print(f"[DEBUG-AI] Metinden belirlenen renk: {detected_color} (skor: {best_match_score:.2f})")
        
        # Kategori öznitelik değerlerinde bu rengi ara
        for val in category_attr_vals:
          val_name = val.get('name', '').lower()
          
          # Renk eşleşme kontrolü - tam veya içinde olma durumu
          if detected_color == val_name or detected_color in val_name or val_name in detected_color:
            print(f"[DEBUG-AI] Tam renk eşleşmesi: {val.get('name')}")
            return {
              "attributeId": val.get('id'),
              "attributeValueId": val.get('id'),
              "attributeName": attr_name,
              "attributeValue": val.get('name')
            }
        
        # Eşleşme bulunamadıysa metin içinde doğrudan arama yap
        for val in category_attr_vals:
          val_name = val.get('name', '').lower()
          if val_name in combined_text:
            print(f"[DEBUG-AI] Metin içinde renk eşleşmesi: {val.get('name')}")
            return {
              "attributeId": val.get('id'),
              "attributeValueId": val.get('id'),
              "attributeName": attr_name,
              "attributeValue": val.get('name')
            }
    
    # CİNSİYET DEĞERİ BELİRLEME
    elif attr_category == 'cinsiyet':
      # Cinsiyet analizi
      gender_matches = {
        'erkek': 0,
        'kadın': 0,
        'kız': 0,
        'unisex': 0
      }
      
      # Önce iyi belirlenmiş ifadeleri ara
      clear_indicators = {
        'erkek': ['erkek çocuk', 'erkek bebek', 'boy', 'men', 'erkekler için'],
        'kadın': ['kadın', 'bayan', 'women', 'kadınlar için'],
        'kız': ['kız çocuk', 'kız bebek', 'girl', 'kızlar için'],
        'unisex': ['unisex', 'hem erkek hem kız', 'universal']
      }
      
      for gender, indicators in clear_indicators.items():
        for indicator in indicators:
          if indicator in combined_text:
            gender_matches[gender] += 3
      
      # Basit kelime eşleşmesi
      if 'erkek' in combined_text:
        gender_matches['erkek'] += 2
      if 'kadın' in combined_text:
        gender_matches['kadın'] += 2
      if 'kız' in combined_text:
        gender_matches['kız'] += 2
      if 'unisex' in combined_text:
        gender_matches['unisex'] += 2
        
      # En iyi eşleşmeyi bul
      best_gender = max(gender_matches.items(), key=lambda x: x[1])
      if best_gender[1] > 0:
        determined_gender = best_gender[0]
        print(f"[DEBUG-AI] Metinden belirlenen cinsiyet: {determined_gender} (skor: {best_gender[1]})")
        
        # Bu cinsiyet için uygun öznitelik değeri ara
        for val in category_attr_vals:
          val_name = val.get('name', '').lower()
          
          # Cinsiyet eşleşme kontrolü
          if determined_gender in val_name:
            print(f"[DEBUG-AI] Cinsiyet eşleşmesi: {val.get('name')}")
            return {
              "attributeId": val.get('id'),
              "attributeValueId": val.get('id'),
              "attributeName": attr_name,
              "attributeValue": val.get('name')
            }
            
    # YAŞ GRUBU DEĞERİ BELİRLEME
    elif attr_category == 'yaş' or 'yaş grubu' in attr_name_lower:
      # Yaş grubu eşleştirme göstergeleri
      age_patterns = [
        (r'(\d+)[- ]?(\d+)?\s*(ay|months)', 'bebek'),  # 0-24 ay
        (r'(\d+)[- ]?(\d+)?\s*(yaş|yas|years|age)', 'çocuk'),  # 2-14 yaş
        (r'yeni\s*doğan|newborn', 'bebek'),  # Yenidoğan
        (r'bebek|baby|infant', 'bebek'),      # Bebek
        (r'çocuk|child|kid', 'çocuk'),        # Çocuk
        (r'genç|teen|ergen|adolescent', 'genç'), # Genç
        (r'yetişkin|adult', 'yetişkin')       # Yetişkin
      ]
      
      determined_age_group = None
      
      # Tam yaş ifadeleri ara - patern eşleştirme
      for pattern, age_group in age_patterns:
        if re.search(pattern, combined_text):
          determined_age_group = age_group
          print(f"[DEBUG-AI] Metinden belirlenen yaş grubu: {determined_age_group} (patern: {pattern})")
          break
          
      # Şimdi spesifik yaş aralıklarını ara
      if not determined_age_group:
        # Yaş aralıklarını ara: "3-4 yaş" gibi
        age_ranges = re.findall(r'(\d+)[-](\d+)\s*(yaş|yas|years|age)', combined_text)
        if age_ranges:
          min_age, max_age = int(age_ranges[0][0]), int(age_ranges[0][1])
          print(f"[DEBUG-AI] Tespit edilen yaş aralığı: {min_age}-{max_age} yaş")
          
          # Yaş aralığına göre grup belirle
          if max_age <= 3:
            determined_age_group = 'bebek'
          elif max_age <= 14:
            determined_age_group = 'çocuk'
          elif max_age <= 18:
            determined_age_group = 'genç'
          else:
            determined_age_group = 'yetişkin'
      
      # Belirli bir yaş grubu bulunduysa
      if determined_age_group:
        # Bu yaş grubu için uygun öznitelik değeri ara
        for val in category_attr_vals:
          val_name = val.get('name', '').lower()
          
          # Yaş grubu eşleşme kontrolü
          if determined_age_group in val_name or val_name in determined_age_group:
            print(f"[DEBUG-AI] Yaş grubu eşleşmesi: {val.get('name')}")
            return {
              "attributeId": val.get('id'),
              "attributeValueId": val.get('id'),
              "attributeName": attr_name,
              "attributeValue": val.get('name')
            }
            
    # BEDEN / BOY DEĞERİ BELİRLEME            
    elif attr_category == 'beden' or 'boy' in attr_name_lower:
      # Beden ve boy için yaygın değerler
      size_patterns = [
        # Çocuk yaş bedenleri
        (r'(\d+)[-]?(\d+)?\s*(yaş|yas|years|age)', 'yaş'),
        # Sayısal beden
        (r'\b(\d+)\s*(beden|numara|size)', 'numara'),
        # Standart bedenler
        (r'\b([xsml]|[XS|S|M|L]|small|medium|large|extra\s*large)\b', 'standart')
      ]
      
      determined_size = None
      size_type = None
      
      # Önce parçalanmış beden isimleri ara - örn: "M Beden"
      for pattern, type_name in size_patterns:
        size_matches = re.search(pattern, combined_text)
        if size_matches:
          if type_name == 'yaş':
            age_min = size_matches.group(1)
            age_max = size_matches.group(2) if size_matches.group(2) else age_min
            determined_size = f"{age_min}-{age_max} Yaş"
          elif type_name == 'numara':
            determined_size = f"{size_matches.group(1)} Beden"
          else:
            determined_size = size_matches.group(1).upper()
            
          size_type = type_name
          print(f"[DEBUG-AI] Metinden belirlenen beden: {determined_size} (tür: {size_type})")
          break
          
      # Bulunan beden için uygun öznitelik değeri ara  
      if determined_size:
        for val in category_attr_vals:
          val_name = val.get('name', '').lower()
          determined_size_lower = determined_size.lower()
          
          # Beden eşleşme kontrolü - tam veya içerme
          if determined_size_lower == val_name or determined_size_lower in val_name:
            print(f"[DEBUG-AI] Beden eşleşmesi: {val.get('name')}")
            return {
              "attributeId": val.get('id'),
              "attributeValueId": val.get('id'),
              "attributeName": attr_name,
              "attributeValue": val.get('name')
            }
      
  # Hiçbir eşleşme bulunamadıysa ve değerler mevcutsa, ilk değeri kullan
  if category_attr_vals and len(category_attr_vals) > 0:
    first_val = category_attr_vals[0]
    print(f"[DEBUG-AI] {attr_name} için özel eşleşme bulunamadı, ilk değer kullanılıyor: {first_val.get('name')}")
    
    # "Belirtilmemiş" değeri ara
    unspecified_val = None
    for val in category_attr_vals:
      val_name = val.get('name', '').lower()
      if val_name in ['belirtilmemiş', 'belirtilmemis', 'bilinmiyor', 'other', 'diğer']:
        unspecified_val = val
        print(f"[DEBUG-AI] {attr_name} için 'Belirtilmemiş' değeri bulundu (ID: {val.get('id')})")
        break
        
    if unspecified_val:
      return {
        "attributeId": unspecified_val.get('id'),
        "attributeValueId": unspecified_val.get('id'),
        "attributeName": attr_name,
        "attributeValue": unspecified_val.get('name')
      }
    else:
      return {
        "attributeId": first_val.get('id'),
        "attributeValueId": first_val.get('id'),
        "attributeName": attr_name,
        "attributeValue": first_val.get('name')
      }
  
  # Hiçbir değer yoksa None döndür
  return None


def get_required_attributes_and_retry(batch_id: str, product_data: Dict, max_retries: int = 3) -> str:
  """
  Batch ID'yi kullanarak hata mesajlarından gereken öznitelikleri alıp ürünü tekrar gönderir.
  Hata devam ederse birden fazla kez deneyerek tüm gerekli öznitelikleri tespit eder.
  
  Args:
      batch_id: İlk gönderimden dönen batch ID
      product_data: Ürün bilgilerini içeren sözlük
      max_retries: Maksimum tekrar deneme sayısı
      
  Returns:
      Yeni oluşturulan batch ID
  """
  current_batch_id = batch_id
  current_product_data = copy.deepcopy(product_data)
  retry_count = 0
  all_required_attrs = set()  # Şimdiye kadar tespit edilen tüm zorunlu öznitelikler
  
  try:
    # API client al
    product_manager = get_product_manager()
    
    # Kategori ID'sini kontrol et
    category_id = current_product_data.get('categoryId')
    if not category_id:
      logger.error("Category ID is required")
      return current_batch_id
      
    # Kategori özniteliklerini al
    category_attrs = product_manager.category_finder.get_category_attributes(category_id)
    
    # Current product attributes - şu ana kadar eklenmiş öznitelikler
    current_attributes = current_product_data.get('attributes', [])
    
    # Tekrarlı deneme döngüsü - her seferinde yeni zorunlu öznitelikler eklenecek
    while retry_count < max_retries:
      retry_count += 1
      
      # Gereken öznitelikleri hata mesajlarından belirle
      new_required_attrs = product_manager.get_required_attributes_from_error(current_batch_id)
      
      if not new_required_attrs:
        logger.info(f"No new required attributes found, product might be ready or processing")
        
        # Son batch durumunu kontrol et
        batch_status = product_manager.check_batch_status(current_batch_id)
        status = batch_status.get('status', 'UNKNOWN')
        
        if status in ['SUCCEEDED', 'SUCCESS', 'PROCESSING', 'IN_PROGRESS']:
          logger.info(f"Batch {current_batch_id} status is {status}, no more retries needed")
          print(f"[DEBUG-API] Batch durumu: {status}. Başarılı oldu veya işleniyor.")
          return current_batch_id
          
        if retry_count >= max_retries:
          logger.warning(f"Maximum retries ({max_retries}) reached with no new attributes found")
          print(f"[DEBUG-API] Maksimum deneme sayısına ulaşıldı: {max_retries}")
          return current_batch_id
          
        # Kısa bir bekleme süresi ve tekrar kontrol
        logger.info("Waiting 3 seconds before rechecking batch status...")
        time.sleep(3)
        continue
        
      # Yeni bulunan öznitelikleri genel listeye ekle
      print(f"[DEBUG-API] Deneme {retry_count}: {len(new_required_attrs)} yeni zorunlu öznitelik bulundu")
      all_required_attrs.update(new_required_attrs)
      
      # Gereken öznitelikleri ata
      for attr_name in new_required_attrs:
        # Daha önce eklenmiş mi kontrol et
        if any(attr.get('attributeName') == attr_name for attr in current_attributes):
          print(f"[DEBUG-API] {attr_name} özniteliği zaten eklenmiş, atlanıyor")
          continue
          
        attr_added = False
        
        # Kategori özelliklerinde ara
        for cat_attr in category_attrs.get('categoryAttributes', []):
          if cat_attr['attribute']['name'] == attr_name and cat_attr.get('attributeValues'):
            # Öznitelik değeri bulundu
            attribute = {
              "attributeId": cat_attr['attribute']['id'],
              "attributeName": cat_attr['attribute']['name']
            }
            
            # Özel öznitelik işleme (kumaş/kalıp)
            attr_name_lower = attr_name.lower()
            
            # SPECIAL_ATTRIBUTES değişkeninin tanımlı olup olmadığını kontrol et
            if 'SPECIAL_ATTRIBUTES' not in globals():
                # Tanımlı değilse, özel öznitelikleri burada tanımla
                is_fabric_attribute = any(keyword in attr_name_lower for keyword in ['kumaş', 'fabric', 'material'])
                is_pattern_attribute = any(keyword in attr_name_lower for keyword in ['kalıp', 'pattern', 'fit'])
            else:
                # Tanımlıysa, global değişkeni kullan
                is_fabric_attribute = any(keyword in attr_name_lower for keyword in SPECIAL_ATTRIBUTES.get('kumaş', [])) 
                is_pattern_attribute = any(keyword in attr_name_lower for keyword in SPECIAL_ATTRIBUTES.get('kalıp', []))
            
            # Belirtilmemiş değerini ara
            if is_fabric_attribute or is_pattern_attribute:
              belirtilmemis_found = False
              for val in cat_attr['attributeValues']:
                if val['name'].lower() in ['belirtilmemiş', 'belirtilmemis', 'bilinmiyor', 'other', 'diğer']:
                  attribute["attributeValueId"] = val['id']
                  attribute["attributeValue"] = val['name']
                  belirtilmemis_found = True
                  print(f"[DEBUG-API] Özel işleme: {attr_name} için 'Belirtilmemiş' değeri seçildi")
                  break
              
              # Belirtilmemiş bulunamadıysa ilk değeri kullan
              if not belirtilmemis_found and cat_attr['attributeValues']:
                first_val = cat_attr['attributeValues'][0]
                attribute["attributeValueId"] = first_val['id']
                attribute["attributeValue"] = first_val['name']
                print(f"[DEBUG-API] {attr_name} için ilk değer seçildi: {first_val['name']}")
            else:
              # Normal öznitelik için ilk değeri kullan
              first_val = cat_attr['attributeValues'][0]
              attribute["attributeValueId"] = first_val['id']
              attribute["attributeValue"] = first_val['name']
              print(f"[DEBUG-API] {attr_name} için ilk değer seçildi: {first_val['name']}")
            
            current_attributes.append(attribute)
            attr_added = True
            break
        
        if not attr_added:
          logger.warning(f"Could not find attribute '{attr_name}' in category attributes")
      
      # Attributes listesini güncelle
      if not current_attributes:
        logger.warning("No attributes could be added")
        return current_batch_id
      
      # Ürün payload'ını güncelle
      current_product_data['attributes'] = current_attributes
      
      # Ürünü tekrar gönder
      logger.info(f"Resubmitting product with {len(current_attributes)} attributes (pass {retry_count})")
      print(f"[DEBUG-API] Ürün {len(current_attributes)} öznitelik ile tekrar gönderiliyor (Deneme {retry_count})")
      print(f"[DEBUG-API] Eklenen öznitelikler: {', '.join([attr.get('attributeName') for attr in current_attributes])}")
      
      # API üzerinden gönder
      response = product_manager.api.post(
        f"product/sellers/{product_manager.api.config.seller_id}/products", 
        {"items": [current_product_data]}
      )
      
      new_batch_id = response.get('batchRequestId')
      if new_batch_id:
        logger.info(f"Product resubmitted with batch ID: {new_batch_id}")
        print(f"[DEBUG-API] Ürün tekrar gönderildi. Yeni Batch ID: {new_batch_id}")
        current_batch_id = new_batch_id
        
        # Kısa bir bekleme süresi - API'nin işleme zamanı için
        logger.info("Waiting 3 seconds for API processing...")
        time.sleep(3)
        
        # Batch durumunu hemen kontrol et
        batch_status = product_manager.check_batch_status(current_batch_id)
        status = batch_status.get('status', 'UNKNOWN')
        
        # Eğer başarılı olduysa döngüyü sonlandır
        if status in ['SUCCEEDED', 'SUCCESS']:
          logger.info(f"Batch {current_batch_id} status is {status}, retries complete")
          print(f"[DEBUG-API] Batch durumu: {status}. İşlem başarıyla tamamlandı!")
          return current_batch_id
      else:
        logger.error("Failed to get batch ID from response")
        return current_batch_id
    
    # Son batch ID'yi döndür
    return current_batch_id
      
  except Exception as e:
    logger.error(f"Error in get_required_attributes_and_retry: {str(e)}")
    print(f"[DEBUG-API] Hata: {str(e)}")
    return current_batch_id


def sync_product_to_trendyol(trendyol_product: TrendyolProduct) -> str:
  """
    Sync a Trendyol product to the Trendyol platform using minimalist approach:
    1. First send without attributes
    2. Check batch status for required attributes
    3. Resend with only required attributes
    
    Returns the batch ID of the submission.
    Raises exceptions if the sync fails.
    """
  try:
    # 1. Prepare product data - but without attributes
    product_data = prepare_product_for_trendyol(trendyol_product)
    
    # Get the API manager
    product_manager = get_product_manager()
    
    # Remove attributes before sending
    product_data_copy = copy.deepcopy(product_data)
    product_data_copy['attributes'] = []
    
    logger.info(f"Sending product {trendyol_product.id} without attributes first")
    print(f"[DEBUG-API] Ürün önce özniteliksiz gönderiliyor (ID: {trendyol_product.id})")
    
    # 2. Send the product to Trendyol
    response = product_manager.api.post(
        f"product/sellers/{product_manager.api.config.seller_id}/products",
        {"items": [product_data_copy]})

    # Get the batch ID
    initial_batch_id = response.get('batchRequestId')
    if not initial_batch_id:
      raise ValueError(f"No batch ID returned from Trendyol API: {response}")
    
    # Update product with initial batch ID
    trendyol_product.batch_id = initial_batch_id
    trendyol_product.batch_status = 'processing'
    trendyol_product.last_sync_time = timezone.now()
    trendyol_product.status_message = "Initial submission without attributes"
    trendyol_product.save()
    
    logger.info(f"Initial submission successful with batch ID: {initial_batch_id}")
    print(f"[DEBUG-API] İlk gönderim başarılı. Batch ID: {initial_batch_id}")
    
    # 3. Wait for a moment before checking batch status
    time.sleep(2)
    
    # 4. Check batch status to get required attributes
    logger.info(f"Checking batch status to determine required attributes")
    batch_status = product_manager.check_batch_status(initial_batch_id)
    
    # 5. Get required attributes from error messages
    required_attrs = product_manager.get_required_attributes_from_error(initial_batch_id)
    
    # 6. If required attributes found, resubmit with them
    if required_attrs:
      logger.info(f"Found {len(required_attrs)} required attributes: {', '.join(required_attrs)}")
      print(f"[DEBUG-API] {len(required_attrs)} zorunlu öznitelik bulundu: {', '.join(required_attrs)}")
      
      # Resubmit with required attributes
      final_batch_id = get_required_attributes_and_retry(initial_batch_id, product_data_copy)
      
      if final_batch_id != initial_batch_id:
        # Update product with new batch ID
        trendyol_product.batch_id = final_batch_id
        trendyol_product.batch_status = 'processing'
        trendyol_product.last_sync_time = timezone.now()
        trendyol_product.status_message = f"Resubmitted with {len(required_attrs)} required attributes"
        trendyol_product.save()
        
        logger.info(f"Product resubmitted with required attributes, new batch ID: {final_batch_id}")
        print(f"[DEBUG-API] Ürün zorunlu özniteliklerle tekrar gönderildi. Yeni Batch ID: {final_batch_id}")
        
        return final_batch_id
    
    return initial_batch_id
    
  except Exception as e:
    # Update the product status
    trendyol_product.batch_status = 'failed'
    trendyol_product.status_message = f"Sync failed: {str(e)}"
    trendyol_product.save()

    logger.error(f"Failed to sync product {trendyol_product.id} to Trendyol: {str(e)}")
    raise
