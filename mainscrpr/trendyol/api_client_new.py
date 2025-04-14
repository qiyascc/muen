"""
Trendyol API Client for Integration with Trendyol Marketplace

This module provides classes and functions to interact with the Trendyol API
for product management, category discovery, and other marketplace operations.
"""

import requests
import json
from urllib.parse import quote
import time
import logging
import uuid
import re
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from functools import lru_cache
from typing import Dict, List, Optional, Union, Any

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

from trendyol.models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct

TRENDYOL_API_BASE_URL = "https://apigw.trendyol.com"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

class TrendyolAPI:
    """Base class for Trendyol API operations with retry mechanism"""
    
    def __init__(self, config: TrendyolAPIConfig):
        self.config = config
        self.base_url = config.base_url
        self.supplier_id = config.supplier_id
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        
        # URLs for different API endpoints
        self.brands = f"{self.base_url}/integration/product/brands"
        self.categories = f"{self.base_url}/integration/product/product-categories"
        self.products = f"{self.base_url}/integration/product/sellers/{self.supplier_id}/products"
        self.inventory = f"{self.base_url}/integration/updateProducts"
        
        # Setup session with authentication
        self.session = requests.Session()
        import base64
        auth_token = base64.b64encode(f"{self.api_key}:{self.api_secret}".encode()).decode()
        self.session.headers.update({
            "Authorization": f"Basic {auth_token}",
            "User-Agent": f"{self.supplier_id} - Integration",
            "Content-Type": "application/json"
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Generic request method with retry logic"""
        url = endpoint
        kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Making {method} request to {url}")
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
                    # Return error information in a structured format
                    return {
                        "error": True,
                        "message": f"API request failed: {str(e)}",
                        "details": f"Status code: {getattr(e.response, 'status_code', 'N/A')}, Response: {getattr(e.response, 'text', 'No response')}"
                    }
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
        self._category_cache = None
        self._attribute_cache = {}
        
        # Initialize advanced search components if available
        if ADVANCED_SEARCH_AVAILABLE:
            try:
                self.model = SentenceTransformer('emrecan/bert-base-turkish-cased-mean-nli-stsb-tr')
                self.dictionary = MultiDictionary()
                logger.info("Initialized semantic search with Turkish model")
            except Exception as e:
                logger.warning(f"Failed to initialize semantic search: {str(e)}")
                self.model = None
                self.dictionary = None
        else:
            self.model = None
            self.dictionary = None
    
    @property
    def category_cache(self) -> List[Dict]:
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self) -> List[Dict]:
        """Fetch all categories from Trendyol API"""
        try:
            data = self.api.get(self.api.categories)
            categories = data.get('categories', [])
            logger.info(f"Fetched {len(categories)} categories from Trendyol API")
            return categories
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            return []
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id: int) -> Dict:
        """Get attributes for a specific category with caching"""
        if category_id in self._attribute_cache:
            return self._attribute_cache[category_id]
        
        try:
            endpoint = f"{self.api.categories}/{category_id}/attributes"
            data = self.api.get(endpoint)
            self._attribute_cache[category_id] = data
            return data
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            return {}
    
    def find_best_category(self, search_term: str) -> int:
        """Find the most relevant category for a given search term"""
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
                            string_sim = difflib.SequenceMatcher(None, term.lower(), cat['name'].lower()).ratio()
                            cat['similarity'] = string_sim
                            matches.append(cat.copy())
            
            if not matches:
                raise ValueError(f"No matching categories found for '{search_term}'")
            
            # Sort by similarity and return the best match
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            best_match = matches[0]
            
            logger.info(f"Best category match for '{search_term}': {best_match['name']} (ID: {best_match['id']}, Similarity: {best_match['similarity']:.2f})")
            return best_match['id']
            
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            # Fall back to simpler method
            return self._find_best_category_simple(search_term, categories)
    
    def _find_best_category_simple(self, search_term, categories):
        """Simple string matching for category search"""
        matches = self._find_all_matches(search_term, categories)
        
        if not matches:
            # Try with partial matching
            matches = self._find_partial_matches(search_term, categories)
        
        if matches:
            # Use difflib to find the best match
            best_match = max(matches, key=lambda x: difflib.SequenceMatcher(None, search_term.lower(), x['name'].lower()).ratio())
            logger.info(f"Best simple category match for '{search_term}': {best_match['name']} (ID: {best_match['id']})")
            return best_match['id']
        
        # Return a default category if nothing matches
        logger.warning(f"No category matches found for '{search_term}', using default")
        return 385  # Default category
    
    def _find_all_matches(self, search_term, categories):
        """Find exact matches in categories"""
        matches = []
        self._search_categories(search_term, categories, matches, exact=True)
        return matches
    
    def _find_partial_matches(self, search_term, categories):
        """Find partial matches in categories"""
        matches = []
        self._search_categories(search_term, categories, matches, exact=False)
        return matches
    
    def _search_categories(self, search_term, categories, matches, exact=True):
        """Recursively search through category tree"""
        term = search_term.lower()
        
        for cat in categories:
            cat_name = cat['name'].lower()
            
            if (exact and term == cat_name) or (not exact and term in cat_name):
                matches.append(cat)
            
            if 'subCategories' in cat and cat['subCategories']:
                self._search_categories(term, cat['subCategories'], matches, exact)
    
    def _collect_leaf_categories(self, categories, result):
        """Recursively collect categories without subcategories"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def _select_best_match(self, search_term, candidates):
        """Select best match using string similarity"""
        if not candidates:
            return None
        
        term = search_term.lower()
        best_score = -1
        best_match = None
        
        for candidate in candidates:
            name = candidate['name'].lower()
            score = difflib.SequenceMatcher(None, term, name).ratio()
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        return best_match
    
    def get_required_attributes(self, category_id: int) -> List[Dict]:
        """Get required attributes for a specific category"""
        try:
            attrs = self.get_category_attributes(category_id)
            attributes = []
            
            if not attrs or 'categoryAttributes' not in attrs:
                logger.warning(f"No category attributes found for category {category_id}")
                return []
            
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

def get_api_client() -> Optional[TrendyolAPI]:
    """Get a configured Trendyol API client instance"""
    try:
        # Get active configuration from database
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            logger.warning("No active Trendyol API configuration found")
            return None
        
        # Create and return API client
        api_client = TrendyolAPI(config)
        logger.info(f"Created Trendyol API client with config: {config.name}")
        return api_client
    except Exception as e:
        logger.error(f"Error creating Trendyol API client: {str(e)}")
        return None

def find_brand_id_by_name(brand_name: str, client: Optional[TrendyolAPI] = None) -> Optional[int]:
    """Find a brand ID by name in Trendyol"""
    if not client:
        client = get_api_client()
        if not client:
            logger.error("No API client available for brand search")
            return None
    
    try:
        # Check if we already have this brand in our database
        brand = TrendyolBrand.objects.filter(name__icontains=brand_name, is_active=True).first()
        if brand:
            logger.info(f"Using existing brand ID: {brand.brand_id}")
            return brand.brand_id
        
        # Encode the brand name for URL
        encoded_name = quote(brand_name)
        endpoint = f"{client.brands}/by-name?name={encoded_name}"
        
        response = client.get(endpoint)
        
        if isinstance(response, dict) and response.get('error'):
            logger.error(f"API error searching brand: {response.get('message')}")
            return None
        
        if not response or not isinstance(response, list) or len(response) == 0:
            logger.warning(f"No brand found with name: {brand_name}")
            return None
        
        brand_id = response[0].get('id')
        
        # Store brand in database for future use
        if brand_id:
            TrendyolBrand.objects.create(
                name=response[0].get('name'),
                brand_id=brand_id,
                is_active=True
            )
            logger.info(f"Added new brand to database: {response[0].get('name')} (ID: {brand_id})")
        
        return brand_id
    except Exception as e:
        logger.error(f"Error finding brand ID: {str(e)}")
        return None

def find_trendyol_category_id(search_term: str, client: Optional[TrendyolAPI] = None) -> int:
    """Find a suitable category ID based on the search term"""
    if not client:
        client = get_api_client()
        if not client:
            logger.error("No API client available for category search")
            return 385  # Default to a safe category
    
    try:
        # Check if we already have this category stored
        category = TrendyolCategory.objects.filter(name__icontains=search_term, is_active=True).first()
        if category:
            logger.info(f"Using existing category: {category.name} (ID: {category.category_id})")
            return category.category_id
        
        # Use our category finder
        finder = TrendyolCategoryFinder(client)
        category_id = finder.find_best_category(search_term)
        
        return category_id
    except Exception as e:
        logger.error(f"Error finding category ID: {str(e)}")
        return 385  # Default to a safe category

def get_required_attributes_for_category(
    category_id: int,
    product_title: str = None,
    product_color: str = None,
    product_size: str = None) -> List[Dict[str, Any]]:
    """
    Get required attributes for a specific category directly from Trendyol API.
    Returns a list of attribute dictionaries in format required by Trendyol API.
    
    Bu fonksiyon, her kategori için doğru özellikleri Trendyol API'sinden alır
    ve sabit değerlere ihtiyaç duymaz.
    
    Args:
        category_id: The category ID
        product_title: The product title to infer attributes from (optional)
        product_color: The product color if known (optional)
        product_size: The product size if known (optional)
    
    Returns:
        List of attribute dictionaries in the format required by Trendyol API
    """
    logger.info(f"Getting required attributes for category ID={category_id}")

    try:
        client = get_api_client()
        if not client:
            logger.warning("API client could not be obtained")
            return []

        # İyileştirilmiş kategori bulucu kullanarak öznitelikleri al
        finder = TrendyolCategoryFinder(client)

        # Doğrudan API'den kategoriye özgü öznitelikleri al
        try:
            attributes = finder.get_required_attributes(category_id)
            logger.info(f"Kategorinin zorunlu özellikleri API'den alındı: {len(attributes)} özellik")
            logger.debug(f"Özellikler: {json.dumps(attributes, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"Kategori özellikleri alınırken hata: {str(e)}")
            attributes = []

        return attributes
    except Exception as e:
        logger.error(f"Error getting required attributes: {str(e)}")
        # Return an empty list on error - we won't use hardcoded values anymore
        # This will force the API to provide the correct values
        return []

def fetch_brands(api_client=None):
    """Fetch and store brands from Trendyol API"""
    if not api_client:
        api_client = get_api_client()
        if not api_client:
            logger.error("No API client available to fetch brands")
            return False
    
    try:
        # First check if we already have brands
        if TrendyolBrand.objects.count() > 0:
            logger.info(f"Using existing {TrendyolBrand.objects.count()} brands from database")
            return True
        
        logger.info("Fetching brands from Trendyol API...")
        response = api_client.get(api_client.brands)
        
        if isinstance(response, dict) and response.get('error'):
            logger.error(f"API error fetching brands: {response.get('message')}")
            return False
        
        if not response:
            logger.error("Empty response when fetching brands")
            return False
        
        # Store brands in database
        count = 0
        for brand in response:
            if 'id' in brand and 'name' in brand:
                TrendyolBrand.objects.get_or_create(
                    brand_id=brand['id'],
                    defaults={
                        'name': brand['name'],
                        'is_active': True
                    }
                )
                count += 1
        
        logger.info(f"Stored {count} brands in database")
        return True
    except Exception as e:
        logger.error(f"Error fetching brands: {str(e)}")
        return False

def fetch_categories(api_client=None):
    """Fetch and store categories from Trendyol API"""
    if not api_client:
        api_client = get_api_client()
        if not api_client:
            logger.error("No API client available to fetch categories")
            return False
    
    try:
        # First check if we already have categories
        if TrendyolCategory.objects.count() > 0:
            logger.info(f"Using existing {TrendyolCategory.objects.count()} categories from database")
            return True
        
        logger.info("Fetching categories from Trendyol API...")
        response = api_client.get(api_client.categories)
        
        if isinstance(response, dict) and response.get('error'):
            logger.error(f"API error fetching categories: {response.get('message')}")
            return False
        
        if not response or 'categories' not in response:
            logger.error("Invalid response when fetching categories")
            return False
        
        # Process categories recursively
        count = _process_categories(response['categories'])
        
        logger.info(f"Stored {count} categories in database")
        return True
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        return False

def _process_categories(categories, parent_id=None, count=0):
    """Recursively process and store categories"""
    for category in categories:
        if 'id' in category and 'name' in category:
            obj, created = TrendyolCategory.objects.get_or_create(
                category_id=category['id'],
                defaults={
                    'name': category['name'],
                    'parent_id': parent_id,
                    'is_active': True
                }
            )
            count += 1
            
            # Process subcategories if any
            if 'subCategories' in category and category['subCategories']:
                count = _process_categories(category['subCategories'], category['id'], count)
    
    return count

def prepare_product_data(product, client=None):
    """
    Prepare product data for Trendyol API submission.
    This function enriches the product with required attributes from Trendyol API.
    """
    if not client:
        client = get_api_client()
        if not client:
            logger.error("No API client available to prepare product data")
            raise ValueError("API client could not be obtained")
    
    # Check if we have required fields
    if not product.barcode or not product.title or not product.category_id:
        logger.error(f"Product {product.id} missing required fields")
        raise ValueError("Missing required fields: barcode, title or category_id")
    
    # Ensure we have brand ID
    brand_id = product.brand_id
    if not brand_id:
        raise ValueError("Brand ID is required")
    
    # Get category ID
    category_id = product.category_id
    if not category_id:
        raise ValueError("Category ID is required")
    
    # Get image URLs
    image_urls = []
    if product.image_url:
        image_urls.append(product.image_url)
    
    if product.additional_images:
        if isinstance(product.additional_images, list):
            image_urls.extend(product.additional_images)
        elif isinstance(product.additional_images, str):
            try:
                additional = json.loads(product.additional_images)
                if isinstance(additional, list):
                    image_urls.extend(additional)
            except:
                logger.warning(f"Failed to parse additional images for product {product.id}")
    
    # Get or create attributes
    attributes = product.attributes or []
    print(f"[DEBUG-PRODUCT] Zorunlu özellikleri alıyoruz, Ürün: {product.id}, Kategori: {category_id}")
    print(f"[DEBUG-PRODUCT] Mevcut özellikler: {json.dumps(attributes, ensure_ascii=False)}")
    
    # Get required attributes with our enhanced finder
    required_attrs = get_required_attributes_for_category(category_id)
    
    # Get existing attribute IDs, but handle special case for string "color"
    existing_attr_ids = set()
    color_attribute_exists = False
    
    # Pre-process attributes to fix the color attribute issue
    fixed_attributes = []
    for attr in attributes:
        if attr.get('attributeId') == 'color':
            # Mark that we have a color attribute to handle specially
            color_attribute_exists = True
            print(f"[DEBUG-PRODUCT] Renk özelliği string ID ile bulundu, değeri: {attr.get('attributeValueId')}")
            # Do not add this attribute to the fixed list yet
        else:
            # Add non-color attributes to our fixed attributes list
            fixed_attributes.append(attr)
            existing_attr_ids.add(attr.get('attributeId'))
    
    # Replace the original attributes with fixed ones (without 'color')
    attributes = fixed_attributes
    
    # Add required attributes from API, which will include the correct color attribute format
    for attr in required_attrs:
        attr_id = attr.get('attributeId')
        if attr_id not in existing_attr_ids:
            attributes.append(attr)
            print(f"[DEBUG-PRODUCT] Zorunlu özellik eklendi: AttributeID={attr_id}, ValueID={attr.get('attributeValueId')}")
    
    print(f"[DEBUG-PRODUCT] Toplam özellik sayısı: {len(attributes)}")
    
    # If attributes is still empty after all our attempts, this is a critical issue
    # and we should not proceed with submitting the product
    if not attributes or len(attributes) == 0:
        logger.error(f"Product {product.id} has no attributes after processing. Cannot submit to Trendyol.")
        logger.error(f"Category ID: {category_id}, Product Title: {product.title}")
        logger.error(f"API Response Debug - Required Attributes: {json.dumps(required_attrs, ensure_ascii=False)}")
        # Try one more time with direct API call to debug response
        try:
            debug_client = get_api_client()
            category_attrs_url = f"{debug_client.categories}/{category_id}/attributes"
            debug_response = debug_client.get(category_attrs_url)
            logger.error(f"API Debug Response: {json.dumps(debug_response, indent=2, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"Failed to get debug API response: {str(e)}")
        return None  # Don't proceed with empty attributes
    
    print(f"[DEBUG-PRODUCT] Özellikler: {json.dumps(attributes, ensure_ascii=False)}")
    
    # Prepare product data
    # Normalize whitespace - replace multiple spaces with single space
    normalized_title = " ".join(product.title.split()) if product.title else ""
    
    # Limit title to 100 characters to avoid "Ürün Adı 100 karakterden fazla olamaz" error
    title = normalized_title[:100] if normalized_title and len(normalized_title) > 100 else normalized_title
    
    product_data = {
        "barcode": product.barcode,
        "title": title,
        "productMainId": product.product_main_id or product.barcode,
        "brandId": brand_id,
        "categoryId": category_id,
        "stockCode": product.stock_code or product.barcode,
        "quantity": product.quantity or 10,  # Default to 10 if not specified
        # Removed stockUnitType per request
        # Removed dimensionalWeight per request
        "description": product.description or product.title,  # Use title as fallback description
        "currencyType": product.currency_type or "TRY",  # Default to Turkish Lira
        "listPrice": float(product.price or 0),
        "salePrice": float(product.price or 0),
        "vatRate": 10,  # Fix to 10% VAT as requested
        "cargoCompanyId": 17,  # Fixed cargo company ID as requested
        # Removed shipmentAddressId per request
        # Removed deliveryDuration per request
        # Removed pimCategoryId per request
        # Removed gender field - will be handled through attributes
        "attributes": attributes,
    }
    
    # Only add images if we have any
    if image_urls:
        product_data["images"] = [{"url": url} for url in image_urls if url]
    
    # We no longer add a separate "color" field - it should only be in attributes
    # This was previously causing validation errors
    # Color should only be in attributes with proper attributeId from the API
    # See updated implementation in admin.py and retry_failed_trendyol_products.py
    
    # Ensure all numeric values are proper floats/ints
    for key in ["quantity", "listPrice", "salePrice", "vatRate"]:
        if key in product_data and product_data[key] is not None:
            try:
                if key in ["listPrice", "salePrice"]:
                    product_data[key] = float(product_data[key])
                else:
                    product_data[key] = int(product_data[key])
            except (ValueError, TypeError):
                # If conversion fails, use default values
                if key in ["listPrice", "salePrice"]:
                    product_data[key] = 0.0
                else:
                    product_data[key] = 0
    
    # Make sure brandId and categoryId are integers
    for key in ["brandId", "categoryId"]:
        if key in product_data and product_data[key] is not None:
            try:
                product_data[key] = int(product_data[key])
            except (ValueError, TypeError):
                logger.error(f"Invalid {key}: {product_data[key]}")
                raise ValueError(f"Invalid {key}: must be an integer")
    
    return product_data

def lcwaikiki_to_trendyol_product(lcw_product) -> Optional[TrendyolProduct]:
    """
    Convert an LCWaikiki product to a Trendyol product.
    Returns the created or updated Trendyol product instance.
    
    This is an enhanced version with improved product code extraction and
    barcode generation to ensure uniqueness and Trendyol compatibility.
    It now also handles brand lookups and attribute mapping.
    """
    if not lcw_product:
        return None
    
    try:
        # Check if a Trendyol product already exists for this LCWaikiki product
        trendyol_product = TrendyolProduct.objects.filter(
            lcwaikiki_product=lcw_product).first()
    
        # Extract and format product code properly
        product_code = None
        if lcw_product.product_code:
            # Clean up product code - only allow alphanumeric characters
            product_code = re.sub(r'[^a-zA-Z0-9]', '', lcw_product.product_code)
            # Ensure it's not empty after cleaning
            if not product_code:
                product_code = None
    
        # Generate a unique barcode that meets Trendyol requirements
        # Trendyol requires unique barcode with alphanumeric chars
        barcode = None
        if product_code:
            barcode = f"LCW{product_code}"
        else:
            # If no product code, create a unique identifier based on ID and timestamp
            timestamp = int(time.time())
            barcode = f"LCW{lcw_product.id}{timestamp}"
    
        # Ensure barcode is alphanumeric and meets Trendyol requirements
        barcode = re.sub(r'[^a-zA-Z0-9]', '', barcode)
        # Cap length to avoid potential issues with very long barcodes
        barcode = barcode[:32]
    
        # Get the price with proper discount handling
        price = lcw_product.price or Decimal('0.00')
        if lcw_product.discount_ratio and lcw_product.discount_ratio > 0:
            # Apply discount if available
            discount_multiplier = Decimal('1.0') - (Decimal(str(lcw_product.discount_ratio)) / Decimal('100'))
            price = price * discount_multiplier
    
        # Handle images - ensure we have proper URL format
        images = []
        if hasattr(lcw_product, 'images') and lcw_product.images:
            try:
                if isinstance(lcw_product.images, str):
                    images = json.loads(lcw_product.images)
                elif isinstance(lcw_product.images, list):
                    images = lcw_product.images
    
                # Ensure all images start with http/https
                for i, img in enumerate(images):
                    if not img.startswith('http'):
                        images[i] = f"https:{img}" if img.startswith('//') else f"https://{img}"
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode images JSON for product {lcw_product.id}")
            except Exception as e:
                logger.warning(f"Error processing images for product {lcw_product.id}: {str(e)}")
    
        # If no images found, use a default placeholder image
        if not images:
            images = ["https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20224/5841125/l_20224-w4bi51z8-ct5_a.jpg"]
            logger.warning(f"No valid images found for product {lcw_product.id}, using placeholder")
    
        # Get quantity with fallback
        quantity = 10  # Default to 10 for better Trendyol acceptance
        if hasattr(lcw_product, 'get_total_stock'):
            try:
                stock = lcw_product.get_total_stock()
                if stock and stock > 0:
                    quantity = stock
            except Exception as e:
                logger.warning(f"Error getting total stock for product {lcw_product.id}: {str(e)}")
    
        # Find the appropriate brand ID in the Trendyol system
        brand_id = None
        try:
            # Try to find the LCW brand in our database
            lcw_brand = TrendyolBrand.objects.filter(name__icontains="LCW", is_active=True).first()
    
            if lcw_brand:
                brand_id = lcw_brand.brand_id
                logger.info(f"Found brand: {lcw_brand.name} (ID: {brand_id})")
            else:
                # Try to fetch brands if none found
                logger.info("No LCW brand found in database, fetching from Trendyol...")
                fetch_brands()
    
                # Try again after fetching
                lcw_brand = TrendyolBrand.objects.filter(name__icontains="LCW", is_active=True).first()
    
                if lcw_brand:
                    brand_id = lcw_brand.brand_id
                    logger.info(f"Found brand after fetch: {lcw_brand.name} (ID: {brand_id})")
                else:
                    # If still not found, use any available brand
                    any_brand = TrendyolBrand.objects.filter(is_active=True).first()
                    if any_brand:
                        brand_id = any_brand.brand_id
                        logger.warning(f"Using fallback brand: {any_brand.name} (ID: {brand_id})")
        except Exception as e:
            logger.error(f"Error finding brand for product {lcw_product.id}: {str(e)}")
    
        # Prepare basic attributes based on product data
        attributes = []
    
        # We'll fetch the actual attributes from API once we have the category ID
        # Setting this empty array ensures we check and populate it later in prepare_product_data
        # Using the enhanced get_required_attributes_for_category function
    
        # Find category information
        category_id = None
        if trendyol_product and trendyol_product.category_id:
            category_id = trendyol_product.category_id
        else:
            # Try to find a category based on the product's category name
            category_name = lcw_product.category or ""
            try:
                if category_name:
                    # Try to find a matching category
                    if "tişört" in category_name.lower() or "t-shirt" in category_name.lower():
                        # Look for T-shirt category
                        t_shirt_category = TrendyolCategory.objects.filter(
                            name__icontains="Tişört", is_active=True).first()
    
                        if t_shirt_category:
                            category_id = t_shirt_category.category_id
                            logger.info(f"Found T-shirt category: {t_shirt_category.name} (ID: {category_id})")
                    else:
                        # Generic search
                        words = category_name.split()
                        for word in words:
                            if len(word) > 3:  # Skip short words
                                matching_category = TrendyolCategory.objects.filter(
                                    name__icontains=word, is_active=True).first()
    
                                if matching_category:
                                    category_id = matching_category.category_id
                                    logger.info(f"Found category for '{word}': {matching_category.name} (ID: {category_id})")
                                    break
            except Exception as e:
                logger.error(f"Error finding category for product {lcw_product.id}: {str(e)}")
    
        # If category still not found, try to fetch categories
        if not category_id:
            try:
                logger.info("No category found, fetching from Trendyol...")
                fetch_categories()
    
                # Default to a standard clothing category if available
                default_category = TrendyolCategory.objects.filter(
                    name__icontains="Giyim", is_active=True).first()
    
                if default_category:
                    category_id = default_category.category_id
                    logger.warning(f"Using default category: {default_category.name} (ID: {category_id})")
            except Exception as e:
                logger.error(f"Error fetching categories: {str(e)}")
    
        if not trendyol_product:
            # We'll fetch attributes from API for the category later in prepare_product_data
            # This ensures that even though we're initializing with an empty attributes array,
            # it will be populated correctly before being sent to Trendyol
    
            # Create a new Trendyol product with enhanced data
            trendyol_product = TrendyolProduct.objects.create(
                title=lcw_product.title or "LC Waikiki Product",
                description=lcw_product.description or lcw_product.title
                or "LC Waikiki Product Description",
                barcode=barcode,
                product_main_id=product_code or barcode,
                stock_code=product_code or barcode,
                brand_name="LCW",
                brand_id=brand_id,
                category_name=lcw_product.category or "Clothing",
                category_id=category_id,
                pim_category_id=category_id,  # Use same as category_id initially
                price=price or Decimal('100.00'),  # Fallback price if none provided
                quantity=quantity,
                image_url=images[0] if images else "",
                additional_images=images[1:] if len(images) > 1 else [],
                attributes=attributes,
                lcwaikiki_product=lcw_product,
                batch_status='pending',
                status_message="Created from LCWaikiki product",
                currency_type="TRY",  # Turkish Lira
                vat_rate=18  # Default VAT rate in Turkey
            )
            logger.info(f"Created new Trendyol product from LCW product {lcw_product.id} with barcode {barcode}")
        else:
            # Update existing Trendyol product with latest LCWaikiki data
            trendyol_product.title = lcw_product.title or trendyol_product.title or "LC Waikiki Product"
            trendyol_product.description = lcw_product.description or lcw_product.title or trendyol_product.description or "LC Waikiki Product Description"
            trendyol_product.price = price or trendyol_product.price or Decimal('100.00')
            trendyol_product.quantity = quantity
            trendyol_product.brand_id = brand_id or trendyol_product.brand_id
            trendyol_product.category_id = category_id or trendyol_product.category_id
            trendyol_product.pim_category_id = category_id or trendyol_product.pim_category_id
    
            # We'll fetch attributes from API for the category later in prepare_product_data
            # This ensures that even though we're initializing with an empty attributes array,
            # it will be populated correctly before being sent to Trendyol
            
            # If product already has valid attributes, keep them, otherwise initialize empty
            if not trendyol_product.attributes or len(trendyol_product.attributes) == 0:
                trendyol_product.attributes = []
    
            # Only update barcode if it's not already been used with Trendyol
            if not trendyol_product.trendyol_id and not trendyol_product.batch_status == 'completed':
                trendyol_product.barcode = barcode
                trendyol_product.product_main_id = product_code or barcode
                trendyol_product.stock_code = product_code or barcode
    
            # Update images if available
            if images:
                trendyol_product.image_url = images[0]
                trendyol_product.additional_images = images[1:] if len(images) > 1 else []
    
            trendyol_product.save()
            logger.info(f"Updated Trendyol product {trendyol_product.id} from LCW product {lcw_product.id}")
    
        return trendyol_product
    except Exception as e:
        logger.error(f"Error converting LCWaikiki product to Trendyol product: {str(e)}")
        logger.exception(e)  # Log full traceback for debugging
        return None

def create_trendyol_product(product: TrendyolProduct) -> Optional[str]:
    """
    Create a product on Trendyol using the new API structure.
    Returns the batch ID if successful, None otherwise.
    
    This function includes comprehensive error handling with detailed
    error messages to make debugging easier. It validates required fields
    before submission and properly logs all operations.
    """
    print(f"[DEBUG-CREATE] Ürün oluşturma başlatılıyor: ID={product.id}, Başlık={product.title}")

    client = get_api_client()
    if not client:
        error_message = "No active Trendyol API configuration found"
        print(f"[DEBUG-CREATE] HATA: API yapılandırması bulunamadı")
        logger.error(error_message)
        product.batch_status = 'failed'
        product.status_message = error_message
        product.save()
        return None

    try:
        # Prepare product data
        print(f"[DEBUG-CREATE] Ürün verileri hazırlanıyor...")
        try:
            product_data = prepare_product_data(product, client)
            print(f"[DEBUG-CREATE] Hazırlanan ürün verileri: {json.dumps(product_data, ensure_ascii=False, default=str)[:250]}...")
        except ValueError as e:
            error_message = f"Error preparing product data: {str(e)}"
            print(f"[DEBUG-CREATE] HATA: Ürün verileri hazırlanamadı: {str(e)}")
            logger.error(f"{error_message} for product ID {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None

        # Validate that required fields are present
        required_fields = [
            'barcode', 'title', 'productMainId', 'brandId', 'categoryId',
            'quantity'
        ]
        missing_fields = [
            field for field in required_fields
            if field not in product_data or product_data[field] is None
        ]

        if missing_fields:
            error_message = f"Product data missing required fields: {', '.join(missing_fields)}"
            logger.error(f"{error_message} for product ID {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None

        # Create the product on Trendyol
        print(f"[DEBUG-CREATE] Trendyol'a ürün gönderiliyor...")
        
        # Create a unique batch ID
        batch_id = str(uuid.uuid4())
        
        # Construct the final payload
        payload = {
            "items": [product_data],
            "batchRequestId": batch_id,
            "hasMultiSupplier": False
        }
        
        logger.info(f"Submitting product '{product.title}' (ID: {product.id}) to Trendyol")
        logger.info(f"Product data: {json.dumps(product_data, default=str, indent=2)}")
        
        # Send the request
        response = client.post(client.products, payload)
        
        print(f"[DEBUG-CREATE] Trendyol'dan gelen yanıt: {json.dumps(response, ensure_ascii=False, default=str)}")

        # Handle different response error scenarios
        if not response:
            error_message = "No response from Trendyol API"
            logger.error(f"{error_message} for product ID {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None

        # Check if the response contains an error flag (from our enhanced error handling)
        if isinstance(response, dict) and response.get('error') is True:
            error_message = response.get('message', 'Unknown API error')
            error_details = response.get('details', '')

            # Log detailed error information
            logger.error(f"API error for product ID {product.id}: {error_message}")
            if error_details:
                logger.error(f"Error details: {error_details}")

            # Save detailed error information to the product
            full_error = f"{error_message}"
            if error_details:
                full_error += f" - {error_details}"

            product.batch_status = 'failed'
            product.status_message = full_error[:500]  # Truncate if too long
            product.save()
            return None

        # Check for errors in standard response format
        if isinstance(response, dict) and 'errors' in response and response['errors']:
            errors = response['errors']
            if isinstance(errors, list):
                error_message = f"Failed to create product: {errors[0].get('message', 'Unknown error')}"
            else:
                error_message = f"Failed to create product: {errors}"

            logger.error(f"{error_message} for product ID {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None

        if 'batchRequestId' not in response:
            error_message = "Failed to create product on Trendyol: No batch request ID returned"
            logger.error(f"{error_message} for product ID {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None

        batch_id = response.get('batchRequestId')

        # Update product with batch ID and status
        logger.info(f"Product '{product.title}' (ID: {product.id}) submitted with batch ID: {batch_id}")
        product.batch_id = batch_id
        product.batch_status = 'processing'
        product.status_message = "Product creation initiated"
        product.last_check_time = timezone.now()
        product.save()

        return batch_id
    except Exception as e:
        error_message = f"Error creating product: {str(e)}"
        logger.error(f"{error_message} for product ID {product.id}")
        product.batch_status = 'failed'
        product.status_message = error_message
        product.save()
        return None