import requests
import json
import uuid
import logging
import base64
from django.utils import timezone
from openai import OpenAI
import os
from functools import lru_cache
import time
from django.conf import settings

from .models import TrendyolAPIConfig, TrendyolProduct

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

def get_active_api_config():
    """
    Get the active API configuration
    """
    try:
        return TrendyolAPIConfig.objects.filter(is_active=True).first()
    except Exception as e:
        logger.error(f"Error retrieving API config: {str(e)}")
        return None


class TrendyolAPI:
    """Base class for Trendyol API operations with retry mechanism"""
    
    def __init__(self, config: TrendyolAPIConfig):
        self.config = config
        self.session = requests.Session()
        auth_str = f"{settings.TRENDYOL_SUPPLIER_ID}:{self.config.api_key}"
        auth_bytes = auth_str.encode('utf-8')
        encoded_auth = base64.b64encode(auth_bytes).decode('utf-8')
        
        self.session.headers.update({
            "Authorization": f"Basic {encoded_auth}",
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
    """Handles category discovery using GPT-4o"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self._category_cache = None
    
    @property
    def category_cache(self):
        """Cached category list"""
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
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id):
        """Get attributes for a specific category with caching"""
        try:
            data = self.api.get(f"product/product-categories/{category_id}/attributes")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            raise Exception(f"Failed to load attributes for category {category_id}")
    
    def find_matching_category(self, product_title, product_description=None):
        """Find best matching category using GPT-4o"""
        categories = self.category_cache
        if not categories:
            raise ValueError("No categories available from Trendyol API")
        
        # Prepare the category data in a format suitable for GPT
        category_data = self._prepare_category_data(categories)
        
        # Query GPT-4o to find the best matching category
        return self._query_gpt_for_category(category_data, product_title, product_description)
    
    def _prepare_category_data(self, categories, parent_path=''):
        """Recursively prepare category data for GPT"""
        result = []
        for category in categories:
            current_path = f"{parent_path}/{category['name']}" if parent_path else category['name']
            category_entry = {
                'id': category['id'], 
                'name': category['name'], 
                'path': current_path,
                'has_children': bool(category.get('subCategories', []))
            }
            result.append(category_entry)
            
            if category.get('subCategories'):
                subcategories = self._prepare_category_data(
                    category['subCategories'], current_path)
                result.extend(subcategories)
        
        return result
    
    def _query_gpt_for_category(self, category_data, product_title, product_description=None):
        """Query GPT-4o to find the best matching category"""
        try:
            # Prepare prompt with product information
            prompt = f"""
            I need to match a product to the appropriate Trendyol category ID. 
            
            Product title: {product_title}
            """
            
            if product_description:
                prompt += f"\nProduct description: {product_description}\n"
            
            # Add category information
            prompt += """
            Below is the full list of available Trendyol categories with their IDs, names, and hierarchical paths:
            """
            
            # Add category data (limit to avoid token limits)
            categories_str = json.dumps(category_data)
            prompt += f"\n{categories_str}\n"
            
            prompt += """
            Please analyze the product information and find the most appropriate category.
            
            You are a Turkish e-commerce expert at Trendyol. Considering both the product title and description,
            select the most specific and appropriate category for this product. Consider the product attributes 
            and match it to the most precise subcategory possible.
            
            Give me ONLY the category ID (not the name) that best matches the product. 
            Return ONLY the numeric ID with no other text or explanations.
            """
            
            # Make the API call
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                messages=[
                    {"role": "system", "content": "You are a Turkish e-commerce expert at Trendyol."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=10  # We just need a category ID, so keep it short
            )
            
            # Extract the category ID from the response
            category_id = response.choices[0].message.content.strip()
            
            # Ensure it's a valid numeric ID
            try:
                category_id = int(category_id)
                logger.info(f"GPT-4o selected category ID {category_id} for product '{product_title}'")
                return category_id
            except ValueError:
                logger.error(f"GPT-4o response was not a valid category ID: {category_id}")
                raise ValueError(f"Invalid category ID from GPT: {category_id}")
                
        except Exception as e:
            logger.error(f"Error finding category with GPT-4o: {str(e)}")
            raise Exception(f"Failed to find category with GPT-4o: {str(e)}")
    
    def get_required_attributes(self, category_id):
        """Get required attributes for a category"""
        attributes_data = self.get_category_attributes(category_id)
        required_attributes = []
        
        if not attributes_data or 'categoryAttributes' not in attributes_data:
            return []
        
        for attr in attributes_data.get('categoryAttributes', []):
            if attr.get('required'):
                required_attributes.append({
                    'id': attr.get('attribute', {}).get('id'),
                    'name': attr.get('attribute', {}).get('name'),
                    'allowCustom': attr.get('allowCustom', False),
                    'valueType': attr.get('attribute', {}).get('valueType'),
                    'attributeValues': attr.get('attributeValues', [])
                })
        
        return required_attributes
    
    def match_attribute_values(self, product_title, product_description, required_attributes):
        """Match product to attribute values using GPT-4o"""
        if not required_attributes:
            return {}
            
        result = {}
        for attr in required_attributes:
            if not attr.get('attributeValues'):
                continue
                
            attribute_values = [{
                'id': val.get('id'),
                'name': val.get('name')
            } for val in attr.get('attributeValues', [])]
            
            # Query GPT to select the best attribute value
            selected_value = self._query_gpt_for_attribute_value(
                product_title, 
                product_description, 
                attr.get('name'),
                attribute_values
            )
            
            if selected_value:
                result[attr.get('id')] = selected_value
        
        return result
    
    def _query_gpt_for_attribute_value(self, product_title, product_description, attr_name, attr_values):
        """Query GPT-4o to select the best attribute value"""
        try:
            # Prepare prompt with product and attribute information
            prompt = f"""
            I need to select the most appropriate value for a product attribute.
            
            Product title: {product_title}
            Product description: {product_description or 'No description available'}
            
            Attribute name: {attr_name}
            Available values: {json.dumps(attr_values)}
            
            Based on the product title and description, select the most appropriate value for this attribute.
            Return ONLY the numeric ID of the selected value, no explanation.
            
            If there is no appropriate match, return 'none'.
            """
            
            # Make the API call
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                messages=[
                    {"role": "system", "content": "You are a Turkish e-commerce product attributes expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=10  # We just need a value ID, so keep it short
            )
            
            # Extract the value ID from the response
            value_id = response.choices[0].message.content.strip()
            
            # Handle the case where no appropriate match was found
            if value_id.lower() == 'none':
                return None
                
            # Ensure it's a valid numeric ID
            try:
                value_id = int(value_id)
                logger.info(f"GPT-4o selected value ID {value_id} for attribute '{attr_name}'")
                return value_id
            except ValueError:
                logger.error(f"GPT-4o response was not a valid value ID: {value_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error finding attribute value with GPT-4o: {str(e)}")
            return None
            

class TrendyolProductManager:
    """Manages Trendyol products and batch processes"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.category_finder = TrendyolCategoryFinder(api_client)
    
    def create_product(self, product: TrendyolProduct):
        """Create a product on Trendyol"""
        try:
            # Find matching category
            category_id = self.category_finder.find_matching_category(
                product.title, product.description)
            
            # Get required attributes for this category
            required_attributes = self.category_finder.get_required_attributes(category_id)
            
            # Match attribute values
            attribute_values = self.category_finder.match_attribute_values(
                product.title, product.description, required_attributes[:8])  # Limit to first 8 attributes
            
            # Default attributes
            if 'fabric' not in attribute_values:
                attribute_values['fabric'] = 'unspecified'
            if 'pattern' not in attribute_values:
                attribute_values['pattern'] = 'unspecified'
            
            # Prepare product data
            product_data = {
                'items': [{
                    'barcode': product.barcode,
                    'title': product.title,
                    'productMainId': product.product_main_id,
                    'brandName': product.brand_name,
                    'categoryName': product.category_name,
                    'quantity': product.quantity,
                    'stockCode': product.stock_code,
                    'dimensionalWeight': 1,
                    'description': product.description,
                    'currencyType': product.currency_type,
                    'listPrice': float(product.price),
                    'salePrice': float(product.sale_price),
                    'vatRate': product.vat_rate,
                    'cargoCompanyId': 10,  # Default cargo company
                    'images': [
                        {
                            'url': product.image_url
                        }
                    ],
                    'attributes': self._format_attributes(attribute_values),
                    'categoryId': category_id
                }]
            }
            
            # Send to Trendyol
            response = self.api.post('supplier/product-service/v2/products', product_data)
            
            if 'batchId' in response:
                return response['batchId']
            else:
                raise Exception("No batch ID returned from API")
                
        except Exception as e:
            logger.error(f"Error creating product on Trendyol: {str(e)}")
            raise
    
    def _format_attributes(self, attribute_values):
        """Format attributes for Trendyol API"""
        formatted = []
        for attr_id, value_id in attribute_values.items():
            formatted.append({
                'attributeId': attr_id,
                'attributeValueId': value_id
            })
        return formatted
    
    def check_batch_status(self, batch_id):
        """Check status of a product batch"""
        try:
            response = self.api.get(f'supplier/product-service/v2/products/batch/{batch_id}')
            return response
        except Exception as e:
            logger.error(f"Error checking batch status: {str(e)}")
            raise


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
    """Check the status of a product batch"""
    if not product.batch_id:
        return
    
    if not product.needs_status_check():
        return
        
    config = get_active_api_config()
    if not config:
        product.set_batch_status('failed', 'No active Trendyol API config found')
        return
        
    try:
        api = TrendyolAPI(config)
        product_manager = TrendyolProductManager(api)
        
        batch_status = product_manager.check_batch_status(product.batch_id)
        
        status = batch_status.get('status', 'processing').lower()
        message = None
        
        if status == 'failed':
            message = batch_status.get('failureReasons', 'Unknown error')
            if isinstance(message, list):
                message = '; '.join([reason.get('message', 'Unknown') for reason in message])
        
        product.set_batch_status(status, message)
        
    except Exception as e:
        logger.error(f"Failed to check batch status for {product.batch_id}: {str(e)}")
        # Don't update status on connection errors, just log them


def check_pending_products():
    """Check status of all pending products"""
    try:
        pending_products = TrendyolProduct.objects.filter(
            batch_id__isnull=False,
            batch_status__in=['pending', 'processing']
        )
        
        for product in pending_products:
            if product.needs_status_check():
                check_product_batch_status(product)
                time.sleep(0.5)  # Avoid rate limiting
                
        return f"Checked {pending_products.count()} pending products"
        
    except Exception as e:
        logger.error(f"Error checking pending products: {str(e)}")
        return f"Error: {str(e)}"