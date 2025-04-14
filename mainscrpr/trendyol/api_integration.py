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
import time
from functools import lru_cache
from django.conf import settings
from decimal import Decimal

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
    additional_images: List[str] = None
    vat_rate: int = 10
    cargo_company_id: int = 10
    currency_type: str = "TRY"
    dimensional_weight: int = 1
    
    def __post_init__(self):
        if self.additional_images is None:
            self.additional_images = []

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
        
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request method: {method}")
        logger.debug(f"Request kwargs: {kwargs}")
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Log response information for debugging
                logger.debug(f"Response status code: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                logger.debug(f"Response body: {response.text[:500]}...")
                
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
    
    def put(self, endpoint: str, data: Dict) -> Dict:
        return self._make_request('PUT', endpoint, json=data)
    
    def delete(self, endpoint: str) -> Dict:
        return self._make_request('DELETE', endpoint)

class TrendyolCategoryFinder:
    """Handles category discovery and attribute management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        # Initialize sentence transformer model for semantic search
        try:
            self.model = SentenceTransformer('emrecan/bert-base-turkish-cased-mean-nli-stsb-tr')
            self.dictionary = MultiDictionary()
            self.use_ai = True
        except Exception as e:
            logger.warning(f"Failed to initialize sentence transformer: {e}")
            self.use_ai = False
            
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
        if not self.use_ai:
            # Fallback to simple text matching if AI is not available
            return self._find_category_by_text_match(search_term)
            
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
    
    def _find_category_by_text_match(self, search_term: str) -> int:
        """Simple text matching fallback for category finding"""
        categories = self.category_cache
        search_term_lower = search_term.lower()
        
        # First try exact matches
        for cat in self._get_all_leaf_categories(categories):
            if cat['name'].lower() == search_term_lower:
                return cat['id']
        
        # Then try partial matches
        for cat in self._get_all_leaf_categories(categories):
            if search_term_lower in cat['name'].lower():
                return cat['id']
        
        # If all fails, return a default category (Clothing)
        for cat in self._get_all_leaf_categories(categories):
            if 'giyim' in cat['name'].lower():
                return cat['id']
        
        # Ultimate fallback - just return the first leaf category
        if categories:
            return self._get_all_leaf_categories(categories)[0]['id']
        
        raise ValueError(f"No matching category found for: {search_term}")
    
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
    
    def get_required_attributes(self, category_id: int) -> List[Dict]:
        """Get required attributes for a category formatted for product submission"""
        category_attrs = self.get_category_attributes(category_id)
        required_attrs = []
        
        for attr in category_attrs.get('categoryAttributes', []):
            if attr.get('required', False):
                if attr['attribute']['name'] == 'Renk':
                    # Special handling for color attribute which is commonly required
                    required_attrs.append({
                        "attributeId": attr['attribute']['id'],
                        "attributeName": attr['attribute']['name']
                    })
                    
                    # Add a default color value (Siyah/Black) if available in values
                    for value in attr.get('attributeValues', []):
                        if 'siyah' in value['name'].lower():
                            required_attrs[-1]["attributeValueId"] = value['id']
                            required_attrs[-1]["attributeValue"] = value['name']
                            break
                else:
                    attribute = {
                        "attributeId": attr['attribute']['id'],
                        "attributeName": attr['attribute']['name']
                    }
                    
                    if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                        if not attr.get('allowCustom', False):
                            attribute["attributeValueId"] = attr['attributeValues'][0]['id']
                            attribute["attributeValue"] = attr['attributeValues'][0]['name']
                        else:
                            attribute["customAttributeValue"] = f"Standart"
                    
                    required_attrs.append(attribute)
        
        return required_attrs

class TrendyolProductManager:
    """Handles product creation and management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.category_finder = TrendyolCategoryFinder(api_client)
    
    def get_brand_id(self, brand_name: str) -> int:
        """Find brand ID by name"""
        encoded_name = quote(brand_name)
        try:
            brands = self.api.get(f"product/brands/by-name?name={encoded_name}")
            if isinstance(brands, list) and brands:
                return brands[0]['id']
            
            # If LCW brand not found, use fallback
            if 'lcw' in brand_name.lower() or 'lc waikiki' in brand_name.lower():
                logger.warning(f"Brand not found in API, using default LCW ID: 7651")
                return 7651
                
            raise ValueError(f"Brand not found: {brand_name}")
        except Exception as e:
            logger.error(f"Brand search failed for '{brand_name}': {str(e)}")
            # Use default ID for LC Waikiki as a fallback
            if 'lcw' in brand_name.lower() or 'lc waikiki' in brand_name.lower():
                logger.warning(f"Falling back to default LCW brand ID (7651) due to error")
                return 7651
            raise
    
    def create_product(self, product_data: ProductData) -> str:
        """Create a new product on Trendyol"""
        try:
            category_id = self.category_finder.find_best_category(product_data.category_name)
            brand_id = self.get_brand_id(product_data.brand_name)
            attributes = self.category_finder.get_required_attributes(category_id)
            
            payload = self._build_product_payload(product_data, category_id, brand_id, attributes)
            
            logger.info("Submitting product creation request...")
            response = self.api.post(f"product/sellers/{self.api.config.seller_id}/products", payload)
            
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Product creation failed: {str(e)}")
            raise
    
    def check_batch_status(self, batch_id: str) -> Dict:
        """Check the status of a batch operation"""
        try:
            return self.api.get(f"product/sellers/{self.api.config.seller_id}/products/batch-requests/{batch_id}")
        except Exception as e:
            logger.error(f"Failed to check batch status: {str(e)}")
            raise
    
    def update_price(self, barcode: str, list_price: float, sale_price: float) -> Dict:
        """Update product prices"""
        try:
            payload = {
                "items": [{
                    "barcode": barcode,
                    "listPrice": list_price,
                    "salePrice": sale_price
                }]
            }
            return self.api.post(f"product/sellers/{self.api.config.seller_id}/products/price-and-inventory", payload)
        except Exception as e:
            logger.error(f"Failed to update price for product {barcode}: {str(e)}")
            raise
    
    def update_stock(self, barcode: str, quantity: int) -> Dict:
        """Update product stock quantity"""
        try:
            payload = {
                "items": [{
                    "barcode": barcode,
                    "quantity": quantity
                }]
            }
            return self.api.post(f"product/sellers/{self.api.config.seller_id}/products/price-and-inventory", payload)
        except Exception as e:
            logger.error(f"Failed to update stock for product {barcode}: {str(e)}")
            raise
    
    def _build_product_payload(self, product: ProductData, category_id: int, brand_id: int, attributes: List[Dict]) -> Dict:
        """Construct the complete product payload"""
        images = [{"url": product.image_url}]
        for img_url in product.additional_images:
            images.append({"url": img_url})
            
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
                "images": images,
                "attributes": attributes
            }],
            "batchRequestId": str(uuid.uuid4()),
            "hasMultiSupplier": False,
            "supplierId": int(self.api.config.seller_id)
        }

def get_api_client(api_key=None, seller_id=None, base_url=None):
    """Factory function to create a configured API client"""
    from django.db import connection
    from django.db.utils import ProgrammingError
    
    # Try to get API configuration from database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT api_key, supplier_id, base_url FROM trendyol_trendyolapiconfig WHERE is_active = True LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                db_api_key, db_seller_id, db_base_url = row
                
                # Use provided values if they exist, otherwise fall back to database values
                api_key = api_key or db_api_key
                seller_id = seller_id or db_seller_id
                base_url = base_url or db_base_url or TRENDYOL_API_BASE_URL
    except (ProgrammingError, Exception) as e:
        logger.warning(f"Failed to get API config from database: {e}")
    
    # Final fallback to environment variables or default values
    api_key = api_key or getattr(settings, 'TRENDYOL_API_KEY', None)
    seller_id = seller_id or getattr(settings, 'TRENDYOL_SELLER_ID', None)
    base_url = base_url or getattr(settings, 'TRENDYOL_API_BASE_URL', TRENDYOL_API_BASE_URL)
    
    if not api_key or not seller_id:
        raise ValueError("API key and seller ID are required. Configure them in the database or settings.")
    
    config = APIConfig(api_key=api_key, seller_id=seller_id, base_url=base_url)
    return TrendyolAPI(config)

def get_product_manager(api_client=None):
    """Factory function to create a product manager with optional API client"""
    if api_client is None:
        api_client = get_api_client()
    return TrendyolProductManager(api_client)

def convert_lcwaikiki_to_trendyol(lcw_product):
    """Convert LC Waikiki product to Trendyol ProductData format"""
    from decimal import Decimal
    import re
    
    # Extract and clean product information
    product_code = None
    if hasattr(lcw_product, 'product_code') and lcw_product.product_code:
        product_code = re.sub(r'[^a-zA-Z0-9]', '', lcw_product.product_code)
    
    # Generate a unique barcode
    barcode = f"LCW{product_code or lcw_product.id}{int(time.time())}"
    barcode = re.sub(r'[^a-zA-Z0-9]', '', barcode)[:32]
    
    # Get the price with discount
    price = float(lcw_product.price or 0)
    sale_price = price
    if hasattr(lcw_product, 'discount_ratio') and lcw_product.discount_ratio and lcw_product.discount_ratio > 0:
        sale_price = price * (1 - (lcw_product.discount_ratio / 100))
    
    # Process images
    images = []
    if hasattr(lcw_product, 'image_urls') and lcw_product.image_urls:
        try:
            if isinstance(lcw_product.image_urls, str):
                img_list = json.loads(lcw_product.image_urls)
                for img in img_list:
                    if img.startswith('//'):
                        images.append(f"https:{img}")
                    elif not img.startswith('http'):
                        images.append(f"https://{img}")
                    else:
                        images.append(img)
        except Exception as e:
            logger.warning(f"Error processing images for product {lcw_product.id}: {str(e)}")
    
    # If no images found, use a default
    if not images and hasattr(lcw_product, 'image_url') and lcw_product.image_url:
        img = lcw_product.image_url
        if img.startswith('//'):
            images.append(f"https:{img}")
        elif not img.startswith('http'):
            images.append(f"https://{img}")
        else:
            images.append(img)
    
    # Get stock quantity
    quantity = 10  # Default value
    if hasattr(lcw_product, 'get_total_stock'):
        try:
            stock = lcw_product.get_total_stock()
            if stock and stock > 0:
                quantity = stock
        except Exception:
            pass
    
    # Create ProductData
    return ProductData(
        barcode=barcode,
        title=lcw_product.title or "LC Waikiki Product",
        product_main_id=product_code or barcode,
        brand_name="LC Waikiki",
        category_name=lcw_product.category or "Giyim",
        quantity=quantity,
        stock_code=product_code or barcode,
        price=price,
        sale_price=sale_price,
        description=lcw_product.description or lcw_product.title or "LC Waikiki Product Description",
        image_url=images[0] if images else "https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20224/5841125/l_20224-w4bi51z8-ct5_a.jpg",
        additional_images=images[1:] if len(images) > 1 else [],
        currency_type="TRY",
        vat_rate=18
    )