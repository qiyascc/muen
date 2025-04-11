import logging
import json
import time
import requests
import base64
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union

from django.utils import timezone

from .models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct

logger = logging.getLogger(__name__)


class TrendyolApi:
    """Custom Trendyol API client implementation"""
    
    def __init__(self, api_key, api_secret, supplier_id, api_url='https://apigw.trendyol.com/integration'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.supplier_id = supplier_id
        self.api_url = api_url
        self.brands = BrandsAPI(self)
        self.categories = CategoriesAPI(self)
        self.products = ProductsAPI(self)
        self.inventory = InventoryAPI(self)
        
    def make_request(self, method, endpoint, data=None, params=None):
        """Make a request to the Trendyol API"""
        url = f"{self.api_url}{endpoint}"
        
        # Format the auth string and encode as Base64 for Basic Authentication
        auth_string = f"{self.api_key}:{self.api_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()
        
        # Create User-Agent header with supplier ID
        user_agent = f"{self.supplier_id} - SelfIntegration"
        
        headers = {
            'Authorization': f"Basic {auth_encoded}",
            'Content-Type': 'application/json',
            'User-Agent': user_agent,
        }
        
        logger.debug(f"Making {method} request to {url}")
        if data:
            logger.debug(f"Request data: {json.dumps(data)}")
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=30
            )
            
            # Log response status
            logger.debug(f"Response status: {response.status_code}")
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Parse the response JSON
            try:
                result = response.json()
                logger.debug(f"Response data: {json.dumps(result)}")
                return result
            except ValueError:
                # If the response is not JSON, return the response text
                logger.debug(f"Response text: {response.text}")
                return {"response": response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Trendyol API: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            return None


class BrandsAPI:
    """Trendyol Brands API"""
    
    def __init__(self, client):
        self.client = client
        
    def get_brands(self, page=0, size=1000):
        """Get all brands from Trendyol"""
        endpoint = '/product/brands'
        params = {
            'page': page,
            'size': size
        }
        return self.client.make_request('GET', endpoint, params=params)
    
    def get_brand_by_name(self, name):
        """Get brand by name"""
        endpoint = '/product/brands/by-name'
        params = {
            'name': name
        }
        return self.client.make_request('GET', endpoint, params=params)


class CategoriesAPI:
    """Trendyol Categories API"""
    
    def __init__(self, client):
        self.client = client
        
    def get_categories(self):
        """Get all categories from Trendyol"""
        endpoint = '/product/product-categories'
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
        endpoint = f'/product/sellers/{self.client.supplier_id}/products'
        return self.client.make_request('POST', endpoint, data={"items": products})
        
    def update_products(self, products):
        """Update existing products on Trendyol"""
        endpoint = f'/product/sellers/{self.client.supplier_id}/products'
        return self.client.make_request('PUT', endpoint, data={"items": products})
        
    def delete_products(self, barcodes):
        """Delete products from Trendyol"""
        endpoint = f'/product/sellers/{self.client.supplier_id}/products'
        items = [{"barcode": barcode} for barcode in barcodes]
        return self.client.make_request('DELETE', endpoint, data={"items": items})
        
    def get_batch_request_status(self, batch_id):
        """Get the status of a batch request"""
        endpoint = f'/product/sellers/{self.client.supplier_id}/products/batch-requests/{batch_id}'
        return self.client.make_request('GET', endpoint)
        
    def get_products(self, barcode=None, approved=None, page=0, size=50):
        """Get products from Trendyol"""
        endpoint = f'/product/sellers/{self.client.supplier_id}/products'
        params = {
            'page': page,
            'size': size
        }
        
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
        endpoint = f'/inventory/sellers/{self.client.supplier_id}/products/price-and-inventory'
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
        
        # Initialize the Trendyol API client
        client = TrendyolApi(
            api_key=config.api_key,
            api_secret=config.api_secret,
            supplier_id=config.seller_id,
            api_url=config.base_url
        )
        
        return client
    except Exception as e:
        logger.error(f"Error creating Trendyol API client: {str(e)}")
        return None


def fetch_brands() -> List[Dict[str, Any]]:
    """
    Fetch all brands from Trendyol and update the local database.
    Returns a list of brand dictionaries.
    """
    client = get_api_client()
    if not client:
        return []
    
    try:
        # Fetch brands from Trendyol
        response = client.brands.get_brands()
        
        if not response or 'brands' not in response:
            logger.error("Failed to fetch brands from Trendyol API")
            return []
        
        brands = response.get('brands', [])
        
        # Update or create brands in our database
        for brand in brands:
            brand_id = brand.get('id')
            name = brand.get('name')
            
            if brand_id and name:
                TrendyolBrand.objects.update_or_create(
                    brand_id=brand_id,
                    defaults={
                        'name': name,
                        'is_active': True
                    }
                )
        
        return brands
    except Exception as e:
        logger.error(f"Error fetching brands from Trendyol: {str(e)}")
        return []


def fetch_categories() -> List[Dict[str, Any]]:
    """
    Fetch all categories from Trendyol and update the local database.
    Returns a list of category dictionaries.
    """
    client = get_api_client()
    if not client:
        return []
    
    try:
        # Fetch categories from Trendyol
        response = client.categories.get_categories()
        
        if not response or 'categories' not in response:
            logger.error("Failed to fetch categories from Trendyol API")
            return []
        
        categories = response.get('categories', [])
        
        # Update or create categories in our database
        for category in categories:
            category_id = category.get('id')
            name = category.get('name')
            parent_id = category.get('parentId')
            
            if category_id and name:
                # Build category path
                path = name
                if parent_id:
                    try:
                        parent = TrendyolCategory.objects.get(category_id=parent_id)
                        path = f"{parent.path} > {name}"
                    except TrendyolCategory.DoesNotExist:
                        pass
                
                TrendyolCategory.objects.update_or_create(
                    category_id=category_id,
                    defaults={
                        'name': name,
                        'parent_id': parent_id,
                        'path': path,
                        'is_active': True
                    }
                )
        
        return categories
    except Exception as e:
        logger.error(f"Error fetching categories from Trendyol: {str(e)}")
        return []


def find_best_category_match(product: TrendyolProduct) -> Optional[int]:
    """
    Find the best matching category for a product.
    Returns the category ID if found, None otherwise.
    """
    # If we already have a category ID, use it
    if product.category_id:
        # Verify the category exists
        try:
            TrendyolCategory.objects.get(category_id=product.category_id)
            return product.category_id
        except TrendyolCategory.DoesNotExist:
            pass
    
    # Try to find by category name
    if product.category_name:
        try:
            # Try exact match first
            category = TrendyolCategory.objects.filter(
                name__iexact=product.category_name,
                is_active=True
            ).first()
            
            if category:
                return category.category_id
            
            # Try partial match
            category = TrendyolCategory.objects.filter(
                name__icontains=product.category_name,
                is_active=True
            ).first()
            
            if category:
                return category.category_id
        except Exception as e:
            logger.error(f"Error finding category by name: {str(e)}")
    
    # If we have a related LCWaikiki product, use its category
    if product.lcwaikiki_product and product.lcwaikiki_product.category:
        try:
            # Try to find similar category
            category = TrendyolCategory.objects.filter(
                name__icontains=product.lcwaikiki_product.category,
                is_active=True
            ).first()
            
            if category:
                return category.category_id
        except Exception as e:
            logger.error(f"Error finding category from LCWaikiki product: {str(e)}")
    
    # If all else fails, return None or a default category ID
    return None


def find_best_brand_match(product: TrendyolProduct) -> Optional[int]:
    """
    Find the best matching brand for a product.
    Returns the brand ID if found, None otherwise.
    """
    # If we already have a brand ID, use it
    if product.brand_id:
        # Verify the brand exists
        try:
            TrendyolBrand.objects.get(brand_id=product.brand_id)
            return product.brand_id
        except TrendyolBrand.DoesNotExist:
            pass
    
    # Try to find by brand name
    if product.brand_name:
        try:
            # Try exact match first
            brand = TrendyolBrand.objects.filter(
                name__iexact=product.brand_name,
                is_active=True
            ).first()
            
            if brand:
                return brand.brand_id
            
            # Try partial match
            brand = TrendyolBrand.objects.filter(
                name__icontains=product.brand_name,
                is_active=True
            ).first()
            
            if brand:
                return brand.brand_id
        except Exception as e:
            logger.error(f"Error finding brand by name: {str(e)}")
    
    # If we have a related LCWaikiki product, assume it's LCWaikiki brand
    if product.lcwaikiki_product:
        try:
            brand = TrendyolBrand.objects.filter(
                name__icontains="LCW",
                is_active=True
            ).first()
            
            if brand:
                return brand.brand_id
        except Exception as e:
            logger.error(f"Error finding LCW brand: {str(e)}")
    
    # If all else fails, return None
    return None


def get_required_attributes_for_category(category_id: int) -> List[Dict[str, Any]]:
    """
    Get required attributes for a specific category.
    Returns a list of attribute dictionaries.
    """
    client = get_api_client()
    if not client or not category_id:
        return []
    
    try:
        # Fetch category attributes from Trendyol
        response = client.categories.get_category_attributes(category_id)
        
        if not response or 'categoryAttributes' not in response:
            logger.error(f"Failed to fetch attributes for category {category_id}")
            return []
        
        category_attributes = response.get('categoryAttributes', [])
        
        # Filter required attributes
        required_attributes = [
            attr for attr in category_attributes 
            if attr.get('required', False) and attr.get('allowCustom', False)
        ]
        
        return required_attributes
    except Exception as e:
        logger.error(f"Error fetching category attributes: {str(e)}")
        return []


def prepare_product_data(product: TrendyolProduct) -> Dict[str, Any]:
    """
    Prepare product data for Trendyol API.
    Returns a dictionary with the product data.
    """
    # Validate required fields
    if not product.title or not product.barcode or not product.price:
        logger.error(f"Product {product.id} is missing required fields")
        raise ValueError("Product is missing required fields: title, barcode, or price")
    
    # Find best category and brand matches
    category_id = find_best_category_match(product)
    brand_id = find_best_brand_match(product)
    
    if not category_id:
        logger.error(f"No matching category found for product {product.id}")
        raise ValueError("No matching category found for product")
    
    if not brand_id:
        logger.error(f"No matching brand found for product {product.id}")
        raise ValueError("No matching brand found for product")
    
    # Get image URLs
    image_urls = []
    if product.image_url:
        image_urls.append(product.image_url)
    
    if product.additional_images:
        if isinstance(product.additional_images, list):
            image_urls.extend(product.additional_images)
        elif isinstance(product.additional_images, str):
            try:
                additional = json.loads(product.additional_images)
                if isinstance(additional, list):
                    image_urls.extend(additional)
            except json.JSONDecodeError:
                pass
    
    # Prepare attributes
    attributes = []
    if product.attributes:
        if isinstance(product.attributes, dict):
            for key, value in product.attributes.items():
                attributes.append({
                    "attributeId": key,
                    "attributeValueId": value
                })
        elif isinstance(product.attributes, str):
            try:
                attrs = json.loads(product.attributes)
                if isinstance(attrs, dict):
                    for key, value in attrs.items():
                        attributes.append({
                            "attributeId": key,
                            "attributeValueId": value
                        })
            except json.JSONDecodeError:
                pass
    
    # If no attributes are set, check if there are required attributes for the category
    if not attributes:
        required_attrs = get_required_attributes_for_category(category_id)
        for attr in required_attrs:
            attr_id = attr.get('id')
            if attr_id and attr.get('allowCustom', False) and attr.get('values', []):
                # Use the first value as a default
                value_id = attr.get('values', [])[0].get('id')
                if value_id:
                    attributes.append({
                        "attributeId": attr_id,
                        "attributeValueId": value_id
                    })
    
    # Prepare product data
    product_data = {
        "barcode": product.barcode,
        "title": product.title,
        "productMainId": product.product_main_id or product.barcode,
        "brandId": brand_id,
        "categoryId": category_id,
        "stockCode": product.stock_code or product.barcode,
        "quantity": product.quantity,
        "stockUnitType": "PIECE",  # Default to pieces
        "dimensionalWeight": 1,  # Default to 1kg
        "description": product.description,
        "currencyType": product.currency_type,
        "listPrice": float(product.price),
        "salePrice": float(product.price),
        "vatRate": product.vat_rate,
        "cargoCompanyId": 0,  # Default cargo company
        "images": [{"url": url} for url in image_urls if url],
        "attributes": attributes,
    }
    
    return product_data


def create_trendyol_product(product: TrendyolProduct) -> Optional[str]:
    """
    Create a product on Trendyol using the new API structure.
    Returns the batch ID if successful, None otherwise.
    """
    client = get_api_client()
    if not client:
        product.batch_status = 'failed'
        product.status_message = "No active Trendyol API configuration found"
        product.save()
        return None
    
    try:
        # Prepare product data
        product_data = prepare_product_data(product)
        
        # Create the product on Trendyol
        response = client.products.create_products([product_data])
        
        if not response or 'batchRequestId' not in response:
            logger.error(f"Failed to create product {product.id} on Trendyol")
            product.batch_status = 'failed'
            product.status_message = "Failed to create product on Trendyol: No batch request ID returned"
            product.save()
            return None
        
        batch_id = response.get('batchRequestId')
        
        # Update product with batch ID and status
        product.batch_id = batch_id
        product.batch_status = 'processing'
        product.status_message = "Product creation initiated"
        product.save()
        
        return batch_id
    except Exception as e:
        logger.error(f"Error creating product {product.id} on Trendyol: {str(e)}")
        product.batch_status = 'failed'
        product.status_message = f"Error creating product: {str(e)}"
        product.save()
        return None


def check_product_batch_status(product: TrendyolProduct) -> str:
    """
    Check the status of a product batch on Trendyol.
    Updates the product with the status and returns the status.
    """
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
        # Check batch status
        response = client.products.get_batch_request_status(product.batch_id)
        
        if not response:
            logger.error(f"Failed to check batch status for product {product.id} on Trendyol")
            product.batch_status = 'failed'
            product.status_message = "Failed to check batch status: No response from API"
            product.save()
            return 'failed'
        
        # Get batch status details
        status = response.get('status', 'failed')
        
        # Map Trendyol status to our status
        status_mapping = {
            'PROCESSING': 'processing',
            'DONE': 'completed',
            'FAILED': 'failed',
        }
        
        internal_status = status_mapping.get(status, 'failed')
        
        # Get error message if any
        error_message = ""
        if 'items' in response:
            items = response.get('items', [])
            for item in items:
                if item.get('status') in ['FAILED', 'INVALID']:
                    errors = item.get('failureReasons', [])
                    for error in errors:
                        if error.get('message'):
                            error_message += error.get('message') + ". "
        
        # If status is completed and no Trendyol ID, try to get it
        if internal_status == 'completed' and not product.trendyol_id:
            # Try to get the product ID from Trendyol
            try:
                products_response = client.products.get_product_by_barcode(product.barcode)
                if products_response and 'content' in products_response and products_response['content']:
                    trendyol_product = products_response['content'][0]
                    product.trendyol_id = str(trendyol_product.get('id', ''))
                    product.trendyol_url = f"https://www.trendyol.com/brand/name-p-{product.trendyol_id}"
            except Exception as e:
                logger.error(f"Error getting product ID from Trendyol: {str(e)}")
        
        # Update product status
        product.batch_status = internal_status
        product.status_message = error_message if error_message else f"Batch status: {status}"
        product.last_check_time = timezone.now()
        
        if internal_status == 'completed':
            product.last_sync_time = timezone.now()
        
        product.save()
        
        return internal_status
    except Exception as e:
        logger.error(f"Error checking batch status for product {product.id} on Trendyol: {str(e)}")
        product.batch_status = 'failed'
        product.status_message = f"Error checking batch status: {str(e)}"
        product.save()
        return 'failed'


def update_price_and_inventory(product: TrendyolProduct) -> Optional[str]:
    """
    Update only the price and inventory for an existing product on Trendyol.
    This uses the dedicated price and inventory update endpoint.
    
    Returns:
        The batch request ID if successful, None otherwise.
    """
    client = get_api_client()
    if not client:
        product.batch_status = 'failed'
        product.status_message = "No active Trendyol API configuration found"
        product.save()
        return None
    
    try:
        # Prepare price and inventory data
        item_data = {
            "barcode": product.barcode,
            "quantity": product.quantity,
            "salePrice": float(product.price),
            "listPrice": float(product.price * Decimal('1.05'))  # 5% higher for list price
        }
        
        # Update price and inventory on Trendyol
        response = client.inventory.update_price_and_inventory([item_data])
        
        if not response or 'batchRequestId' not in response:
            logger.error(f"Failed to update price and inventory for product {product.id} on Trendyol")
            product.batch_status = 'failed'
            product.status_message = "Failed to update price and inventory: No batch request ID returned"
            product.save()
            return None
        
        batch_id = response.get('batchRequestId')
        
        # Update product with batch ID and status
        product.batch_id = batch_id
        product.batch_status = 'processing'
        product.status_message = "Price and inventory update initiated"
        product.save()
        
        return batch_id
    except Exception as e:
        logger.error(f"Error updating price and inventory for product {product.id} on Trendyol: {str(e)}")
        product.batch_status = 'failed'
        product.status_message = f"Error updating price and inventory: {str(e)}"
        product.save()
        return None


def sync_product_to_trendyol(product: TrendyolProduct) -> bool:
    """
    Sync a product to Trendyol.
    Returns True if successful, False otherwise.
    
    This function determines whether to create a new product or just update
    price and inventory based on the product's status.
    """
    # First check if the product already exists on Trendyol
    if product.trendyol_id:
        # Product exists, just update price and inventory
        batch_id = update_price_and_inventory(product)
        return bool(batch_id)
    
    # If product has a batch ID, check its status
    if product.batch_id:
        status = check_product_batch_status(product)
        if status == 'completed':
            # Product was created successfully, update price and inventory
            if not product.trendyol_id:
                # Try to get the product ID one more time
                try:
                    client = get_api_client()
                    if client:
                        products_response = client.products.get_product_by_barcode(product.barcode)
                        if products_response and 'content' in products_response and products_response['content']:
                            trendyol_product = products_response['content'][0]
                            product.trendyol_id = str(trendyol_product.get('id', ''))
                            product.trendyol_url = f"https://www.trendyol.com/brand/name-p-{product.trendyol_id}"
                            product.save()
                except Exception as e:
                    logger.error(f"Error getting product ID from Trendyol: {str(e)}")
            
            # Now update price and inventory
            batch_id = update_price_and_inventory(product)
            return bool(batch_id)
        elif status == 'failed':
            # Creation failed, try again
            batch_id = create_trendyol_product(product)
            return bool(batch_id)
        elif status == 'processing':
            # If still processing, do nothing
            return True
        else:
            # Unknown status, try creating a new batch
            batch_id = create_trendyol_product(product)
            return bool(batch_id)
    else:
        # No batch ID, create a new product
        batch_id = create_trendyol_product(product)
        return bool(batch_id)


def lcwaikiki_to_trendyol_product(lcw_product) -> Optional[TrendyolProduct]:
    """
    Convert an LCWaikiki product to a Trendyol product.
    Returns the created or updated Trendyol product instance.
    """
    if not lcw_product:
        return None
    
    try:
        # Check if a Trendyol product already exists for this LCWaikiki product
        trendyol_product = TrendyolProduct.objects.filter(
            lcwaikiki_product=lcw_product
        ).first()
        
        if not trendyol_product:
            # Create a new Trendyol product
            barcode = lcw_product.product_code or f"LCW-{lcw_product.id}"
            
            # Get the price
            price = lcw_product.price or Decimal('0.00')
            if lcw_product.discount_ratio and lcw_product.discount_ratio > 0:
                # Apply discount if available
                discount = Decimal(lcw_product.discount_ratio) / Decimal('100')
                price = price * (Decimal('1.00') - discount)
            
            # Get images
            images = []
            if lcw_product.images:
                try:
                    if isinstance(lcw_product.images, str):
                        images = json.loads(lcw_product.images)
                    elif isinstance(lcw_product.images, list):
                        images = lcw_product.images
                except json.JSONDecodeError:
                    pass
            
            # Create Trendyol product
            trendyol_product = TrendyolProduct.objects.create(
                title=lcw_product.title,
                description=lcw_product.description or lcw_product.title,
                barcode=barcode,
                product_main_id=lcw_product.product_code,
                brand_name="LCW",
                category_name=lcw_product.category or "",
                price=price,
                quantity=lcw_product.get_total_stock() if hasattr(lcw_product, 'get_total_stock') else 0,
                image_url=images[0] if images else "",
                additional_images=images[1:] if len(images) > 1 else [],
                lcwaikiki_product=lcw_product,
                batch_status='pending',
                status_message="Created from LCWaikiki product"
            )
        else:
            # Update existing Trendyol product with latest LCWaikiki data
            price = lcw_product.price or Decimal('0.00')
            if lcw_product.discount_ratio and lcw_product.discount_ratio > 0:
                discount = Decimal(lcw_product.discount_ratio) / Decimal('100')
                price = price * (Decimal('1.00') - discount)
            
            trendyol_product.title = lcw_product.title
            trendyol_product.description = lcw_product.description or lcw_product.title
            trendyol_product.price = price
            trendyol_product.quantity = lcw_product.get_total_stock() if hasattr(lcw_product, 'get_total_stock') else 0
            
            # Update images if available
            if lcw_product.images:
                try:
                    if isinstance(lcw_product.images, str):
                        images = json.loads(lcw_product.images)
                    elif isinstance(lcw_product.images, list):
                        images = lcw_product.images
                        
                    if images:
                        trendyol_product.image_url = images[0]
                        trendyol_product.additional_images = images[1:] if len(images) > 1 else []
                except json.JSONDecodeError:
                    pass
            
            trendyol_product.save()
        
        return trendyol_product
    except Exception as e:
        logger.error(f"Error converting LCWaikiki product to Trendyol product: {str(e)}")
        return None