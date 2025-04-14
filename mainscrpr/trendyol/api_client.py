import requests
import json
import time
import re
import uuid
import base64
import logging
from urllib.parse import quote
from sentence_transformers import SentenceTransformer, util
from PyMultiDictionary import MultiDictionary
from functools import lru_cache
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Union, Any, Tuple
from collections import defaultdict

from django.utils import timezone

from .models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trendyol_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


TRENDYOL_API_BASE_URL = "https://api.trendyol.com/sapigw"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

@dataclass
class APIConfig:
    api_key: str
    api_secret: str
    seller_id: str
    base_url: str = TRENDYOL_API_BASE_URL
    
    def get_auth_token(self):
        """Generate base64 encoded auth token"""
        auth_string = f"{self.api_key}:{self.api_secret}"
        return base64.b64encode(auth_string.encode()).decode()


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
    cargo_company_id: int = 17
    currency_type: str = "TRY"
    dimensional_weight: int = 1
    attributes: Dict[str, Any] = None


class TrendyolAPI:
    """Base class for Trendyol API operations with retry mechanism"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {config.get_auth_token()}",
            "User-Agent": f"{self.config.seller_id} - SelfIntegration",
            "Content-Type": "application/json"
        })
        self.brands = BrandsAPI(self)
        self.categories = CategoriesAPI(self)
        self.products = ProductsAPI(self)
        self.inventory = InventoryAPI(self)
    
    def make_request(self, method: str, endpoint: str, data=None, params=None):
        """Generic request method with retry logic"""
        # Make sure endpoint starts with a slash
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
            
        # Remove any duplicate /integration prefix from the endpoint
        if endpoint.startswith('/integration') and 'integration' in self.config.base_url:
            endpoint = endpoint.replace('/integration', '', 1)
            
        url = f"{self.config.base_url.rstrip('/')}{endpoint}"
        timeout = DEFAULT_TIMEOUT
        
        for attempt in range(MAX_RETRIES):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=timeout)
                elif method.upper() == 'POST':
                    response = self.session.post(url, json=data, timeout=timeout)
                elif method.upper() == 'PUT':
                    response = self.session.put(url, json=data, timeout=timeout)
                elif method.upper() == 'DELETE':
                    response = self.session.delete(url, json=data, timeout=timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                
                try:
                    return response.json()
                except ValueError:
                    return {"message": response.text, "status": response.status_code}
                    
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
                    return {"error": True, "message": str(e), "details": f"Failed after {MAX_RETRIES} attempts"}
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                time.sleep(RETRY_DELAY * (attempt + 1))
        
        return {"error": True, "message": "Request failed after all retry attempts"}


class BrandsAPI:
    """Handles brand-related API operations"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
    
    def get_brands(self, page=0, size=1000):
        """Get all brands with pagination"""
        return self.api.make_request('GET', '/product/brands', params={'page': page, 'size': size})
    
    def search_brand_by_name(self, brand_name: str):
        """Search for a brand by name"""
        encoded_name = quote(brand_name)
        return self.api.make_request('GET', f'/product/brands/by-name?name={encoded_name}')


class CategoriesAPI:
    """Handles category-related API operations"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
    
    def get_categories(self):
        """Get all categories"""
        return self.api.make_request('GET', '/product/product-categories')
    
    def get_category_attributes(self, category_id: int):
        """Get attributes for a specific category"""
        return self.api.make_request('GET', f'/product/product-categories/{category_id}/attributes')


class ProductsAPI:
    """Handles product-related API operations"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
    
    def create_products(self, products_data: List[Dict[str, Any]]):
        """Create products on Trendyol"""
        supplier_id = self.api.config.seller_id
        
        # Validate required fields for each product
        for item in products_data:
            required_fields = [
                'barcode', 'title', 'productMainId', 'brandId', 'categoryId',
                'listPrice', 'salePrice', 'vatRate', 'stockCode'
            ]

            missing_fields = [
                field for field in required_fields
                if field not in item or item[field] is None
            ]

            if missing_fields:
                return {
                    "error": True,
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }
        
        payload = {"items": products_data}
        return self.api.make_request('POST', f'/product/sellers/{supplier_id}/products', data=payload)
    
    def get_products(self, approved=True, page=0, size=100):
        """Get all products with filtering and pagination"""
        supplier_id = self.api.config.seller_id
        params = {
            'approved': approved,
            'page': page,
            'size': size
        }
        return self.api.make_request('GET', f'/product/sellers/{supplier_id}/products', params=params)
    
    def get_batch_request_status(self, batch_id: str):
        """Check the status of a batch request"""
        supplier_id = self.api.config.seller_id
        return self.api.make_request('GET', f'/product/sellers/{supplier_id}/products/batch-requests/{batch_id}')
    
    def delete_product(self, product_id: str):
        """Delete a product by barcode or supplier product code"""
        supplier_id = self.api.config.seller_id
        return self.api.make_request('DELETE', f'/product/sellers/{supplier_id}/products/{product_id}')


class InventoryAPI:
    """Handles inventory-related API operations"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
    
    def update_inventory(self, inventory_data: List[Dict[str, Any]]):
        """Update product inventory"""
        supplier_id = self.api.config.seller_id
        payload = {"items": inventory_data}
        return self.api.make_request('POST', f'/product/sellers/{supplier_id}/products/inventory', data=payload)
    
    def update_price(self, price_data: List[Dict[str, Any]]):
        """Update product prices"""
        supplier_id = self.api.config.seller_id
        payload = {"items": price_data}
        return self.api.make_request('POST', f'/product/sellers/{supplier_id}/products/price', data=payload)


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
            data = self.api.categories.get_categories()
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise Exception("Failed to load categories. Please check your API credentials and try again.")
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id: int) -> Dict:
        """Get attributes for a specific category with caching"""
        try:
            data = self.api.categories.get_category_attributes(category_id)
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
            # Default fallback for LCWaikiki clothing
            if "giyim" in search_term.lower() or "elbise" in search_term.lower():
                return 2356  # Default ID for men's clothing
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
        
    def get_required_attributes(self, category_id: int) -> List[Dict[str, Any]]:
        """Generate attributes for a category with default values for required attributes"""
        attributes = []
        category_attrs = self.get_category_attributes(category_id)
        
        for attr in category_attrs.get('categoryAttributes', []):
            # Skip optional attributes without values
            if not attr.get('required', False) and not attr.get('attributeValues'):
                continue
                
            attribute = {
                "attributeId": attr['attribute']['id'],
                "attributeName": attr['attribute']['name']
            }
            
            if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                # Use first value as default
                attribute["attributeValueId"] = attr['attributeValues'][0]['id']
            elif attr.get('allowCustom'):
                # For custom attributes
                attribute["customAttributeValue"] = f"Default {attr['attribute']['name']}"
            else:
                continue
            
            attributes.append(attribute)
        
        return attributes


class TrendyolProductManager:
    """Handles product creation and management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.category_finder = TrendyolCategoryFinder(api_client)
    
    def get_brand_id(self, brand_name: str) -> int:
        """Find brand ID by name"""
        try:
            brands = self.api.brands.search_brand_by_name(brand_name)
            if isinstance(brands, list) and brands:
                return brands[0]['id']
                
            # Try with any available brand as fallback
            logger.warning(f"Brand not found: {brand_name}, trying to get any available brand from API")
            all_brands = self.api.brands.get_brands()
            if isinstance(all_brands, dict) and 'brands' in all_brands and all_brands['brands']:
                logger.info(f"Using first available brand: {all_brands['brands'][0]['name']}")
                return all_brands['brands'][0]['id']
                
            # If no brands found at all, raise an exception
            raise ValueError(f"No brands found in Trendyol API")
            
        except Exception as e:
            logger.error(f"Brand search failed for '{brand_name}': {str(e)}")
            raise ValueError(f"Brand search failed: {str(e)}")
    
    def lcwaikiki_to_product_data(self, lcw_product) -> ProductData:
        """Convert LCWaikiki product to ProductData"""
        if not lcw_product:
            return None
            
        try:
            # Extract and format product code
            product_code = None
            if hasattr(lcw_product, 'product_code') and lcw_product.product_code:
                product_code = re.sub(r'[^a-zA-Z0-9]', '', lcw_product.product_code)
                
            # Generate barcode
            barcode = f"LCW{product_code}" if product_code else f"LCW{lcw_product.id}{int(time.time())}"
            barcode = re.sub(r'[^a-zA-Z0-9]', '', barcode)
            barcode = barcode[:32]  # Cap length
            
            # Process price
            price = Decimal(lcw_product.price) if hasattr(lcw_product, 'price') and lcw_product.price else Decimal('0.00')
            sale_price = price
            
            if hasattr(lcw_product, 'discount_ratio') and lcw_product.discount_ratio and lcw_product.discount_ratio > 0:
                discount = Decimal(lcw_product.discount_ratio) / Decimal('100')
                sale_price = price * (Decimal('1.00') - discount)
                
            # Process images
            images = []
            if hasattr(lcw_product, 'images') and lcw_product.images:
                try:
                    if isinstance(lcw_product.images, str):
                        images = json.loads(lcw_product.images)
                    elif isinstance(lcw_product.images, list):
                        images = lcw_product.images
                        
                    # Clean and fix URLs
                    clean_images = []
                    for img in images:
                        if img and isinstance(img, str):
                            if not img.startswith(('http://', 'https://')):
                                img = f"https:{img}" if img.startswith('//') else f"https://{img}"
                            clean_images.append(img)
                    
                    images = clean_images
                except Exception as e:
                    logger.warning(f"Error processing images: {str(e)}")
            
            # Default image if none found
            if not images and hasattr(lcw_product, 'image_url') and lcw_product.image_url:
                images = [lcw_product.image_url]
                
            # Get quantity
            quantity = 10  # Default
            if hasattr(lcw_product, 'get_total_stock'):
                try:
                    stock = lcw_product.get_total_stock()
                    if stock and stock > 0:
                        quantity = min(stock, 20000)  # Trendyol max 20,000
                except Exception:
                    pass
                    
            # Get title and description
            title = lcw_product.title if hasattr(lcw_product, 'title') and lcw_product.title else ""
            title = " ".join(title.split())  # Normalize whitespace
            title = title[:100]  # Trendyol limit
            
            description = lcw_product.description if hasattr(lcw_product, 'description') and lcw_product.description else title
            
            # Create ProductData
            return ProductData(
                barcode=barcode,
                title=title,
                product_main_id=barcode,
                brand_name="LC Waikiki",  # Assume LC Waikiki for all products
                category_name=lcw_product.category if hasattr(lcw_product, 'category') and lcw_product.category else "Giyim",
                quantity=quantity,
                stock_code=barcode,
                price=float(price),
                sale_price=float(sale_price),
                description=description,
                image_url=images[0] if images else "",
                additional_images=images[1:] if len(images) > 1 else []
            )
            
        except Exception as e:
            logger.error(f"Error converting LCWaikiki product: {str(e)}")
            return None
    
    def create_product(self, product_data: ProductData) -> str:
        """Create a new product on Trendyol"""
        try:
            category_id = self.category_finder.find_best_category(product_data.category_name)
            brand_id = self.get_brand_id(product_data.brand_name)
            attributes = self._get_required_attributes(category_id)
            
            images = [{"url": product_data.image_url}]
            if product_data.additional_images:
                for url in product_data.additional_images:
                    if url:
                        images.append({"url": url})
            
            payload = {
                "barcode": product_data.barcode,
                "title": product_data.title,
                "productMainId": product_data.product_main_id,
                "brandId": brand_id,
                "categoryId": category_id,
                "quantity": product_data.quantity,
                "stockCode": product_data.stock_code,
                "dimensionalWeight": product_data.dimensional_weight,
                "description": product_data.description,
                "currencyType": product_data.currency_type,
                "listPrice": product_data.price,
                "salePrice": product_data.sale_price,
                "vatRate": product_data.vat_rate,
                "cargoCompanyId": product_data.cargo_company_id,
                "images": images,
                "attributes": attributes
            }
            
            # Add custom attributes if provided
            if product_data.attributes:
                for attr_id, value in product_data.attributes.items():
                    for i, attr in enumerate(payload["attributes"]):
                        if str(attr["attributeId"]) == str(attr_id):
                            payload["attributes"][i]["attributeValueId"] = value
                            break
            
            logger.info("Submitting product creation request...")
            response = self.api.products.create_products([payload])
            
            if response.get("error"):
                logger.error(f"Product creation failed: {response}")
                return None
                
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Product creation failed: {str(e)}")
            return None
    
    def check_batch_status(self, batch_id: str) -> Dict:
        """Check the status of a batch operation"""
        try:
            return self.api.products.get_batch_request_status(batch_id)
        except Exception as e:
            logger.error(f"Failed to check batch status: {str(e)}")
            return {"error": True, "message": str(e)}
    
    def _get_required_attributes(self, category_id: int) -> List[Dict]:
        """Generate required attributes for a category"""
        return self.category_finder.get_required_attributes(category_id)


# Helper functions for compatibility with existing code
def get_api_client():
    """Get a TrendyolAPI instance using saved configuration"""
    try:
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            logger.error("No active Trendyol API configuration found")
            return None
            
        api_config = APIConfig(
            api_key=config.api_key,
            api_secret=config.api_secret,
            seller_id=config.supplier_id,
            base_url=config.base_url
        )
        return TrendyolAPI(api_config)
    except Exception as e:
        logger.error(f"Error creating API client: {str(e)}")
        return None


def create_trendyol_product(product: TrendyolProduct) -> Optional[str]:
    """Create a product on Trendyol using the new API structure"""
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
        # Convert TrendyolProduct to ProductData
        product_manager = TrendyolProductManager(client)
        
        product_data = ProductData(
            barcode=product.barcode,
            title=product.title,
            product_main_id=product.product_main_id or product.barcode,
            brand_name=product.brand_name or "LC Waikiki",
            category_name=product.category_name or "Giyim",
            quantity=product.quantity or 10,
            stock_code=product.stock_code or product.barcode,
            price=float(product.price or 0),
            sale_price=float(product.price or 0),
            description=product.description or product.title,
            image_url=product.image_url or "",
            vat_rate=10,
            cargo_company_id=17,
            currency_type="TRY",
            dimensional_weight=1,
            attributes=product.attributes if isinstance(product.attributes, dict) else 
                      json.loads(product.attributes) if isinstance(product.attributes, str) else None
        )
        
        # Add additional images if available
        if product.additional_images:
            if isinstance(product.additional_images, list):
                product_data.additional_images = product.additional_images
            elif isinstance(product.additional_images, str):
                try:
                    product_data.additional_images = json.loads(product.additional_images)
                except json.JSONDecodeError:
                    pass
        
        # Create product
        batch_id = product_manager.create_product(product_data)
        
        if not batch_id:
            error_message = "Failed to create product on Trendyol"
            logger.error(f"{error_message} for product ID {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None
        
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


def check_product_batch_status(product: TrendyolProduct) -> str:
    """Check the status of a product batch on Trendyol"""
    if not product.batch_id:
        product.batch_status = 'failed'
        product.status_message = "No batch ID available to check status"
        product.save()
        return 'failed'
    
    client = get_api_client()
    if not client:
        product.batch_status = 'failed'
        product.status_message = "No active Trendyol API configuration found"
        product.save()
        return 'failed'
    
    try:
        product_manager = TrendyolProductManager(client)
        response = product_manager.check_batch_status(product.batch_id)
        
        if not response:
            product.batch_status = 'failed'
            product.status_message = "Failed to check batch status: No response from API"
            product.save()
            return 'failed'
        
        # Parse response to determine status
        status = response.get('status')
        
        if status == 'DONE':
            product.batch_status = 'completed'
            product.status_message = "Product creation completed successfully"
        elif status == 'ERROR':
            product.batch_status = 'failed'
            product.status_message = response.get('error', 'Unknown error')
        elif status == 'WAITING' or status == 'PROCESSING':
            product.batch_status = 'processing'
            product.status_message = "Product creation in progress"
        else:
            product.batch_status = 'unknown'
            product.status_message = f"Unknown batch status: {status}"
        
        product.last_check_time = timezone.now()
        product.save()
        
        return product.batch_status
    except Exception as e:
        error_message = f"Error checking batch status: {str(e)}"
        logger.error(f"{error_message} for product ID {product.id}")
        product.batch_status = 'failed'
        product.status_message = error_message
        product.save()
        return 'failed'


def find_best_category_match(product: TrendyolProduct) -> Optional[int]:
    """Find the best matching category for a product"""
    client = get_api_client()
    if not client:
        logger.error("No API client available to find category match")
        return None
    
    try:
        category_finder = TrendyolCategoryFinder(client)
        if product.category_name:
            return category_finder.find_best_category(product.category_name)
        return None
    except Exception as e:
        logger.error(f"Error finding category match: {str(e)}")
        return None


def find_best_brand_match(product: TrendyolProduct) -> Optional[int]:
    """Find the best matching brand for a product"""
    client = get_api_client()
    if not client:
        logger.error("No API client available to find brand match")
        raise ValueError("No API client available")
    
    try:
        product_manager = TrendyolProductManager(client)
        if product.brand_name:
            return product_manager.get_brand_id(product.brand_name)
            
        # If no brand name specified, get first available brand from API
        all_brands = client.brands.get_brands()
        if isinstance(all_brands, dict) and 'brands' in all_brands and all_brands['brands']:
            logger.info(f"No brand name specified, using first available brand: {all_brands['brands'][0]['name']}")
            return all_brands['brands'][0]['id']
            
        raise ValueError("No brand name specified and no brands available in API")
    except Exception as e:
        logger.error(f"Error finding brand match: {str(e)}")
        raise ValueError(f"Cannot find brand match: {str(e)}")


def lcwaikiki_to_trendyol_product(lcw_product) -> Optional[TrendyolProduct]:
    """Convert an LCWaikiki product to a Trendyol product"""
    if not lcw_product:
        return None
    
    try:
        # Check if a Trendyol product already exists for this LCWaikiki product
        trendyol_product = TrendyolProduct.objects.filter(lcwaikiki_product=lcw_product).first()
        
        # If not found, create a new one
        if not trendyol_product:
            client = get_api_client()
            if not client:
                logger.error("No API client available to convert product")
                return None
                
            product_manager = TrendyolProductManager(client)
            product_data = product_manager.lcwaikiki_to_product_data(lcw_product)
            
            if not product_data:
                logger.error(f"Failed to convert LCWaikiki product {lcw_product.id}")
                return None
                
            # Create new TrendyolProduct
            trendyol_product = TrendyolProduct(
                lcwaikiki_product=lcw_product,
                barcode=product_data.barcode,
                title=product_data.title,
                product_main_id=product_data.product_main_id,
                brand_name=product_data.brand_name,
                category_name=product_data.category_name,
                quantity=product_data.quantity,
                stock_code=product_data.stock_code,
                price=product_data.price,
                description=product_data.description,
                image_url=product_data.image_url,
                additional_images=json.dumps(product_data.additional_images) if product_data.additional_images else None
            )
            
            # Save the new product
            trendyol_product.save()
        
        return trendyol_product
    except Exception as e:
        logger.error(f"Error converting LCWaikiki product {lcw_product.id}: {str(e)}")
        return None