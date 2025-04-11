import requests
import json
import uuid
import logging
from urllib.parse import quote
from django.utils import timezone
from collections import defaultdict
import time

from .models import TrendyolAPIConfig, TrendyolProduct, TrendyolBrand, TrendyolCategory

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1


class TrendyolAPI:
    """Base class for Trendyol API operations with retry mechanism"""
    
    def __init__(self, config: TrendyolAPIConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {self.config.api_key}:{self.config.api_secret}",
            "User-Agent": f"{self.config.seller_id} - SelfIntegration",
            "Content-Type": "application/json"
        })
    
    def _make_request(self, method, endpoint, **kwargs):
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
    
    def get(self, endpoint, params=None):
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint, data):
        return self._make_request('POST', endpoint, json=data)


class TrendyolCategoryFinder:
    """Handles category discovery and attribute management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
    
    @property
    def category_cache(self):
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self):
        """Fetch all categories from Trendyol API"""
        try:
            data = self.api.get("product/product-categories")
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise Exception("Failed to load categories. Please check your API credentials and try again.")
    
    def get_category_attributes(self, category_id):
        """Get attributes for a specific category with caching"""
        if category_id in self._attribute_cache:
            return self._attribute_cache[category_id]
            
        try:
            data = self.api.get(f"product/product-categories/{category_id}/attributes")
            self._attribute_cache[category_id] = data
            return data
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            raise Exception(f"Failed to load attributes for category {category_id}")
    
    def find_best_category(self, search_term):
        """Find the most relevant category for a given search term"""
        try:
            categories = self.category_cache
            if not categories:
                raise ValueError("Empty category list received from API")
            
            # Store matching categories here
            all_matches = []
            
            # Find exact matches and close matches by name
            for category in self._search_categories(categories, search_term.lower()):
                all_matches.append(category)
            
            # If we found exact matches, use the first one
            for match in all_matches:
                if match['name'].lower() == search_term.lower():
                    return match['id']
            
            # Otherwise, use the first match (if any)
            if all_matches:
                return all_matches[0]['id']
            
            # If no matches found, get all leaf categories for fallback
            leaf_categories = []
            self._collect_leaf_categories(categories, leaf_categories)
            
            # Attempt to find a fallback match
            for category in leaf_categories:
                if "clothing" in category['name'].lower() or "apparel" in category['name'].lower():
                    logger.warning(f"Using fallback category for '{search_term}': {category['name']}")
                    return category['id']
            
            # Last resort: use the first leaf category
            if leaf_categories:
                logger.warning(f"Using first leaf category for '{search_term}': {leaf_categories[0]['name']}")
                return leaf_categories[0]['id']
            
            raise ValueError(f"No category match found for '{search_term}'")
            
        except Exception as e:
            logger.error(f"Category search failed for '{search_term}': {str(e)}")
            raise
    
    def _search_categories(self, categories, search_term):
        """Recursively search categories for matching terms"""
        matches = []
        
        for category in categories:
            # Check if this category matches
            if search_term in category['name'].lower():
                matches.append(category)
            
            # Search subcategories (if any)
            if 'subCategories' in category and category['subCategories']:
                sub_matches = self._search_categories(category['subCategories'], search_term)
                matches.extend(sub_matches)
        
        return matches
    
    def _collect_leaf_categories(self, categories, result):
        """Recursively collect leaf categories (those without subcategories)"""
        for category in categories:
            if not category.get('subCategories'):
                result.append(category)
            else:
                self._collect_leaf_categories(category['subCategories'], result)
    
    def get_sample_attributes(self, category_id):
        """Generate sample attributes for a category"""
        attributes = []
        try:
            category_attrs = self.get_category_attributes(category_id)
            
            for attr in category_attrs.get('categoryAttributes', []):
                # Skip attributes with empty attributeValues array when custom values are not allowed
                if not attr.get('attributeValues') and not attr.get('allowCustom'):
                    continue
                    
                attribute = {
                    "attributeId": attr['attribute']['id'],
                    "attributeName": attr['attribute']['name']
                }
                
                if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                    if not attr.get('allowCustom'):
                        attribute["attributeValueId"] = attr['attributeValues'][0]['id']
                        attribute["attributeValue"] = attr['attributeValues'][0]['name']
                    else:
                        attribute["customAttributeValue"] = f"Sample {attr['attribute']['name']}"
                elif attr.get('allowCustom'):
                    attribute["customAttributeValue"] = f"Sample {attr['attribute']['name']}"
                else:
                    continue
                
                attributes.append(attribute)
                
            return attributes
        except Exception as e:
            logger.error(f"Error getting sample attributes: {str(e)}")
            return []


class TrendyolProductManager:
    """Handles product creation and management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.category_finder = TrendyolCategoryFinder(api_client)
    
    def get_brand_id(self, brand_name):
        """Find brand ID by name"""
        encoded_name = quote(brand_name)
        try:
            brands = self.api.get(f"product/brands/by-name?name={encoded_name}")
            if isinstance(brands, list) and brands:
                brand_id = brands[0]['id']
                
                # Store brand in the database
                TrendyolBrand.objects.update_or_create(
                    brand_id=brand_id,
                    defaults={'name': brands[0]['name']}
                )
                
                return brand_id
                
            raise ValueError(f"Brand not found: {brand_name}")
        except Exception as e:
            logger.error(f"Brand search failed for '{brand_name}': {str(e)}")
            raise
    
    def create_product(self, product_data):
        """Create a new product on Trendyol"""
        try:
            # Find category
            if not product_data.category_id:
                category_id = self.category_finder.find_best_category(product_data.category_name)
                product_data.category_id = category_id
            else:
                category_id = product_data.category_id
            
            # Find brand
            if not product_data.brand_id:
                brand_id = self.get_brand_id(product_data.brand_name)
                product_data.brand_id = brand_id
            else:
                brand_id = product_data.brand_id
            
            # Get attributes if needed
            if not product_data.attributes:
                attributes = self.category_finder.get_sample_attributes(category_id)
                product_data.attributes = attributes
            else:
                attributes = product_data.attributes
            
            # Build payload
            payload = {
                "items": [{
                    "barcode": product_data.barcode,
                    "title": product_data.title,
                    "productMainId": product_data.product_main_id,
                    "brandId": brand_id,
                    "categoryId": category_id,
                    "quantity": product_data.quantity,
                    "stockCode": product_data.stock_code,
                    "description": product_data.description,
                    "currencyType": product_data.currency_type,
                    "listPrice": float(product_data.price) + 10,  # Add margin for list price
                    "salePrice": float(product_data.price),
                    "vatRate": product_data.vat_rate,
                    "images": [{"url": product_data.image_url}] + [{"url": img} for img in product_data.additional_images],
                    "attributes": attributes
                }]
            }
            
            logger.info(f"Submitting product creation request for {product_data.title}")
            response = self.api.post(f"product/sellers/{self.api.config.seller_id}/products", payload)
            
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Product creation failed: {str(e)}")
            raise
    
    def check_batch_status(self, batch_id):
        """Check the status of a batch operation"""
        try:
            return self.api.get(f"product/sellers/{self.api.config.seller_id}/products/batch-requests/{batch_id}")
        except Exception as e:
            logger.error(f"Failed to check batch status: {str(e)}")
            raise
    
    def update_product_stock(self, product):
        """Update product stock"""
        try:
            payload = {
                "items": [{
                    "barcode": product.barcode,
                    "quantity": product.quantity
                }]
            }
            
            response = self.api.post(f"product/sellers/{self.api.config.seller_id}/products/batch-stock-update", payload)
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Failed to update product stock: {str(e)}")
            raise
    
    def update_product_price(self, product):
        """Update product price"""
        try:
            payload = {
                "items": [{
                    "barcode": product.barcode,
                    "listPrice": float(product.price) + 10,  # Add margin for list price
                    "salePrice": float(product.price)
                }]
            }
            
            response = self.api.post(f"product/sellers/{self.api.config.seller_id}/products/batch-price-update", payload)
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Failed to update product price: {str(e)}")
            raise


def get_active_api_config():
    """Get the active API configuration"""
    try:
        return TrendyolAPIConfig.objects.filter(is_active=True).first()
    except:
        return None


def create_trendyol_product(product):
    """Create a product on Trendyol"""
    config = get_active_api_config()
    if not config:
        logger.error("No active Trendyol API config found")
        product.set_batch_status('failed', 'No active Trendyol API config found')
        return
    
    try:
        api = TrendyolAPI(config)
        product_manager = TrendyolProductManager(api)
        
        batch_id = product_manager.create_product(product)
        
        product.batch_id = batch_id
        product.batch_status = 'processing'
        product.status_message = 'Product creation initiated'
        product.last_check_time = timezone.now()
        product.save()
        
        return batch_id
        
    except Exception as e:
        logger.error(f"Failed to create product on Trendyol: {str(e)}")
        product.set_batch_status('failed', f"Error: {str(e)}")
        return None


def check_product_batch_status(product):
    """Check the status of a product batch operation"""
    if not product.batch_id:
        return
    
    config = get_active_api_config()
    if not config:
        logger.error("No active Trendyol API config found")
        return
    
    try:
        api = TrendyolAPI(config)
        product_manager = TrendyolProductManager(api)
        
        status_data = product_manager.check_batch_status(product.batch_id)
        
        items = status_data.get('items', [])
        if not items:
            product.set_batch_status('processing', 'Waiting for processing')
            return
        
        item = items[0]
        status = item.get('status')
        
        if status == 'SUCCESS':
            product.set_batch_status('completed', 'Product created successfully')
            # Try to get product ID from response
            if 'productId' in item:
                product.trendyol_id = item['productId']
                product.trendyol_url = f"https://www.trendyol.com/brand/name-p-{item['productId']}"
                product.save()
        elif status == 'ERROR':
            product.set_batch_status('failed', f"Error: {item.get('failureReasons', 'Unknown error')}")
        else:
            product.set_batch_status('processing', f"Status: {status}")
        
    except Exception as e:
        logger.error(f"Failed to check batch status: {str(e)}")
        product.last_check_time = timezone.now()
        product.save(update_fields=['last_check_time'])


def check_pending_products():
    """Check all pending products"""
    products = TrendyolProduct.objects.filter(
        batch_id__isnull=False,
        batch_status__in=['pending', 'processing']
    )
    
    for product in products:
        if product.needs_status_check():
            logger.info(f"Checking status for product {product.id}: {product.title}")
            check_product_batch_status(product)


def update_product_from_lcwaikiki(lcw_product):
    """
    Update or create a Trendyol product from an LCWaikiki product.
    Returns the Trendyol product.
    """
    try:
        # Try to find existing Trendyol product linked to this LCWaikiki product
        trendyol_product = TrendyolProduct.objects.filter(lcwaikiki_product=lcw_product).first()
        
        # If not found, create a new one
        if not trendyol_product:
            trendyol_product = TrendyolProduct()
        
        # Update from LCWaikiki product
        trendyol_product.from_lcwaikiki_product(lcw_product)
        trendyol_product.save()
        
        return trendyol_product
        
    except Exception as e:
        logger.error(f"Error updating Trendyol product from LCWaikiki: {str(e)}")
        return None