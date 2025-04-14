import requests
import json
from urllib.parse import quote
from sentence_transformers import SentenceTransformer, util
from collections import defaultdict
import uuid
from PyMultiDictionary import MultiDictionary
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass
import logging
from functools import lru_cache
import time
import re
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
    api_secret: str
    seller_id: str
    base_url: str = TRENDYOL_API_BASE_URL

@dataclass
class ProductData:
    barcode: str
    title: str
    product_main_id: str
    brand_id: int
    category_id: int
    quantity: int
    stock_code: str
    price: float
    description: str
    image_url: str
    additional_images: List[str] = None
    attributes: List[Dict] = None
    vat_rate: int = 10
    cargo_company_id: int = 10
    currency_type: str = "TRY"
    dimensional_weight: int = 1

class TrendyolAPI:
    """Base class for Trendyol API operations with retry mechanism"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.session = requests.Session()
        
        # Combine API key and secret for basic auth token
        import base64
        auth_token = base64.b64encode(f"{self.config.api_key}:{self.config.api_secret}".encode()).decode()
        
        self.session.headers.update({
            "Authorization": f"Basic {auth_token}",
            "User-Agent": f"{self.config.seller_id} - SelfIntegration",
            "Content-Type": "application/json"
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Generic request method with retry logic"""
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
        
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request params: {kwargs.get('params')}")
        logger.debug(f"Request body: {kwargs.get('json')}")
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, **kwargs)
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                
                # Log detailed error information
                if response.status_code >= 400:
                    logger.error(f"{response.status_code} ERROR: {response.text}")
                    
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
    
    def delete(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        return self._make_request('DELETE', endpoint, params=params)

class TrendyolCategoryFinder:
    """Handles category discovery and attribute management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        # Initialize if sentence-transformers is available
        try:
            self.model = SentenceTransformer('emrecan/bert-base-turkish-cased-mean-nli-stsb-tr')
        except Exception as e:
            logger.warning(f"Could not initialize SentenceTransformer: {str(e)}")
            self.model = None
            
        # Initialize if PyMultiDictionary is available
        try:
            self.dictionary = MultiDictionary()
        except Exception as e:
            logger.warning(f"Could not initialize MultiDictionary: {str(e)}")
            self.dictionary = None
            
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
        
        if self.dictionary:
            try:
                synonyms = self.dictionary.synonym('tr', search_term.lower())
                search_terms.update(synonyms[:5])
            except Exception as e:
                logger.debug(f"Couldn't fetch synonyms: {str(e)}")
        
        matches = []
        for term in search_terms:
            matches.extend(self._find_matches_for_term(term, categories))
        
        # Deduplicate while preserving order
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
        """Select best match using semantic similarity or fallback to string matching"""
        if self.model:
            # Use semantic similarity with sentence-transformers
            search_embedding = self.model.encode(search_term, convert_to_tensor=True)
            
            for candidate in candidates:
                candidate_embedding = self.model.encode(candidate['name'], convert_to_tensor=True)
                candidate['similarity'] = util.cos_sim(search_embedding, candidate_embedding).item()
            
            candidates_sorted = sorted(candidates, key=lambda x: x['similarity'], reverse=True)
        else:
            # Fallback to simple string matching
            import difflib
            for candidate in candidates:
                candidate['similarity'] = difflib.SequenceMatcher(None, search_term.lower(), 
                                                                 candidate['name'].lower()).ratio()
            
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
        
        if self.model:
            # Use semantic similarity with sentence-transformers
            search_embedding = self.model.encode(search_term, convert_to_tensor=True)
            for cat in leaf_categories:
                cat_embedding = self.model.encode(cat['name'], convert_to_tensor=True)
                cat['similarity'] = util.cos_sim(search_embedding, cat_embedding).item()
        else:
            # Fallback to simple string matching
            import difflib
            for cat in leaf_categories:
                cat['similarity'] = difflib.SequenceMatcher(None, search_term.lower(), 
                                                           cat['name'].lower()).ratio()
        
        sorted_cats = sorted(leaf_categories, key=lambda x: x['similarity'], reverse=True)
        
        suggestions = []
        for i, cat in enumerate(sorted_cats[:top_n], 1):
            suggestions.append(f"{i}. {cat['name']} (Similarity: {cat['similarity']:.2f}, ID: {cat['id']})")
        
        return "\n".join(suggestions)
    
    def get_required_attributes_for_category(self, category_id: int) -> List[Dict]:
        """Get required attributes for a category"""
        attributes_data = self.get_category_attributes(category_id)
        required_attributes = []
        
        for attr in attributes_data.get('categoryAttributes', []):
            if attr.get('required'):
                required_attributes.append({
                    'id': attr['attribute']['id'],
                    'name': attr['attribute']['name'],
                    'allowCustom': attr.get('allowCustom', False),
                    'values': attr.get('attributeValues', [])
                })
        
        return required_attributes

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
            # Fallback to LC Waikiki brand ID if specifically requested
            if brand_name.lower() in ["lcw", "lc waikiki", "lcwaikiki"]:
                logger.warning(f"Brand not found: {brand_name}, using fallback LC Waikiki ID: 7651")
                return 7651
            raise ValueError(f"Brand not found: {brand_name}")
        except Exception as e:
            logger.error(f"Brand search failed for '{brand_name}': {str(e)}")
            if brand_name.lower() in ["lcw", "lc waikiki", "lcwaikiki"]:
                logger.warning(f"Using fallback LC Waikiki ID: 7651")
                return 7651
            raise
    
    def create_product(self, product_data: ProductData) -> str:
        """Create a new product on Trendyol"""
        try:
            # Use provided category_id and brand_id from ProductData
            category_id = product_data.category_id
            brand_id = product_data.brand_id
            
            # Get attributes if they haven't been provided
            attributes = product_data.attributes or []
            if not attributes:
                attributes = self._get_required_attributes(category_id)
            
            payload = self._build_product_payload(product_data, attributes)
            logger.info(f"Submitting product creation request for {product_data.title}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            response = self.api.post(
                f"product/sellers/{self.api.config.seller_id}/products", 
                payload
            )
            
            logger.debug(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)}")
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Product creation failed: {str(e)}")
            raise
    
    def check_batch_status(self, batch_id: str) -> Dict:
        """Check the status of a batch operation"""
        try:
            return self.api.get(
                f"product/sellers/{self.api.config.seller_id}/products/batch-requests/{batch_id}"
            )
        except Exception as e:
            logger.error(f"Failed to check batch status: {str(e)}")
            raise
    
    def update_price(self, product_id: str, price: float, sale_price: Optional[float] = None) -> str:
        """Update product price"""
        try:
            payload = {
                "items": [{
                    "id": product_id,
                    "price": price
                }]
            }
            
            if sale_price is not None:
                payload["items"][0]["salePrice"] = sale_price
            
            response = self.api.put(
                f"product/sellers/{self.api.config.seller_id}/products/price", 
                payload
            )
            
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Price update failed for product {product_id}: {str(e)}")
            raise
    
    def update_stock(self, product_id: str, quantity: int) -> str:
        """Update product stock"""
        try:
            payload = {
                "items": [{
                    "id": product_id,
                    "quantity": quantity
                }]
            }
            
            response = self.api.put(
                f"product/sellers/{self.api.config.seller_id}/products/stock", 
                payload
            )
            
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Stock update failed for product {product_id}: {str(e)}")
            raise
    
    def _build_product_payload(self, product: ProductData, attributes: List[Dict]) -> Dict:
        """Construct the complete product payload"""
        images = []
        
        # Add main image
        images.append({"url": product.image_url})
        
        # Add additional images if provided
        if product.additional_images:
            for img_url in product.additional_images:
                images.append({"url": img_url})
        
        return {
            "items": [{
                "barcode": product.barcode,
                "title": product.title,
                "productMainId": product.product_main_id,
                "brandId": product.brand_id,
                "categoryId": product.category_id,
                "quantity": product.quantity,
                "stockCode": product.stock_code,
                "dimensionalWeight": product.dimensional_weight,
                "description": product.description,
                "currencyType": product.currency_type,
                "listPrice": float(product.price),
                "salePrice": float(product.price),  # Using same as list price if no sale price provided
                "vatRate": product.vat_rate,
                "cargoCompanyId": product.cargo_company_id,
                "images": images,
                "attributes": attributes
            }],
            # "batchRequestId": str(uuid.uuid4()),
            # "hasMultiSupplier": False,
            # "supplierId": int(self.api.config.seller_id)
        }
    
    def _get_required_attributes(self, category_id: int) -> List[Dict]:
        """Generate the required attributes for a category"""
        attributes = []
        required_attrs = self.category_finder.get_required_attributes_for_category(category_id)
        
        for attr in required_attrs:
            # Handle for color attribute (ID 348)
            if attr['id'] == 348:  # Color attribute
                # Default to first color value if available
                if attr['values']:
                    attribute = {
                        "attributeId": attr['id'],
                        "attributeValueId": attr['values'][0]['id']
                    }
                    attributes.append(attribute)
            # Handle other required attributes
            elif attr['values'] and not attr['allowCustom']:
                attribute = {
                    "attributeId": attr['id'],
                    "attributeValueId": attr['values'][0]['id']
                }
                attributes.append(attribute)
            elif attr['allowCustom']:
                attribute = {
                    "attributeId": attr['id'],
                    "customAttributeValue": f"{attr['name']}"
                }
                attributes.append(attribute)
        
        return attributes

def get_api_client():
    """Get a configured API client using environment variables or defaults"""
    from django.conf import settings
    
    # Get API config from settings
    api_key = getattr(settings, 'TRENDYOL_API_KEY', None)
    api_secret = getattr(settings, 'TRENDYOL_API_SECRET', None)
    seller_id = getattr(settings, 'TRENDYOL_SELLER_ID', None)
    base_url = getattr(settings, 'TRENDYOL_API_BASE_URL', TRENDYOL_API_BASE_URL)
    
    # Check if all required settings are present
    if not all([api_key, api_secret, seller_id]):
        from django.db import models
        # Try to get from database
        try:
            from trendyol.models import TrendyolAPIConfig
            config = TrendyolAPIConfig.objects.filter(is_active=True).first()
            if config:
                api_key = config.api_key
                api_secret = config.api_secret
                seller_id = config.seller_id
                base_url = config.base_url or TRENDYOL_API_BASE_URL
        except Exception as e:
            logger.error(f"Failed to get API config from database: {str(e)}")
    
    # Check if we have the necessary config
    if not all([api_key, api_secret, seller_id]):
        logger.error("Missing required Trendyol API configuration")
        return None
    
    config = APIConfig(
        api_key=api_key,
        api_secret=api_secret,
        seller_id=seller_id,
        base_url=base_url
    )
    
    return TrendyolAPI(config)

def get_product_manager():
    """Get a configured product manager"""
    api_client = get_api_client()
    if not api_client:
        return None
    
    return TrendyolProductManager(api_client)

# Add Django model conversion helper
def lcwaikiki_to_trendyol_product(lcw_product):
    """Convert LCWaikiki product to Trendyol ProductData"""
    try:
        from django.db import models
        from trendyol.models import TrendyolProduct, TrendyolCategory, TrendyolBrand
        from decimal import Decimal
        
        # Early validation
        if not lcw_product:
            logger.error("Cannot convert None to TrendyolProduct")
            return None
        
        # Extract product code
        product_code = None
        if hasattr(lcw_product, 'product_code') and lcw_product.product_code:
            product_code = re.sub(r'[^a-zA-Z0-9]', '', lcw_product.product_code)
        
        # Generate barcode
        barcode = None
        if product_code:
            barcode = f"LCW{product_code}"
        else:
            timestamp = int(time.time())
            barcode = f"LCW{lcw_product.id}{timestamp}"
        
        # Format barcode
        barcode = re.sub(r'[^a-zA-Z0-9]', '', barcode)[:32]
        
        # Get price
        price = getattr(lcw_product, 'price', Decimal('0.00'))
        if hasattr(lcw_product, 'discount_ratio') and lcw_product.discount_ratio and lcw_product.discount_ratio > 0:
            discount = lcw_product.discount_ratio / 100
            price = price * (1 - Decimal(str(discount)))
        
        # Get quantity/stock
        quantity = 10  # Default to 10 for better Trendyol acceptance
        if hasattr(lcw_product, 'get_total_stock'):
            try:
                stock = lcw_product.get_total_stock()
                if stock and stock > 0:
                    quantity = stock
            except Exception as e:
                logger.warning(f"Error getting total stock: {str(e)}")
        
        # Get images
        images = []
        try:
            if hasattr(lcw_product, 'images') and lcw_product.images:
                if isinstance(lcw_product.images, str):
                    # Try to decode JSON
                    img_data = json.loads(lcw_product.images)
                    if isinstance(img_data, list):
                        images = img_data
                        # Ensure https:// prefix
                        for i, img in enumerate(images):
                            if img.startswith('//'):
                                images[i] = f"https:{img}"
                            elif not (img.startswith('http://') or img.startswith('https://')):
                                images[i] = f"https://{img}"
                elif isinstance(lcw_product.images, list):
                    images = lcw_product.images
        except Exception as e:
            logger.warning(f"Error processing images: {str(e)}")
        
        # If no images, use a default placeholder
        if not images:
            logger.warning(f"No images found for product {lcw_product.id}")
            return None
        
        # Get brand ID
        brand_id = None
        product_manager = get_product_manager()
        if product_manager:
            try:
                brand_id = product_manager.get_brand_id("LC Waikiki")
            except Exception as e:
                logger.error(f"Error finding brand: {str(e)}")
                brand_id = 7651  # Default LCW brand ID
        else:
            brand_id = 7651  # Default LCW brand ID
        
        # Get category ID
        category_id = None
        if hasattr(lcw_product, 'category') and lcw_product.category:
            category_name = lcw_product.category
            try:
                # Try to find matching category
                if product_manager and product_manager.category_finder:
                    category_id = product_manager.category_finder.find_best_category(category_name)
            except Exception as e:
                logger.error(f"Error finding category: {str(e)}")
                # Try to find a default category in DB
                try:
                    default_category = TrendyolCategory.objects.filter(
                        name__icontains="Giyim", is_active=True).first()
                    if default_category:
                        category_id = default_category.category_id
                        logger.warning(f"Using default category: {default_category.name} (ID: {category_id})")
                except Exception as db_e:
                    logger.error(f"Error finding default category: {str(db_e)}")
        
        if not category_id:
            # Use a common default category for clothing if all else fails
            category_id = 411  # Default to a common clothing category
            logger.warning(f"Using hardcoded default category ID: {category_id}")
        
        # Create product data
        product_data = ProductData(
            barcode=barcode,
            title=getattr(lcw_product, 'title', "LC Waikiki Product"),
            product_main_id=product_code or barcode,
            brand_id=brand_id,
            category_id=category_id,
            quantity=quantity,
            stock_code=product_code or barcode,
            price=float(price),
            description=getattr(lcw_product, 'description', getattr(lcw_product, 'title', "LC Waikiki Product")),
            image_url=images[0],
            additional_images=images[1:] if len(images) > 1 else [],
            attributes=[]  # Will be populated by the product manager
        )
        
        return product_data
        
    except Exception as e:
        logger.error(f"Error converting LCWaikiki to Trendyol: {str(e)}")
        logger.exception(e)
        return None


def send_lcwaikiki_to_trendyol(lcw_product, max_retries=3, retry_delay=1):
    """
    Send an LCWaikiki product to Trendyol
    
    Args:
        lcw_product: LCWaikiki product model instance
        max_retries: Maximum number of retries for API requests
        retry_delay: Delay in seconds between retries
        
    Returns:
        Tuple (success, message, batch_id): 
            - success: Boolean indicating success
            - message: Status message
            - batch_id: Trendyol batch ID if successful, None otherwise
    """
    if not lcw_product:
        return False, "No product provided", None
        
    try:
        # Create Trendyol product data from LCWaikiki product
        logger.info(f"Converting LCWaikiki product {lcw_product.id} to Trendyol format")
        product_data = lcwaikiki_to_trendyol_product(lcw_product)
        
        if not product_data:
            logger.error(f"Failed to convert LCWaikiki product {lcw_product.id} to Trendyol format")
            return False, "Failed to convert product to Trendyol format", None
            
        # Get product manager
        product_manager = get_product_manager()
        if not product_manager:
            logger.error("Failed to initialize product manager")
            return False, "Failed to initialize Trendyol API", None
            
        # Ensure product has required attributes, especially color
        if not product_data.attributes:
            try:
                # Get required attributes
                logger.info(f"Getting required attributes for category {product_data.category_id}")
                required_attributes = product_manager.category_finder.get_required_attributes_for_category(product_data.category_id)
                
                # Check if color is required
                color_attribute = next((attr for attr in required_attributes if attr['name'].lower() == 'renk'), None)
                
                if color_attribute:
                    logger.info("Adding color attribute")
                    # Try to get color from LCWaikiki product
                    color_value = getattr(lcw_product, 'color', None)
                    if color_value:
                        # Find matching color value
                        color_id = None
                        for value in color_attribute.get('values', []):
                            if color_value.lower() in value['name'].lower():
                                color_id = value['id']
                                break
                                
                        if color_id:
                            product_data.attributes.append({
                                'attributeId': color_attribute['id'],
                                'attributeValueId': color_id
                            })
                        else:
                            # Use default attribute ID 348 for color
                            logger.warning(f"Color '{color_value}' not found in values, using attribute ID 348")
                            product_data.attributes.append({
                                'attributeId': 348,
                                'customAttributeValue': color_value
                            })
            except Exception as e:
                logger.error(f"Error getting required attributes: {str(e)}")
                # Continue without attributes
        
        # Create or update the Trendyol product
        from trendyol.models import TrendyolProduct
        from django.db import transaction
        
        with transaction.atomic():
            # Check if product already exists
            trendyol_product = TrendyolProduct.objects.filter(
                lcwaikiki_product=lcw_product
            ).first()
            
            if not trendyol_product:
                # Create new TrendyolProduct instance
                trendyol_product = TrendyolProduct(
                    lcwaikiki_product=lcw_product,
                    barcode=product_data.barcode,
                    title=product_data.title,
                    product_main_id=product_data.product_main_id,
                    stock_code=product_data.stock_code,
                    brand_id=product_data.brand_id,
                    brand_name="LC Waikiki",
                    category_id=product_data.category_id,
                    price=product_data.price,
                    quantity=product_data.quantity,
                    description=product_data.description,
                    image_url=product_data.image_url,
                    additional_images=product_data.additional_images,
                    attributes=product_data.attributes,
                    vat_rate=product_data.vat_rate,
                    currency_type=product_data.currency_type,
                    batch_status="pending"
                )
            else:
                # Update existing TrendyolProduct
                trendyol_product.title = product_data.title
                trendyol_product.barcode = product_data.barcode
                trendyol_product.product_main_id = product_data.product_main_id
                trendyol_product.stock_code = product_data.stock_code
                trendyol_product.brand_id = product_data.brand_id
                trendyol_product.brand_name = "LC Waikiki"
                trendyol_product.category_id = product_data.category_id
                trendyol_product.price = product_data.price
                trendyol_product.quantity = product_data.quantity
                trendyol_product.description = product_data.description
                trendyol_product.image_url = product_data.image_url
                trendyol_product.additional_images = product_data.additional_images
                trendyol_product.attributes = product_data.attributes
                trendyol_product.vat_rate = product_data.vat_rate
                trendyol_product.currency_type = product_data.currency_type
                trendyol_product.batch_status = "pending"
            
            # Save the product
            trendyol_product.save()
            
            # Send to Trendyol API
            for attempt in range(max_retries):
                try:
                    logger.info(f"Sending product {trendyol_product.title} to Trendyol (attempt {attempt+1}/{max_retries})")
                    batch_id = product_manager.create_product(product_data)
                    
                    if batch_id:
                        # Update batch information
                        trendyol_product.batch_id = batch_id
                        trendyol_product.batch_status = "processing"
                        trendyol_product.status_message = "Product sent to Trendyol, waiting for processing"
                        trendyol_product.save()
                        
                        # Create batch request record
                        from trendyol.models import TrendyolBatchRequest
                        batch_request, created = TrendyolBatchRequest.objects.get_or_create(
                            batch_id=batch_id,
                            defaults={
                                'operation_type': 'create',
                                'status': 'processing',
                                'status_message': 'Batch submitted to Trendyol',
                                'items_count': 1
                            }
                        )
                        
                        # Link batch request to product
                        trendyol_product.batch_request = batch_request
                        trendyol_product.save()
                        
                        logger.info(f"Successfully sent product {trendyol_product.title} to Trendyol with batch ID {batch_id}")
                        return True, "Product successfully sent to Trendyol", batch_id
                    else:
                        logger.error(f"Failed to get batch ID for product {trendyol_product.title}")
                        time.sleep(retry_delay * (attempt + 1))
                except Exception as e:
                    logger.error(f"Error sending product {trendyol_product.title} to Trendyol: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                    else:
                        # Update error status
                        trendyol_product.batch_status = "failed"
                        trendyol_product.status_message = f"Error: {str(e)}"
                        trendyol_product.save()
                        return False, f"Error sending product to Trendyol: {str(e)}", None
            
            # If we get here, all retries failed
            trendyol_product.batch_status = "failed"
            trendyol_product.status_message = "All retry attempts failed"
            trendyol_product.save()
            return False, "Failed to send product to Trendyol after multiple attempts", None
    
    except Exception as e:
        logger.error(f"Error in send_lcwaikiki_to_trendyol: {str(e)}")
        logger.exception(e)
        return False, f"Error: {str(e)}", None