"""
Improved Trendyol API Client

This module provides enhanced functionality for interacting with the Trendyol API.
It includes robust error handling, attribute management, and category discovery.
"""

import requests
import json
import re
import time
import uuid
import logging
from urllib.parse import quote
from typing import Dict, List, Optional, Union, Any, Tuple
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

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

from trendyol.models import (
    TrendyolProduct, TrendyolBrand, TrendyolCategory, TrendyolAPIConfig
)

# API configuration constants
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
        
        # API endpoints
        self.brands = f"{self.base_url}/sapigw/product/brands"
        self.categories = f"{self.base_url}/sapigw/product/product-categories"
        self.products = f"{self.base_url}/sapigw/product/sellers/{self.supplier_id}/products"
        self.inventory = f"{self.base_url}/sapigw/suppliers/{self.supplier_id}/products/inventory"
        
        # Set up session
        self.session = requests.Session()
        self.user_agent = f"{self.supplier_id} - Integration"
        
        # Generate auth token
        import base64
        auth_token = base64.b64encode(f"{self.api_key}:{self.api_secret}".encode()).decode()
        
        self.session.headers.update({
            "Authorization": f"Basic {auth_token}",
            "User-Agent": self.user_agent,
            "Content-Type": "application/json"
        })
    
    def make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Generic request method with retry logic"""
        url = endpoint if endpoint.startswith(('http://', 'https://')) else endpoint
        kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Making {method} request to {url}")
                response = self.session.request(method, url, **kwargs)
                logger.debug(f"Response status code: {response.status_code}")
                
                # Handle non-200 responses
                if response.status_code != 200:
                    logger.warning(f"API request returned status {response.status_code}: {response.text}")
                    
                    # Clear response payload for failed requests and include error details
                    error_info = {
                        'error': True,
                        'status_code': response.status_code,
                        'message': f"API request failed with status {response.status_code}",
                        'details': response.text
                    }
                    
                    # For 400+ errors, try to parse response json if available
                    if response.status_code >= 400:
                        try:
                            error_response = response.json()
                            if isinstance(error_response, dict):
                                error_info['message'] = error_response.get('message', error_info['message'])
                                error_info['errors'] = error_response.get('errors')
                        except Exception:
                            pass
                    
                    # Raise exception for server errors
                    if response.status_code >= 500:
                        if attempt < MAX_RETRIES - 1:
                            logger.warning(f"Server error, retrying in {RETRY_DELAY}s...")
                            time.sleep(RETRY_DELAY * (attempt + 1))
                            continue
                        
                    return error_info
                
                # Parse JSON response
                try:
                    result = response.json()
                    return result
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {response.text}")
                    return {
                        'error': True,
                        'message': "Invalid JSON response",
                        'details': response.text[:500]
                    }
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt+1}/{MAX_RETRIES}): {str(e)}")
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
                    return {
                        'error': True,
                        'message': f"Request failed: {str(e)}",
                        'details': str(e)
                    }
                logger.info(f"Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY * (attempt + 1))
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request"""
        return self.make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Dict) -> Dict:
        """Make a POST request"""
        return self.make_request('POST', endpoint, json=data)
    
    def put(self, endpoint: str, data: Dict) -> Dict:
        """Make a PUT request"""
        return self.make_request('PUT', endpoint, json=data)
    
    def delete(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a DELETE request"""
        return self.make_request('DELETE', endpoint, params=params)


class TrendyolCategoryFinder:
    """Handles category discovery and attribute management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
        
        if ADVANCED_SEARCH_AVAILABLE:
            try:
                self.model = SentenceTransformer('emrecan/bert-base-turkish-cased-mean-nli-stsb-tr')
                self.dictionary = MultiDictionary()
                logger.info("Initialized advanced search capabilities")
            except Exception as e:
                logger.warning(f"Failed to initialize advanced search: {str(e)}")
                self.model = None
                self.dictionary = None
        else:
            self.model = None
            self.dictionary = None
    
    @property
    def category_cache(self) -> List[Dict]:
        """Cached category data to avoid repeated API calls"""
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self) -> List[Dict]:
        """Fetch all categories from Trendyol API"""
        try:
            data = self.api.get(self.api.categories)
            if isinstance(data, dict) and 'error' in data and data['error']:
                logger.error(f"Error fetching categories: {data['message']}")
                return []
                
            categories = data.get('categories', [])
            logger.info(f"Fetched {len(categories)} top-level categories")
            return categories
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            return []
    
    def get_required_attributes(self, category_id: int) -> List[Dict]:
        """Get required attributes for a category in the format expected by Trendyol API"""
        attributes = []
        
        # Check cache first
        if category_id in self._attribute_cache:
            logger.info(f"Using cached attributes for category {category_id}")
            return self._attribute_cache[category_id]
        
        try:
            # Fetch category attributes from API
            attrs_endpoint = f"{self.api.categories}/{category_id}/attributes"
            attrs = self.api.get(attrs_endpoint)
            
            if isinstance(attrs, dict) and attrs.get('error'):
                logger.error(f"Error fetching attributes: {attrs.get('message')}")
                return []
            
            logger.info(f"Processing attributes for category {category_id}")
            
            # Process each attribute
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
            
            # Cache the results
            self._attribute_cache[category_id] = attributes
            
            # Log summary of attributes
            logger.info(f"Returning {len(attributes)} attributes for category {category_id}")
            return attributes
            
        except Exception as e:
            logger.error(f"Error getting required attributes: {str(e)}")
            return []
    
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
            # Default category
            logger.warning("Returning default category ID as fallback")
            return 385  # Default to Women's Clothing - Jacket as a safe fallback
    
    def _find_best_category_semantic(self, search_term: str, categories: List[Dict]) -> int:
        """Find best category using semantic similarity"""
        leaf_categories = []
        self._collect_leaf_categories(categories, leaf_categories)
        
        # Get the search term embedding
        search_embedding = self.model.encode(search_term, convert_to_tensor=True)
        
        # Calculate similarities for all categories
        for cat in leaf_categories:
            cat_embedding = self.model.encode(cat['name'], convert_to_tensor=True)
            cat['similarity'] = util.cos_sim(search_embedding, cat_embedding).item()
        
        # Sort by similarity
        sorted_cats = sorted(leaf_categories, key=lambda x: x['similarity'], reverse=True)
        
        # Log top matches
        logger.info(f"Top matches for '{search_term}':")
        for i, cat in enumerate(sorted_cats[:3], 1):
            logger.info(f"{i}. {cat['name']} (Similarity: {cat['similarity']:.4f}, ID: {cat['id']})")
        
        return sorted_cats[0]['id']
    
    def _find_all_matches(self, search_term: str, categories: List[Dict]) -> List[Dict]:
        """Find all matches using basic string comparison"""
        matches = []
        
        # Recursive helper function
        def _find_matches_recursive(term, cats, path=""):
            for cat in cats:
                current_path = f"{path} > {cat['name']}" if path else cat['name']
                
                # Check if this category matches
                if term.lower() in cat['name'].lower():
                    cat_copy = cat.copy()
                    cat_copy['full_path'] = current_path
                    matches.append(cat_copy)
                
                # Check subcategories
                if 'subCategories' in cat and cat['subCategories']:
                    _find_matches_recursive(term, cat['subCategories'], current_path)
        
        _find_matches_recursive(search_term, categories)
        return matches
    
    def _select_best_match(self, search_term: str, matches: List[Dict]) -> Dict:
        """Select best match using basic string similarity"""
        if not matches:
            raise ValueError(f"No matches found for: {search_term}")
        
        # Use difflib for basic string comparison
        similarities = []
        for match in matches:
            similarity = difflib.SequenceMatcher(None, search_term.lower(), match['name'].lower()).ratio()
            match['similarity'] = similarity
            similarities.append((similarity, match))
        
        # Sort by similarity
        similarities.sort(reverse=True, key=lambda x: x[0])
        
        # Log top matches
        logger.info(f"Top matches for '{search_term}':")
        for i, (similarity, match) in enumerate(similarities[:3], 1):
            logger.info(f"{i}. {match['name']} (Similarity: {similarity:.4f}, ID: {match['id']})")
        
        return similarities[0][1]
    
    def _collect_leaf_categories(self, categories: List[Dict], result: List[Dict]) -> None:
        """Recursively collect leaf categories"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)


def get_api_client() -> Optional[TrendyolAPI]:
    """Get a configured API client from database configuration"""
    try:
        # Get active API configuration
        api_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        
        if not api_config:
            logger.error("No active Trendyol API configuration found")
            return None
        
        logger.info(f"Using API config: {api_config.name}")
        
        # Create API client
        client = TrendyolAPI(api_config)
        logger.info(f"Trendyol API client initialized with base URL: {api_config.base_url}")
        return client
    except Exception as e:
        logger.error(f"Error initializing API client: {str(e)}")
        return None


def fetch_brands() -> List[Dict]:
    """Fetch all brands from Trendyol API and update local database"""
    client = get_api_client()
    if not client:
        logger.error("Cannot fetch brands: No API client available")
        return []
    
    try:
        brands_response = client.get(client.brands)
        
        if isinstance(brands_response, dict) and brands_response.get('error'):
            logger.error(f"Error fetching brands: {brands_response.get('message')}")
            return []
        
        brands = brands_response
        
        if not brands or not isinstance(brands, list):
            logger.error(f"Invalid brands response: {brands}")
            return []
        
        logger.info(f"Fetched {len(brands)} brands from Trendyol API")
        
        # Process and store in database
        stored_count = 0
        for brand in brands:
            brand_id = brand.get('id')
            brand_name = brand.get('name')
            
            if not brand_id or not brand_name:
                continue
            
            try:
                TrendyolBrand.objects.update_or_create(
                    brand_id=brand_id,
                    defaults={
                        'name': brand_name,
                        'is_active': True
                    }
                )
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing brand {brand_name}: {str(e)}")
        
        logger.info(f"Stored {stored_count} brands in database")
        return brands
    except Exception as e:
        logger.error(f"Error fetching brands: {str(e)}")
        return []


def fetch_categories() -> List[Dict]:
    """Fetch all categories from Trendyol API and update local database"""
    client = get_api_client()
    if not client:
        logger.error("Cannot fetch categories: No API client available")
        return []
    
    try:
        categories_response = client.get(client.categories)
        
        if isinstance(categories_response, dict) and categories_response.get('error'):
            logger.error(f"Error fetching categories: {categories_response.get('message')}")
            return []
        
        categories = categories_response.get('categories', [])
        
        if not categories:
            logger.error("No categories found in API response")
            return []
        
        logger.info(f"Fetched {len(categories)} top-level categories from Trendyol API")
        
        # Process and store in database
        def store_categories(categories_list, parent_id=None, parent_name=""):
            stored_count = 0
            
            for category in categories_list:
                category_id = category.get('id')
                category_name = category.get('name')
                
                if not category_id or not category_name:
                    continue
                
                full_name = f"{parent_name} > {category_name}" if parent_name else category_name
                
                try:
                    cat_obj, created = TrendyolCategory.objects.update_or_create(
                        category_id=category_id,
                        defaults={
                            'name': category_name,
                            'full_name': full_name,
                            'parent_id': parent_id,
                            'is_active': True
                        }
                    )
                    stored_count += 1
                    
                    # Process subcategories
                    if 'subCategories' in category and category['subCategories']:
                        sub_count = store_categories(
                            category['subCategories'], 
                            parent_id=category_id,
                            parent_name=full_name
                        )
                        stored_count += sub_count
                except Exception as e:
                    logger.error(f"Error storing category {category_name}: {str(e)}")
            
            return stored_count
        
        total_stored = store_categories(categories)
        logger.info(f"Stored {total_stored} categories in database")
        return categories
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        return []


def find_brand_id_by_name(brand_name: str, client=None) -> Optional[int]:
    """Find a brand ID by name in Trendyol system"""
    if not client:
        client = get_api_client()
        if not client:
            logger.error("Cannot find brand: No API client available")
            return None
    
    try:
        # First check local database
        local_brand = TrendyolBrand.objects.filter(
            name__icontains=brand_name,
            is_active=True
        ).first()
        
        if local_brand:
            logger.info(f"Found brand in database: {local_brand.name} (ID: {local_brand.brand_id})")
            return local_brand.brand_id
        
        # If not found locally, try API
        encoded_name = quote(brand_name)
        endpoint = f"{client.brands}/by-name?name={encoded_name}"
        brands_response = client.get(endpoint)
        
        if isinstance(brands_response, dict) and brands_response.get('error'):
            logger.error(f"Error finding brand: {brands_response.get('message')}")
            return None
        
        if not brands_response or not isinstance(brands_response, list) or len(brands_response) == 0:
            logger.warning(f"No brands found for name: {brand_name}")
            return None
        
        brand_id = brands_response[0]['id']
        brand_obj_name = brands_response[0]['name']
        
        # Store in database for future use
        try:
            TrendyolBrand.objects.update_or_create(
                brand_id=brand_id,
                defaults={
                    'name': brand_obj_name,
                    'is_active': True
                }
            )
        except Exception as e:
            logger.error(f"Error storing brand {brand_obj_name}: {str(e)}")
        
        logger.info(f"Found brand via API: {brand_obj_name} (ID: {brand_id})")
        return brand_id
    except Exception as e:
        logger.error(f"Error finding brand {brand_name}: {str(e)}")
        return None


def find_trendyol_category_id(product_title: str, client=None) -> int:
    """Find the best matching category ID for a product title"""
    if not client:
        client = get_api_client()
        if not client:
            logger.error("Cannot find category: No API client available")
            return 385  # Default category as fallback
    
    try:
        finder = TrendyolCategoryFinder(client)
        category_id = finder.find_best_category(product_title)
        logger.info(f"Found category ID {category_id} for product title: {product_title}")
        return category_id
    except Exception as e:
        logger.error(f"Error finding category for {product_title}: {str(e)}")
        return 385  # Default to a common clothing category


def prepare_product_data(product: TrendyolProduct) -> Dict[str, Any]:
    """Prepare product data for submission to Trendyol API"""
    client = get_api_client()
    if not client:
        raise ValueError("Cannot prepare product data: No API client available")
    
    # Verify required fields
    if not product.barcode:
        raise ValueError("Product barcode is required")
    
    if not product.title:
        raise ValueError("Product title is required")
    
    if not product.brand_id:
        raise ValueError("Product brand ID is required")
    
    category_id = product.category_id
    if not category_id:
        raise ValueError("Product category ID is required")
    
    # Prepare image URLs
    image_urls = []
    if product.image_url:
        image_urls.append(product.image_url)
    
    if product.additional_images:
        if isinstance(product.additional_images, list):
            image_urls.extend(product.additional_images)
        elif isinstance(product.additional_images, str):
            try:
                additional_images = json.loads(product.additional_images)
                if isinstance(additional_images, list):
                    image_urls.extend(additional_images)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse additional_images for product {product.id}")
    
    # Verify we have at least one image
    if not image_urls:
        raise ValueError("At least one product image is required")
    
    # Get attributes and ensure we have all required ones
    attributes = product.attributes or []
    
    # Even if we have existing attributes, ensure we have required ones from API
    logger.info(f"Getting required attributes for category {category_id}")
    
    # Use TrendyolCategoryFinder to get required attributes
    finder = TrendyolCategoryFinder(client)
    required_attrs = finder.get_required_attributes(category_id)
    
    # Get existing attribute IDs
    existing_attr_ids = set(attr.get('attributeId') for attr in attributes if attr.get('attributeId'))
    
    # Add any missing required attributes
    for attr in required_attrs:
        attr_id = attr.get('attributeId')
        if attr_id not in existing_attr_ids:
            attributes.append(attr)
            logger.info(f"Added required attribute: {attr}")
    
    # If attributes is still empty after our efforts, this is a critical issue
    if not attributes:
        raise ValueError(f"No attributes found for category {category_id}")
    
    # Normalize title (limit to 100 chars)
    title = " ".join(product.title.split())  # Normalize whitespace
    if len(title) > 100:
        title = title[:97] + "..."
    
    # Prepare the product data payload
    product_data = {
        "barcode": product.barcode,
        "title": title,
        "productMainId": product.product_main_id or product.barcode,
        "brandId": int(product.brand_id),
        "categoryId": int(category_id),
        "stockCode": product.stock_code or product.barcode,
        "quantity": int(product.quantity or 10),
        "listPrice": float(product.price or 0),
        "salePrice": float(product.price or 0),
        "vatRate": 10,  # Fixed VAT rate
        "cargoCompanyId": 17,  # Fixed cargo company
        "description": product.description or product.title,
        "currencyType": product.currency_type or "TRY",
        "attributes": attributes,
        "images": [{"url": url} for url in image_urls if url]
    }
    
    return product_data


def create_trendyol_product(product: TrendyolProduct) -> Optional[str]:
    """Create a product on Trendyol and return the batch ID if successful"""
    client = get_api_client()
    if not client:
        product.batch_status = 'failed'
        product.status_message = "No active Trendyol API configuration found"
        product.save()
        return None
    
    try:
        # Prepare product data
        product_data = prepare_product_data(product)
        
        # Create the batch request payload
        batch_request_id = str(uuid.uuid4())
        payload = {
            "items": [product_data],
            "batchRequestId": batch_request_id,
            "hasMultiSupplier": False,
            "supplierId": int(client.supplier_id)
        }
        
        # Send the request
        logger.info(f"Creating product on Trendyol: {product.title}")
        response = client.post(client.products, payload)
        
        # Handle error responses
        if isinstance(response, dict) and response.get('error'):
            error_message = response.get('message', 'Unknown API error')
            product.batch_status = 'failed'
            product.status_message = error_message[:500]
            product.save()
            return None
        
        # Check for batch request ID in the response
        if not response or 'batchRequestId' not in response:
            product.batch_status = 'failed'
            product.status_message = "No batch request ID returned from API"
            product.save()
            return None
        
        # Update product with batch ID and status
        batch_id = response['batchRequestId']
        product.batch_id = batch_id
        product.batch_status = 'processing'
        product.status_message = "Product creation initiated"
        product.last_check_time = timezone.now()
        product.save()
        
        logger.info(f"Product {product.title} created with batch ID: {batch_id}")
        return batch_id
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        product.batch_status = 'failed'
        product.status_message = f"Error: {str(e)}"[:500]
        product.save()
        return None


def check_batch_status(batch_id: str) -> Dict[str, Any]:
    """Check the status of a batch request on Trendyol"""
    client = get_api_client()
    if not client:
        return {"error": True, "message": "No API client available"}
    
    try:
        endpoint = f"{client.products}/batch-requests/{batch_id}"
        response = client.get(endpoint)
        
        if isinstance(response, dict) and response.get('error'):
            return {"error": True, "message": response.get('message', 'API Error')}
        
        return response
    except Exception as e:
        logger.error(f"Error checking batch status for {batch_id}: {str(e)}")
        return {"error": True, "message": str(e)}


def update_trendyol_product_status(product: TrendyolProduct) -> str:
    """
    Update the status of a Trendyol product by checking its batch status.
    Returns the current status: 'completed', 'failed', 'processing'
    """
    if not product.batch_id:
        product.batch_status = 'failed'
        product.status_message = "No batch ID available"
        product.save()
        return 'failed'
    
    try:
        # Check batch status
        batch_response = check_batch_status(product.batch_id)
        
        if isinstance(batch_response, dict) and batch_response.get('error'):
            product.batch_status = 'failed'
            product.status_message = batch_response.get('message', 'Unknown error')
            product.save()
            return 'failed'
        
        # Determine status from response
        status = 'processing'  # Default status
        status_message = "Processing"
        
        # Extract batch status information
        batch_status = batch_response.get('status')
        if batch_status:
            if batch_status == 'DONE' or batch_status == 'SUCCESS':
                status = 'completed'
                status_message = "Completed successfully"
            elif batch_status == 'FAILED':
                status = 'failed'
                status_message = "Batch failed"
        
        # Check for failed items
        items = batch_response.get('items', [])
        failed_items = [item for item in items if item.get('status') in ['FAILED', 'INVALID']]
        
        if failed_items:
            status = 'failed'
            
            # Collect error messages
            error_messages = []
            for item in failed_items:
                reasons = item.get('failureReasons', [])
                for reason in reasons:
                    if reason.get('message'):
                        error_messages.append(reason['message'])
            
            if error_messages:
                status_message = " | ".join(error_messages)[:500]
            else:
                status_message = "Item failed without specific reason"
        
        # Check for Trendyol product ID
        if status == 'completed' and not product.trendyol_id:
            for item in items:
                if item.get('status') == 'SUCCESS' and item.get('tracingId'):
                    product.trendyol_id = item['tracingId']
                    break
        
        # Update product status
        product.batch_status = status
        product.status_message = status_message
        product.last_check_time = timezone.now()
        product.save()
        
        logger.info(f"Updated product {product.id} status to {status}: {status_message}")
        return status
    except Exception as e:
        logger.error(f"Error updating product status: {str(e)}")
        product.status_message = f"Error checking status: {str(e)}"[:500]
        product.save()
        return 'processing'  # Keep as processing to try again


def lcwaikiki_to_trendyol_product(lcw_product) -> Optional[TrendyolProduct]:
    """Convert an LCWaikiki product to a Trendyol product"""
    from lcwaikiki.models import Product
    
    # Make sure product is a Product instance
    if not isinstance(lcw_product, Product):
        logger.error(f"Product is not a valid Product instance: {lcw_product}")
        return None
    
    try:
        # Get API client
        client = get_api_client()
        if not client:
            logger.error("No API client available")
            return None
        
        # Check if a Trendyol product already exists for this LCWaikiki product
        trendyol_product = TrendyolProduct.objects.filter(
            lcwaikiki_product=lcw_product).first()
        
        # Generate unique barcode
        barcode = f"LCW{lcw_product.id:09d}"
        
        # Get the price
        price = lcw_product.price or Decimal('100.00')
        
        # Process images
        images = []
        if hasattr(lcw_product, 'images') and lcw_product.images:
            if isinstance(lcw_product.images, list):
                images = lcw_product.images
            elif isinstance(lcw_product.images, str):
                try:
                    images = json.loads(lcw_product.images)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse images JSON for product {lcw_product.id}")
        
        # Make sure we have valid images
        valid_images = []
        for img in images:
            if isinstance(img, str) and img.strip():
                if not img.startswith(('http://', 'https://')):
                    img = f"https:{img}" if img.startswith('//') else f"https://{img}"
                valid_images.append(img)
        
        if not valid_images:
            logger.warning(f"No valid images found for product {lcw_product.id}")
            return None
        
        # Get quantity with fallback
        quantity = 10  # Default
        if hasattr(lcw_product, 'get_total_stock'):
            try:
                stock = lcw_product.get_total_stock()
                if stock and stock > 0:
                    quantity = min(stock, 20000)  # Trendyol max is 20000
            except Exception as e:
                logger.warning(f"Error getting stock: {str(e)}")
        
        # Find brand ID with fallback to default LC Waikiki ID
        brand_id = find_brand_id_by_name("LC Waikiki", client) or 7651
        
        # Find category ID
        category_name = lcw_product.category if hasattr(lcw_product, 'category') else ""
        category_id = find_trendyol_category_id(
            f"{category_name} {lcw_product.title}" if category_name else lcw_product.title,
            client
        )
        
        if not trendyol_product:
            # Create new Trendyol product
            trendyol_product = TrendyolProduct.objects.create(
                barcode=barcode,
                title=lcw_product.title[:100] if lcw_product.title else "LC Waikiki Product",
                description=lcw_product.description or lcw_product.title or "LC Waikiki Product",
                product_main_id=barcode,
                stock_code=barcode,
                brand_id=brand_id,
                brand_name="LC Waikiki",
                category_id=category_id,
                category_name=lcw_product.category if hasattr(lcw_product, 'category') else "Clothing",
                price=price,
                quantity=quantity,
                image_url=valid_images[0],
                additional_images=valid_images[1:] if len(valid_images) > 1 else [],
                attributes=[],  # Will be populated during API submission
                lcwaikiki_product=lcw_product,
                batch_status='pending',
                status_message="Created from LCWaikiki product",
                currency_type="TRY",
                vat_rate=10
            )
            logger.info(f"Created new Trendyol product from LCW product {lcw_product.id}")
        else:
            # Update existing product
            trendyol_product.title = lcw_product.title[:100] if lcw_product.title else trendyol_product.title
            trendyol_product.description = lcw_product.description or lcw_product.title or trendyol_product.description
            trendyol_product.price = price
            trendyol_product.quantity = quantity
            trendyol_product.brand_id = brand_id
            trendyol_product.category_id = category_id
            
            # Only update images if we have valid ones
            if valid_images:
                trendyol_product.image_url = valid_images[0]
                trendyol_product.additional_images = valid_images[1:] if len(valid_images) > 1 else []
            
            # Reset attributes to be fetched from API during product creation
            trendyol_product.attributes = []
            trendyol_product.save()
            logger.info(f"Updated Trendyol product {trendyol_product.id} from LCW product {lcw_product.id}")
        
        return trendyol_product
    except Exception as e:
        logger.error(f"Error converting LCWaikiki product to Trendyol: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def sync_product_to_trendyol(product: TrendyolProduct) -> bool:
    """Sync a product to Trendyol"""
    try:
        # Only sync products that are not already processing
        if product.batch_status == 'processing':
            logger.info(f"Product {product.id} is already processing, checking status...")
            status = update_trendyol_product_status(product)
            return status == 'completed'
        
        # Create product on Trendyol
        batch_id = create_trendyol_product(product)
        
        if not batch_id:
            logger.error(f"Failed to create product {product.id} on Trendyol")
            return False
        
        logger.info(f"Product {product.id} submitted to Trendyol with batch ID: {batch_id}")
        return True
    except Exception as e:
        logger.error(f"Error syncing product {product.id} to Trendyol: {str(e)}")
        product.status_message = f"Sync error: {str(e)}"[:500]
        product.batch_status = 'failed'
        product.save()
        return False