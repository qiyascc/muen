import requests
import json
import uuid
import logging
from urllib.parse import quote
from django.utils import timezone
import time
import os
from openai import OpenAI

from .models import TrendyolAPIConfig, TrendyolProduct

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
            "Authorization": f"Basic {self.config.api_key}",
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
    """Enhanced category discovery with ChatGPT integration"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
        # OpenAI client
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=self.openai_api_key)
    
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
        if category_id not in self._attribute_cache:
            try:
                data = self.api.get(f"product/product-categories/{category_id}/attributes")
                self._attribute_cache[category_id] = data
            except Exception as e:
                logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
                raise Exception(f"Failed to load attributes for category {category_id}")
        return self._attribute_cache[category_id]
    
    def _get_all_leaf_categories(self, categories):
        """Get all leaf categories (categories without children)"""
        leaf_categories = []
        self._collect_leaf_categories(categories, leaf_categories)
        return leaf_categories
    
    def _collect_leaf_categories(self, categories, result):
        """Recursively collect leaf categories"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def find_best_category_with_gpt(self, search_term, product_info=None):
        """
        Find the most relevant category using ChatGPT
        
        Args:
            search_term: The main search term (usually category name)
            product_info: Optional additional product information to help with matching
        
        Returns:
            category ID of the best match
        """
        try:
            # Get all leaf categories
            categories = self.category_cache
            leaf_categories = self._get_all_leaf_categories(categories)
            
            # Prepare category data for GPT
            category_data = []
            for cat in leaf_categories:
                cat_info = {"id": cat['id'], "name": cat['name']}
                # Add breadcrumb paths if available
                if cat.get('breadcrumb'):
                    cat_info["path"] = " > ".join(cat['breadcrumb'])
                category_data.append(cat_info)
            
            # Format product info
            product_description = ""
            if product_info:
                product_description = f"""
                Ürün başlığı: {product_info.get('title', '')}
                Ürün açıklaması: {product_info.get('description', '')}
                Marka: {product_info.get('brand', '')}
                """
            
            # Construct the prompt for ChatGPT
            prompt = f"""
            Trendyol kategorileri içinden, aşağıdaki ürün bilgilerine en uygun kategoriyi bul.
            
            Ürün bilgileri:
            Aranan kategori: {search_term}
            {product_description}
            
            Aşağıdaki kategoriler arasından en uygun olanı seç:
            ```
            {json.dumps(category_data, ensure_ascii=False, indent=2)}
            ```
            
            Ürünün özellikleri ve kategori isimleri arasında anlamsal bir eşleşme yap.
            Yanıt olarak sadece kategori ID'sini ve kısa bir açıklama döndür, JSON formatında olsun:
            {{
                "category_id": [seçilen kategori ID'si],
                "category_name": [seçilen kategori adı],
                "reasoning": [seçim nedeni]
            }}
            """
            
            logger.info(f"Making category search request to ChatGPT for: {search_term}")
            
            # Make request to OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "Sen bir uzman e-ticaret kategori eşleştiricisisin. "
                                                  "Verilen ürün bilgilerini uygun Trendyol kategorisiyle eşleştir."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            category_id = int(result.get("category_id"))
            
            logger.info(f"ChatGPT found category: {result.get('category_name')} (ID: {category_id})")
            logger.info(f"Reasoning: {result.get('reasoning')}")
            
            return category_id
            
        except Exception as e:
            logger.error(f"Category search with ChatGPT failed for '{search_term}': {str(e)}")
            # Fallback to traditional search
            return self._traditional_category_search(search_term)
    
    def _traditional_category_search(self, search_term):
        """Traditional category search as fallback"""
        categories = self.category_cache
        leaf_categories = self._get_all_leaf_categories(categories)
        
        # Simple text matching
        for cat in leaf_categories:
            if search_term.lower() == cat['name'].lower():
                return cat['id']
        
        # Partial matching
        matches = []
        for cat in leaf_categories:
            if search_term.lower() in cat['name'].lower():
                matches.append(cat)
        
        if matches:
            return matches[0]['id']
            
        # No match found, return a default category
        logger.warning(f"No category match found for '{search_term}', using first leaf category")
        return leaf_categories[0]['id'] if leaf_categories else None
            
    def get_optimized_attributes(self, category_id, product_info):
        """
        Get optimized attributes for a product using ChatGPT
        
        Args:
            category_id: The category ID
            product_info: Dictionary with product information
        
        Returns:
            List of attribute dictionaries
        """
        try:
            # Get the category attributes
            category_attrs = self.get_category_attributes(category_id)
            
            # If no attributes required or available, return empty list
            if not category_attrs.get('categoryAttributes'):
                return []
                
            # Format all available attributes and their values
            available_attributes = []
            required_attributes = []
            
            for attr in category_attrs.get('categoryAttributes', []):
                attr_info = {
                    "attributeId": attr['attribute']['id'],
                    "attributeName": attr['attribute']['name'],
                    "required": attr.get('required', False),
                    "varianter": attr.get('varianter', False),
                    "allowCustom": attr.get('allowCustom', False),
                    "values": []
                }
                
                # Add possible values
                for val in attr.get('attributeValues', []):
                    attr_info["values"].append({
                        "id": val['id'],
                        "name": val['name']
                    })
                
                available_attributes.append(attr_info)
                
                if attr.get('required', False):
                    required_attributes.append(attr_info)
            
            # If we don't have required attributes, just return empty
            if not required_attributes:
                return []
            
            # Format product info for the prompt
            product_description = f"""
            Ürün başlığı: {product_info.get('title', '')}
            Ürün açıklaması: {product_info.get('description', '')}
            Marka: {product_info.get('brand', '')}
            """
            
            # Construct the prompt for ChatGPT
            prompt = f"""
            Bu ürün için en uygun öznitelikleri (attributes) belirle:
            
            {product_description}
            
            Kategori öznitelikleri:
            ```
            {json.dumps(available_attributes, ensure_ascii=False, indent=2)}
            ```
            
            Şu öznitelikler zorunlu: {', '.join([a['attributeName'] for a in required_attributes])}
            
            Ürünün açıklaması ve başlığını incele, en uygun öznitelik değerlerini seç.
            Eğer özniteliğin sabit değerleri (values) varsa, bu listeden seç.
            Eğer öznitelik için özel değer (allowCustom=true) girilebiliyorsa, uygun bir değer yaz.
            
            Yanıt olarak aşağıdaki formatta bir JSON döndür:
            [
                {{
                    "attributeId": [öznitelik ID'si],
                    "attributeName": [öznitelik adı],
                    "attributeValueId": [seçilen değer ID'si, eğer sabit bir liste varsa],
                    "attributeValue": [seçilen değer adı, eğer sabit bir liste varsa],
                    "customAttributeValue": [özel değer, eğer özel değer giriliyorsa]
                }},
                ...
            ]
            """
            
            logger.info(f"Making attribute optimization request to ChatGPT for product in category ID: {category_id}")
            
            # Make request to OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "Sen bir uzman e-ticaret ürün özniteliği belirleyicisisin. "
                                                  "Verilen ürün bilgilerine göre en uygun öznitelikleri seç."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Log the results
            logger.info(f"ChatGPT optimized attributes: {json.dumps(result, ensure_ascii=False)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Attribute optimization with ChatGPT failed: {str(e)}")
            # Fallback to traditional attribute selection
            return self._get_default_attributes(category_id)
    
    def _get_default_attributes(self, category_id):
        """Generate default attributes as fallback"""
        attributes = []
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
        
        return attributes


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
                return brands[0]['id']
            # If LC Waikiki brand is not found, use brand ID 7651 as default
            if brand_name.lower() == 'lcw' or 'lcw' in brand_name.lower() or 'lc waikiki' in brand_name.lower():
                logger.info(f"Using default LC Waikiki brand ID (7651) for: {brand_name}")
                return 7651
            raise ValueError(f"Brand not found: {brand_name}")
        except Exception as e:
            logger.error(f"Brand search failed for '{brand_name}': {str(e)}")
            raise
    
    def create_product(self, product_data):
        """Create a new product on Trendyol with enhanced attribute matching"""
        try:
            # Prepare product info for category search
            product_info = {
                'title': product_data.title,
                'description': product_data.description,
                'brand': product_data.brand_name
            }
            
            # Find category with GPT assistance
            category_id = self.category_finder.find_best_category_with_gpt(
                product_data.category_name, 
                product_info
            )
            
            # Get brand ID
            brand_id = self.get_brand_id(product_data.brand_name)
            
            # Get optimized attributes with GPT
            attributes = self.category_finder.get_optimized_attributes(
                category_id,
                product_info
            )
            
            # Build payload
            payload = self._build_product_payload(product_data, category_id, brand_id, attributes)
            
            logger.info(f"Submitting product creation request for: {product_data.title}")
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
    
    def _build_product_payload(self, product, category_id, brand_id, attributes):
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
                "description": product.description,
                "currencyType": product.currency_type,
                "listPrice": float(product.price) + 10,  # Extra margin for list price
                "salePrice": float(product.price),
                "vatRate": product.vat_rate,
                "images": [{"url": product.image_url}],
                "attributes": attributes
            }]
        }


def get_active_api_config():
    try:
        return TrendyolAPIConfig.objects.filter(is_active=True).first()
    except:
        return None


def create_trendyol_product(product):
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
        elif status == 'ERROR':
            product.set_batch_status('failed', f"Error: {item.get('failureReasons', 'Unknown error')}")
        else:
            product.set_batch_status('processing', f"Status: {status}")
        
    except Exception as e:
        logger.error(f"Failed to check batch status: {str(e)}")
        product.last_check_time = timezone.now()
        product.save(update_fields=['last_check_time'])


def check_pending_products():
    products = TrendyolProduct.objects.filter(
        batch_id__isnull=False,
        batch_status__in=['pending', 'processing']
    )
    
    for product in products:
        if product.needs_status_check():
            logger.info(f"Checking status for product {product.id}: {product.title}")
            check_product_batch_status(product)