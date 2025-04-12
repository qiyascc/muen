"""
Updated Trendyol API client with working endpoints.

This module contains the updated TrendyolAPI class that uses the 
endpoints verified to work with the current Trendyol API version.
"""

import base64
import json
import logging
import requests
import time
from django.utils import timezone
from trendyol.models import TrendyolAPIConfig

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
                    "vatRate": product_data.vat_rate or 10,
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
        response = self.make_request('GET', f'/product/suppliers/{self.seller_id}/products/batch-requests/{batch_id}')
        return response
