import logging
import json
import requests
import base64
from typing import Dict, List, Optional, Any

from django.utils import timezone

from .models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct

logger = logging.getLogger(__name__)


class TrendyolApi:
    """Custom Trendyol API client implementation"""

    def __init__(self,
                api_key,
                api_secret,
                supplier_id,
                base_url='https://api.trendyol.com/sapigw',
                user_agent=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.supplier_id = supplier_id

        # Ensure consistent URL format
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        self.base_url = base_url

        self.user_agent = user_agent or f"{supplier_id} - SelfIntegration"
        self.brands = BrandsAPI(self)
        self.categories = CategoriesAPI(self)
        self.products = ProductsAPI(self)
        self.inventory = InventoryAPI(self)

    def make_request(self, method, endpoint, data=None, params=None):
        """Make a request to the Trendyol API"""
        # Make sure endpoint starts with a slash
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'

        # Build the URL with proper formatting
        url = f"{self.base_url}{endpoint}"

        # Format the auth string and encode as Base64 for Basic Authentication
        auth_string = f"{self.api_key}:{self.api_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()

        headers = {
            'Authorization': f"Basic {auth_encoded}",
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
        }

        logger.info(f"Making request: {method} {url}")

        try:
            # Make the request
            response = requests.request(method=method,
                                        url=url,
                                        headers=headers,
                                        params=params,
                                        json=data,
                                        timeout=30)

            # Log response status
            logger.info(f"Response status: {response.status_code}")

            # Check if the request was successful
            response.raise_for_status()

            # Parse the response JSON
            try:
                result = response.json()
                return result
            except ValueError:
                # If the response is not JSON, return the response text
                return {"response": response.text}

        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Trendyol API: {str(e)}")
            error_details = {}
            if hasattr(e, 'response') and e.response:
                error_details['status_code'] = e.response.status_code
                error_details['response_text'] = e.response.text

            # Return an error response object instead of None
            return {"error": True, "message": str(e), "details": error_details}


class BrandsAPI:
    """Trendyol Brands API"""

    def __init__(self, client):
        self.client = client

    def get_brands(self, page=0, size=1000):
        """Get all brands from Trendyol"""
        endpoint = '/product/brands'
        params = {'page': page, 'size': size}
        return self.client.make_request('GET', endpoint, params=params)

    def get_brand_by_name(self, name):
        """Get brand by name"""
        endpoint = '/product/brands/by-name'
        params = {'name': name}
        return self.client.make_request('GET', endpoint, params=params)


class CategoriesAPI:
    """Trendyol Categories API"""

    def __init__(self, client):
        self.client = client

    def get_categories(self):
        """Get all categories from Trendyol"""
        endpoint = '/product-categories'
        return self.client.make_request('GET', endpoint)

    def get_category_attributes(self, category_id):
        """Get attributes for a specific category"""
        endpoint = f'/product/product-categories/{category_id}/attributes'
        return self.client.make_request('GET', endpoint)


class ProductsAPI:
    """Trendyol Products API"""

    def __init__(self, client):
        self.client = client

    def create_products(self, products):
        """Create products on Trendyol"""
        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products'
        return self.client.make_request('POST', endpoint, data={"items": products})

    def update_products(self, products):
        """Update existing products on Trendyol"""
        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products'
        return self.client.make_request('PUT', endpoint, data={"items": products})

    def delete_products(self, barcodes):
        """Delete products from Trendyol"""
        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products'
        items = [{"barcode": barcode} for barcode in barcodes]
        return self.client.make_request('DELETE', endpoint, data={"items": items})

    def get_batch_request_status(self, batch_id):
        """Get the status of a batch request"""
        # Make sure we have a valid batch ID before making request
        if not batch_id:
            logger.warning("Attempted to check batch status with empty batch ID")
            return None

        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products/batch-requests/{batch_id}'
        return self.client.make_request('GET', endpoint)

    def get_products(self, barcode=None, approved=None, page=0, size=50):
        """Get products from Trendyol"""
        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products'
        params = {'page': page, 'size': size}

        if barcode:
            params['barcode'] = barcode

        if approved is not None:
            params['approved'] = approved

        return self.client.make_request('GET', endpoint, params=params)

    def get_product_by_barcode(self, barcode):
        """Get product by barcode"""
        return self.get_products(barcode=barcode, page=0, size=1)


class InventoryAPI:
    """Trendyol Inventory API for price and stock updates"""

    def __init__(self, client):
        self.client = client

    def update_price_and_inventory(self, items):
        """
        Update price and inventory for products
        
        Args:
            items: List of dictionaries with barcode, quantity, salePrice, and listPrice
                  Example: [{"barcode": "123456", "quantity": 10, "salePrice": 100.0, "listPrice": 120.0}]
        
        Returns:
            Dictionary with batchRequestId if successful
        """
        endpoint = f'/integration/inventory/sellers/{self.client.supplier_id}/products/price-and-inventory'
        return self.client.make_request('POST', endpoint, data={"items": items})


def get_api_client() -> Optional[TrendyolApi]:
    """
    Get a configured Trendyol API client.
    Returns None if no active API configuration is found.
    """
    try:
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            logger.error("No active Trendyol API configuration found")
            return None

        # Get the user_agent from the config, or create a default one
        user_agent = config.user_agent
        if not user_agent:
            user_agent = f"{config.seller_id} - SelfIntegration"

        # Initialize the Trendyol API client
        client = TrendyolApi(
            api_key=config.api_key,
            api_secret=config.api_secret,
            supplier_id=config.seller_id,
            base_url=config.base_url,
            user_agent=user_agent
        )

        return client
    except Exception as e:
        logger.error(f"Error creating Trendyol API client: {str(e)}")
        return None


def create_trendyol_product(source_product):
    """
    Create a TrendyolProduct from a source product
    """
    from trendyol.simple_category_finder import find_best_category_match

    # Get the API client
    api_client = get_api_client()
    if not api_client:
        return None, "No active Trendyol API configuration found"

    # Try to find a matching brand
    brand_name = source_product.brand
    brand_response = api_client.brands.get_brand_by_name(brand_name)
    
    brand_id = None
    if not isinstance(brand_response, dict) or 'error' not in brand_response:
        if isinstance(brand_response, list) and len(brand_response) > 0:
            brand_id = brand_response[0]['id']
            logger.info(f"Using existing brand ID: {brand_id}")
    
    if not brand_id:
        # If no brand is found, use a default/fallback brand ID
        # This should be replaced with proper error handling
        logger.warning(f"Brand not found: {brand_name}")
        brand_id = 1  # Default brand ID (update based on your needs)
        
    # Find the best category match
    category_result = find_best_category_match(source_product.category_name)
    if not category_result:
        return None, f"Could not find a matching category for {source_product.category_name}"
    
    category_id = category_result.category_id
    
    # Create the product payload
    trendyol_product = TrendyolProduct(
        title=source_product.name,
        description=source_product.description,
        brand_id=brand_id,
        category_id=category_id,
        source_product=source_product,
        barcode=f"LCW{source_product.id}",
        list_price=float(source_product.price),
        sale_price=float(source_product.price),
        vat_rate=10,  # Default VAT rate
        stock_code=f"LCW{source_product.id}",
        cargo_company_id=17,  # Default cargo company ID
        dimensional_weight=1,  # Default dimensional weight
        attributes=[],  # Empty attributes
        images=[{"url": image.image_url} for image in source_product.images.all()]
    )
    
    return trendyol_product, None


def send_product_to_trendyol(product):
    """
    Send a product to Trendyol
    """
    api_client = get_api_client()
    if not api_client:
        return None, "No active Trendyol API configuration found"
    
    # Format the product data for Trendyol
    product_data = {
        "barcode": product.barcode,
        "title": product.title,
        "productMainId": product.barcode,
        "brandId": product.brand_id,
        "categoryId": product.category_id,
        "listPrice": product.list_price,
        "salePrice": product.sale_price,
        "vatRate": product.vat_rate,
        "stockCode": product.stock_code,
        "cargoCompanyId": product.cargo_company_id,
        "dimensionalWeight": product.dimensional_weight,
        "description": product.description,
        "attributes": product.attributes,
        "images": product.images
    }
    
    # Print debug info
    print(f"[DEBUG-CREATE] Ürün gönderiliyor: {product.title}")
    print(f"[DEBUG-CREATE] Gönderilen veri: {json.dumps(product_data, indent=2)}")
    
    # Send the product to Trendyol
    response = api_client.products.create_products([product_data])
    
    # Print debug info
    print(f"[DEBUG-CREATE] Trendyol'dan gelen yanıt: {json.dumps(response, indent=2)}")
    
    if 'error' in response:
        return None, f"Error sending product to Trendyol: {response['message']}"
    
    if 'batchRequestId' in response:
        batch_id = response['batchRequestId']
        product.batch_id = batch_id
        product.batch_status = 'pending'
        product.save()
        
        return batch_id, None
    
    return None, "Unknown error sending product to Trendyol"