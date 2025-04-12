"""
Updated Trendyol API client with working endpoints.

This module contains the updated TrendyolAPI class that uses the 
endpoints verified to work with the current Trendyol API version.
It also includes helper classes for category finding, product management,
and utility functions for interacting with Trendyol API.
"""

import base64
import json
import logging
import requests
import time
from django.utils import timezone
from trendyol.models import TrendyolAPIConfig, TrendyolProduct, TrendyolCategory, TrendyolBrand
from tqdm import tqdm

try:
    from sentence_transformers import SentenceTransformer
    from PyMultiDictionary import MultiDictionary
except ImportError:
    pass

logger = logging.getLogger(__name__)

class TrendyolAPI:
    """
    Trendyol API client using verified working endpoints.
    """
    
    def __init__(self, api_config=None):
        """Initialize the API client with the given config or the active config from the database."""
        if api_config:
            self.config = api_config
        else:
            try:
                self.config = TrendyolAPIConfig.objects.filter(is_active=True).first()
                if not self.config:
                    logger.error("No active API configuration found")
            except Exception as e:
                logger.error(f"Error loading API configuration: {str(e)}")
                self.config = None
        
        if self.config:
            self.base_url = self.config.base_url
            self.api_key = self.config.api_key
            self.api_secret = self.config.api_secret
            self.seller_id = self.config.seller_id
            self.user_agent = self.config.user_agent
            
            # Try to get auth token, or generate from API key and secret
            if hasattr(self.config, 'auth_token') and self.config.auth_token:
                self.auth_token = self.config.auth_token
                logger.info("Using provided auth token from configuration")
            else:
                # Generate auth token from API key and secret
                auth_string = f"{self.api_key}:{self.api_secret}"
                self.auth_token = base64.b64encode(auth_string.encode()).decode('utf-8')
                logger.info(f"Generated auth token from API key and secret")
        else:
            logger.warning("Initializing with default values - this is likely not what you want")
            self.base_url = "https://apigw.trendyol.com/integration"
            self.auth_token = ""
            self.api_key = ""
            self.api_secret = ""
            self.seller_id = ""
            self.user_agent = ""
        
        logger.info(f"Initialized TrendyolAPI client with base URL: {self.base_url}")

    def get_headers(self):
        """Get the headers for API requests."""
        return {
            'Authorization': f'Basic {self.auth_token}',
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        
    def make_request(self, method, endpoint, data=None, params=None):
        """
        Make a request to the Trendyol API using verified working endpoints.
        
        Args:
            method: HTTP method ('GET', 'POST', etc.)
            endpoint: API endpoint to call
            data: Optional data to send (for POST/PUT)
            params: Optional query parameters
            
        Returns:
            API response as a dict or raises an exception
        """
        # Map endpoints to known working versions
        working_endpoints = {
            # Categories
            "/categories": "/product/product-categories",
            "/product-categories": "/product/product-categories",
            
            # Category attributes
            "/category-attributes": "/product/product-categories/{category_id}/attributes",
            
            # Brands
            "/brands": "/product/brands",
            
            # Products
            "/suppliers/{seller_id}/products": "/product/sellers/{seller_id}/products",
            "/sellers/{seller_id}/products": "/product/sellers/{seller_id}/products"
        }
        
        # Try to find a working endpoint mapping
        for pattern, working_endpoint in working_endpoints.items():
            if pattern in endpoint:
                # Check if we need to replace parameters
                if "{category_id}" in working_endpoint:
                    # Extract category_id from parameters or endpoint
                    category_id = None
                    if params and "categoryId" in params:
                        category_id = params.pop("categoryId")
                    else:
                        # Try to extract from the endpoint
                        import re
                        match = re.search(r"/categories/([0-9]+)/", endpoint)
                        if match:
                            category_id = match.group(1)
                    
                    if category_id:
                        working_endpoint = working_endpoint.replace("{category_id}", str(category_id))
                    else:
                        logger.warning(f"Could not extract category_id for endpoint: {endpoint}")
                        continue
                        
                if "{seller_id}" in working_endpoint:
                    working_endpoint = working_endpoint.replace("{seller_id}", str(self.seller_id))
                    
                logger.info(f"Using working endpoint mapping: {endpoint} -> {working_endpoint}")
                endpoint = working_endpoint
                break
        
        full_url = f"{self.base_url}{endpoint}"
        
        headers = self.get_headers()
        
        logger.debug(f"Making request to {full_url}")
        logger.debug(f"Headers: {headers}")
        if data:
            logger.debug(f"Data: {json.dumps(data, indent=2)}")
        
        try:
            if method.upper() == 'GET':
                response = requests.get(full_url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = requests.post(full_url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(full_url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(full_url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response content: {response.text[:500]}...")
            
            if response.status_code >= 400:
                logger.error(f"Error making request: {response.status_code} - {response.text}")
                
            response.raise_for_status()
            
            if response.text and len(response.text.strip()) > 0:
                return response.json()
            return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Trendyol API: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            raise

    def get_categories(self):
        """Get all categories from Trendyol."""
        response = self.make_request('GET', '/product/product-categories')
        return response.get('categories', [])
        
    def get_category_attributes(self, category_id):
        """Get attributes for a specific category."""
        response = self.make_request('GET', f'/product/product-categories/{category_id}/attributes')
        return response.get('categoryAttributes', [])
        
    def get_brands(self, name=None):
        """Get brands from Trendyol, optionally filtered by name."""
        params = {}
        if name:
            params['name'] = name
            
        response = self.make_request('GET', '/product/brands', params=params)
        return response.get('brands', [])
    
    def submit_product(self, product_data):
        """Submit a product to Trendyol."""
        # Format product data as expected by Trendyol API
        if isinstance(product_data, dict):
            # Already in API format
            items = [product_data]
        elif isinstance(product_data, list):
            # List of products
            items = product_data
        else:
            # Convert from Django model
            from trendyol.models import TrendyolProduct
            if isinstance(product_data, TrendyolProduct):
                items = [{
                    "barcode": product_data.barcode,
                    "title": product_data.title[:100].strip(),
                    "productMainId": product_data.product_main_id or product_data.barcode,
                    "brandId": product_data.brand_id,
                    "categoryId": product_data.category_id,
                    "quantity": product_data.quantity or 10,
                    "stockCode": product_data.stock_code or product_data.barcode,
                    "dimensionalWeight": 1,
                    "description": (product_data.description or product_data.title)[:500],
                    "currencyType": product_data.currency_type or "TRY",
                    "listPrice": float(product_data.price),
                    "salePrice": float(product_data.price),
                    "vatRate": product_data.vat_rate or 20,
                    "cargoCompanyId": 17,
                    "shipmentAddressId": 0,
                    "deliveryDuration": 3,
                    "images": [{"url": product_data.image_url}],
                    "attributes": product_data.attributes or []
                }]
            else:
                raise ValueError(f"Unsupported product data type: {type(product_data)}")
                
        payload = {"items": items}
        response = self.make_request('POST', f'/product/sellers/{self.seller_id}/products', data=payload)
        
        # Update batch ID in product model if it's a Django model
        if 'batchRequestId' in response and isinstance(product_data, TrendyolProduct):
            product_data.batch_id = response['batchRequestId']
            product_data.batch_status = 'processing'
            product_data.status_message = f"Submitted with batch ID: {response['batchRequestId']}"
            product_data.save()
            
        return response
    
    def get_batch_status(self, batch_id):
        """Get the status of a batch request."""
        response = self.make_request('GET', f'/product/sellers/{self.seller_id}/products/batch-requests/{batch_id}')
        return response


class TrendyolCategoryFinder:
    """
    Helper class for finding the best category match for products in Trendyol API.
    Uses sentence transformers for semantic similarity when available.
    """
    
    def __init__(self, api_client=None):
        """Initialize the category finder with the given API client."""
        self.api_client = api_client or TrendyolAPI()
        self.model = None
        self.dictionary = None
        self.categories = []
        self.categories_by_id = {}
        self.category_embeddings = {}
        
        # Try to initialize sentence-transformers model if available
        try:
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            self.dictionary = MultiDictionary()
            logger.info("Successfully initialized sentence transformer model")
        except (ImportError, NameError):
            logger.warning("sentence-transformers not available, falling back to text matching only")
            
        # Load categories from the API
        self._load_categories()
        
    def _load_categories(self):
        """Load all categories from the Trendyol API."""
        # First try to load from the database
        categories = list(TrendyolCategory.objects.all())
        if categories:
            logger.info(f"Loaded {len(categories)} categories from database")
            self.categories = categories
            self.categories_by_id = {cat.category_id: cat for cat in categories}
        else:
            # Otherwise fetch from the API
            try:
                api_categories = self.api_client.get_categories()
                
                if api_categories:
                    # Get all child categories recursively
                    all_categories = []
                    self._extract_all_categories(api_categories, all_categories)
                    
                    # Save to the database
                    for category in all_categories:
                        cat, created = TrendyolCategory.objects.get_or_create(
                            category_id=category['id'],
                            defaults={
                                'name': category['name'],
                                'parent_id': category.get('parentId'),
                                'path': ' > '.join(category.get('path', [])) if 'path' in category else None
                            }
                        )
                        if not created:
                            cat.name = category['name']
                            cat.parent_id = category.get('parentId')
                            cat.path = ' > '.join(category.get('path', [])) if 'path' in category else None
                            cat.save()
                            
                    # Refresh categories
                    self.categories = list(TrendyolCategory.objects.all())
                    self.categories_by_id = {cat.category_id: cat for cat in self.categories}
                    
                    logger.info(f"Loaded and saved {len(self.categories)} categories from API")
                else:
                    logger.warning("No categories fetched from API")
            except Exception as e:
                logger.error(f"Error loading categories from API: {str(e)}")
                
        # Precompute embeddings if we have a model
        if self.model and self.categories:
            try:
                logger.info("Computing category embeddings...")
                category_texts = [
                    f"{cat.name} {cat.path}" for cat in self.categories
                    if cat.name and (cat.path or cat.parent_id)
                ]
                
                # Compute embeddings in batches to avoid memory issues
                batch_size = 128
                if len(category_texts) > 0:
                    for i in range(0, len(category_texts), batch_size):
                        batch = category_texts[i:i + batch_size]
                        embeddings = self.model.encode(batch)
                        
                        for j, embedding in enumerate(embeddings):
                            idx = i + j
                            if idx < len(self.categories):
                                cat = self.categories[idx]
                                self.category_embeddings[cat.category_id] = embedding
                                
                    logger.info(f"Computed embeddings for {len(self.category_embeddings)} categories")
                
            except Exception as e:
                logger.error(f"Error computing category embeddings: {str(e)}")
    
    def _extract_all_categories(self, categories, result):
        """Recursively extract all categories from the API response."""
        for category in categories:
            result.append(category)
            if 'subCategories' in category and category['subCategories']:
                self._extract_all_categories(category['subCategories'], result)
                
    def _get_category_attributes(self, category_id):
        """Get attributes for a specific category with proper error handling."""
        try:
            attributes = self.api_client.get_category_attributes(category_id)
            return attributes
        except Exception as e:
            logger.error(f"Error getting attributes for category {category_id}: {str(e)}")
            return []
            
    def _get_sample_attributes(self, category_id, required_only=True):
        """
        Get sample attributes for a category to use in product submission.
        
        Args:
            category_id: Category ID to get attributes for
            required_only: Whether to include only required attributes
            
        Returns:
            List of attributes in the format expected by the API
        """
        attributes_data = self._get_category_attributes(category_id)
        result = []
        
        for attr in attributes_data:
            # Skip non-required attributes if required_only is True
            if required_only and not attr.get('required', False):
                continue
                
            attribute_id = attr.get('attribute', {}).get('id')
            attribute_name = attr.get('attribute', {}).get('name')
            
            # For required attributes, we need to provide a value
            if attribute_id:
                # Try to find a valid attribute value
                if 'attributeValues' in attr and attr['attributeValues']:
                    # Check if custom values are allowed
                    allow_custom = attr.get('allowCustom', False)
                    
                    # Get the first attribute value ID 
                    value_id = attr['attributeValues'][0]['id'] if 'id' in attr['attributeValues'][0] else None
                    value_name = attr['attributeValues'][0]['name'] if 'name' in attr['attributeValues'][0] else None
                    
                    if value_id is not None:
                        # Ensure attribute IDs are integers
                        try:
                            attribute_id = int(attribute_id)
                            value_id = int(value_id)
                        except (ValueError, TypeError):
                            logger.warning(f"Could not convert attribute ID or value to integer: {attribute_id}, {value_id}")
                            continue
                            
                        # Add to result
                        result.append({
                            "attributeId": attribute_id,
                            "attributeValueId": value_id,
                            "customAttributeValue": None
                        })
                        
                        logger.debug(f"Added sample attribute: {attribute_name} = {value_name} (ID: {value_id})")
                    elif allow_custom:
                        # Use a placeholder name for custom attribute
                        custom_value = f"Sample {attribute_name}"
                        result.append({
                            "attributeId": attribute_id,
                            "attributeValueId": 0,
                            "customAttributeValue": custom_value
                        })
                        
                        logger.debug(f"Added custom attribute: {attribute_name} = {custom_value}")
        
        return result
                
    def find_best_category(self, product_title, product_description=None):
        """
        Find the best category match for a product based on its title and description.
        
        Args:
            product_title: Product title
            product_description: Optional product description
            
        Returns:
            Best matching category ID or None if no match found
        """
        if not self.categories:
            logger.warning("No categories available for matching")
            return None
            
        # Combine title and description
        text = product_title
        if product_description:
            text = f"{product_title} {product_description}"
            
        # If we have a model, use semantic similarity
        if self.model and self.category_embeddings:
            try:
                # Encode the product text
                product_embedding = self.model.encode(text)
                
                # Find the most similar category
                best_similarity = -1
                best_category_id = None
                
                for category_id, category_embedding in self.category_embeddings.items():
                    similarity = util.pytorch_cos_sim(
                        product_embedding,
                        category_embedding
                    ).item()
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_category_id = category_id
                        
                if best_category_id:
                    category = self.categories_by_id.get(best_category_id)
                    logger.info(f"Found category '{category.name}' with similarity {best_similarity:.2f}")
                    return best_category_id
                    
            except Exception as e:
                logger.error(f"Error finding best category semantically: {str(e)}")
                
        # Fallback to simple text matching
        try:
            import difflib
            
            # Get all words from the product text
            words = text.lower().split()
            
            # Find categories with the most matching words
            matches = {}
            for category in self.categories:
                if not category.name or not category.path:
                    continue
                    
                category_text = f"{category.name} {category.path}".lower()
                match_count = sum(1 for word in words if word in category_text)
                
                if match_count > 0:
                    matches[category.category_id] = match_count
                    
            # Find the category with the most matches
            if matches:
                best_match = max(matches.items(), key=lambda x: x[1])
                category_id = best_match[0]
                category = self.categories_by_id.get(category_id)
                logger.info(f"Found category '{category.name}' with {best_match[1]} word matches")
                return category_id
                
        except Exception as e:
            logger.error(f"Error finding best category by text matching: {str(e)}")
            
        # If all else fails, return a default category
        if self.categories:
            default_category = self.categories[0]
            logger.warning(f"Using default category: {default_category.name}")
            return default_category.category_id
            
        return None
        
    def get_category_attributes_sample(self, category_id, required_only=True):
        """Get sample attributes for a category to use in product submission."""
        return self._get_sample_attributes(category_id, required_only)


class TrendyolProductManager:
    """
    Manager class for handling Trendyol product operations.
    Provides methods for creating and updating products.
    """
    
    def __init__(self, api_client=None, category_finder=None):
        """Initialize the product manager with API client and category finder."""
        self.api_client = api_client or TrendyolAPI()
        self.category_finder = category_finder or TrendyolCategoryFinder(self.api_client)
        
    def ensure_integer_attributes(self, attributes_list):
        """Ensure all attribute IDs are integers."""
        if not attributes_list:
            return []
            
        result = []
        
        for attr in attributes_list:
            if isinstance(attr, dict):
                new_attr = attr.copy()
                # Convert attributeId to integer
                if 'attributeId' in new_attr:
                    try:
                        new_attr['attributeId'] = int(new_attr['attributeId'])
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert attributeId to integer: {new_attr['attributeId']}")
                        continue
                
                # Convert attributeValueId to integer
                if 'attributeValueId' in new_attr:
                    try:
                        new_attr['attributeValueId'] = int(new_attr['attributeValueId'])
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert attributeValueId to integer: {new_attr['attributeValueId']}")
                        continue
                    
                result.append(new_attr)
            
        return result
        
    def _build_product_payload(self, product, category_id, brand_id, attributes):
        """Build a product payload with proper attribute format."""
        # Ensure attributes have integer IDs
        attributes = self.ensure_integer_attributes(attributes)
        
        payload = {
            "items": [
                {
                    "barcode": product.barcode,
                    "title": product.title[:100].strip(),
                    "productMainId": product.product_main_id or product.barcode,
                    "brandId": brand_id,
                    "categoryId": category_id,
                    "quantity": product.quantity or 10,
                    "stockCode": product.stock_code or product.barcode,
                    "dimensionalWeight": 1,
                    "description": (product.description or product.title)[:500],
                    "currencyType": product.currency_type or "TRY",
                    "listPrice": float(product.price),
                    "salePrice": float(product.price),
                    "vatRate": product.vat_rate or 20,
                    "cargoCompanyId": 17,
                    "shipmentAddressId": 0,
                    "deliveryDuration": 3,
                    "images": [{"url": product.image_url}],
                    "attributes": attributes
                }
            ]
        }
        
        return payload
        
    def find_brand_id(self, product):
        """Find a brand ID for a product based on its brand name."""
        brand_name = product.brand_name
        if not brand_name:
            logger.warning(f"No brand name provided for product {product.id}")
            return None
            
        # First check if brand exists in the database
        try:
            brand = TrendyolBrand.objects.filter(name__iexact=brand_name).first()
            if brand:
                logger.info(f"Using existing brand ID {brand.brand_id} for {brand_name}")
                return brand.brand_id
        except Exception as e:
            logger.error(f"Error checking brand in database: {str(e)}")
            
        # Otherwise search the API
        try:
            brands = self.api_client.get_brands(brand_name)
            if brands:
                # Find exact or close match
                for brand in brands:
                    if brand.get('name', '').lower() == brand_name.lower():
                        # Save to database for future use
                        try:
                            TrendyolBrand.objects.create(
                                brand_id=brand['id'],
                                name=brand['name']
                            )
                        except Exception as e:
                            logger.error(f"Error saving brand to database: {str(e)}")
                            
                        logger.info(f"Found exact brand match: {brand['name']} (ID: {brand['id']})")
                        return brand['id']
                
                # If no exact match, use the first result
                brand = brands[0]
                
                # Save to database for future use
                try:
                    TrendyolBrand.objects.create(
                        brand_id=brand['id'],
                        name=brand['name']
                    )
                except Exception as e:
                    logger.error(f"Error saving brand to database: {str(e)}")
                    
                logger.info(f"Using closest brand match: {brand['name']} (ID: {brand['id']})")
                return brand['id']
        except Exception as e:
            logger.error(f"Error finding brand ID: {str(e)}")
            
        # Default to a common brand if available
        try:
            default_brand = TrendyolBrand.objects.first()
            if default_brand:
                logger.warning(f"Using default brand ID {default_brand.brand_id}")
                return default_brand.brand_id
        except Exception:
            pass
            
        logger.error(f"Could not find brand ID for {brand_name}")
        return None
        
    def create_product(self, product):
        """
        Create a product in Trendyol using intelligent category and attribute mapping.
        
        Args:
            product: TrendyolProduct instance
            
        Returns:
            Batch ID if successful, None otherwise
        """
        # Find suitable category
        if not product.category_id:
            category_id = self.category_finder.find_best_category(
                product.title,
                product.description
            )
            if not category_id:
                logger.error(f"Could not find category for product {product.id}")
                return None
        else:
            category_id = product.category_id
            
        # Find brand ID
        if not product.brand_id:
            brand_id = self.find_brand_id(product)
            if not brand_id:
                logger.error(f"Could not find brand ID for product {product.id}")
                return None
        else:
            brand_id = product.brand_id
            
        # Get attributes if not provided
        if not product.attributes:
            attributes = self.category_finder.get_category_attributes_sample(category_id)
        else:
            attributes = product.attributes
            
        # Build and submit payload
        try:
            payload = self._build_product_payload(product, category_id, brand_id, attributes)
            response = self.api_client.make_request(
                'POST',
                f'/product/sellers/{self.api_client.seller_id}/products',
                data=payload
            )
            
            if 'batchRequestId' in response:
                batch_id = response['batchRequestId']
                
                # Update product in database
                product.category_id = category_id
                product.brand_id = brand_id
                product.attributes = attributes
                product.batch_id = batch_id
                product.batch_status = 'processing'
                product.status_message = f"Submitted with batch ID: {batch_id}"
                product.save()
                
                logger.info(f"Created product {product.id} with batch ID {batch_id}")
                return batch_id
            else:
                logger.error(f"Failed to create product {product.id}: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating product {product.id}: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"API Response: {e.response.status_code} - {e.response.text}")
            return None
            
    def check_batch_status(self, batch_id):
        """
        Check the status of a product batch request.
        
        Args:
            batch_id: Batch ID to check
            
        Returns:
            Tuple of (status, items, failureReasons) if successful
            Tuple of (None, None, error_message) otherwise
        """
        try:
            response = self.api_client.get_batch_status(batch_id)
            
            if 'status' not in response:
                return None, None, "Invalid response from API"
                
            status = response['status']
            items = response.get('items', [])
            
            # Check for any failures
            failure_reasons = []
            for item in items:
                if 'status' in item and item['status'] == 'FAILED':
                    if 'failureReasons' in item:
                        failure_reasons.extend(item['failureReasons'])
                    if 'productId' in item:
                        failure_reasons.append(f"Failed product ID: {item['productId']}")
                        
            return status, items, failure_reasons
            
        except Exception as e:
            logger.error(f"Error checking batch status {batch_id}: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"API Response: {e.response.status_code} - {e.response.text}")
            return None, None, str(e)
            
    def update_product_status(self, product):
        """
        Update the status of a product based on its batch ID.
        
        Args:
            product: TrendyolProduct instance
            
        Returns:
            True if successful, False otherwise
        """
        if not product.batch_id:
            logger.warning(f"Product {product.id} has no batch ID")
            return False
            
        status, items, failure_reasons = self.check_batch_status(product.batch_id)
        
        if status is None:
            product.batch_status = 'error'
            product.status_message = failure_reasons
            product.save()
            return False
            
        product.batch_status = status.lower()
        
        if failure_reasons:
            product.status_message = "; ".join(failure_reasons)
        else:
            product.status_message = f"Batch status: {status}"
            
        product.save()
        return True


def get_api_client_from_config():
    """Get a TrendyolAPI instance using the active config from the database."""
    return TrendyolAPI()


def get_product_manager():
    """Get a TrendyolProductManager instance."""
    api = get_api_client_from_config()
    return TrendyolProductManager(api)


def find_best_category_match(product: TrendyolProduct) -> int:
    """Find the best category match for a product."""
    manager = get_product_manager()
    return manager.category_finder.find_best_category(product.title, product.description)


def find_best_brand_match(product: TrendyolProduct) -> int:
    """Find the best brand match for a product."""
    manager = get_product_manager()
    return manager.find_brand_id(product)


def create_trendyol_product(product: TrendyolProduct) -> str:
    """Create a product in Trendyol."""
    manager = get_product_manager()
    return manager.create_product(product)


def check_batch_status(batch_id: str) -> tuple:
    """Check the status of a batch request."""
    manager = get_product_manager()
    return manager.check_batch_status(batch_id)


def check_product_batch_status(product: TrendyolProduct) -> str:
    """Check the batch status of a product."""
    manager = get_product_manager()
    return manager.update_product_status(product)


def sync_product_to_trendyol(product: TrendyolProduct) -> bool:
    """Sync a product to Trendyol."""
    # Check if product already has a batch ID
    if product.batch_id:
        # Check batch status
        manager = get_product_manager()
        status, _, failure_reasons = manager.check_batch_status(product.batch_id)
        
        if status == 'COMPLETED':
            if failure_reasons:
                # If there were failures, try to submit the product again
                logger.info(f"Product {product.id} batch completed with failures, resubmitting")
                batch_id = create_trendyol_product(product)
                return batch_id is not None
            else:
                # Product was successfully submitted
                logger.info(f"Product {product.id} already submitted successfully")
                return True
                
    # Submit the product
    batch_id = create_trendyol_product(product)
    return batch_id is not None


def batch_process_products(products, process_func, batch_size=10, delay=0.5):
    """
    Process products in batches.
    
    Args:
        products: Queryset or list of products to process
        process_func: Function to call for each product
        batch_size: Number of products to process in each batch
        delay: Delay between batches in seconds
        
    Returns:
        Tuple of (success_count, failed_count, errors)
    """
    total = len(products) if hasattr(products, '__len__') else products.count()
    success_count = 0
    failed_count = 0
    errors = []
    
    logger.info(f"Processing {total} products in batches of {batch_size}")
    
    for i in tqdm(range(0, total, batch_size)):
        batch = products[i:i + batch_size] if hasattr(products, '__getitem__') else products[i:i + batch_size]
        
        for product in batch:
            try:
                result = process_func(product)
                if result:
                    success_count += 1
                else:
                    failed_count += 1
                    errors.append(f"Failed to process product {product.id}")
            except Exception as e:
                failed_count += 1
                error_msg = f"Error processing product {product.id}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                
        # Add delay between batches to avoid rate limiting
        if i + batch_size < total and delay > 0:
            time.sleep(delay)
            
    logger.info(f"Processed {total} products: {success_count} successful, {failed_count} failed")
    
    return success_count, failed_count, errors
