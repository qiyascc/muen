import logging
import json
import time
import re
import requests
import base64
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union

from django.utils import timezone

from .models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct

logger = logging.getLogger(__name__)


class TrendyolApi:
  """Custom Trendyol API client implementation"""

  def __init__(self,
               api_key,
               api_secret,
               supplier_id,
               api_url='https://api.trendyol.com/sapigw',
               user_agent=None):
    self.api_key = api_key
    self.api_secret = api_secret
    self.supplier_id = supplier_id
    
    # Ensure consistent URL format
    if api_url.endswith('/'):
        api_url = api_url[:-1]
    self.api_url = api_url
    
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
        
    # Remove any duplicate /integration prefix from the endpoint
    if endpoint.startswith('/integration') and 'integration' in self.api_url:
        endpoint = endpoint.replace('/integration', '', 1)
    
    # Build the URL with proper formatting
    url = f"{self.api_url}{endpoint}"
    
    # Additional safeguard against duplicate integration paths
    url = url.replace('/integration/integration/', '/integration/')

    # Format the auth string and encode as Base64 for Basic Authentication
    auth_string = f"{self.api_key}:{self.api_secret}"
    auth_encoded = base64.b64encode(auth_string.encode()).decode()

    headers = {
        'Authorization': f"Basic {auth_encoded}",
        'Content-Type': 'application/json',
        'User-Agent': self.user_agent,
    }

    logger.info(f"Making {method} request to {url}")
    if data:
      logger.info(f"Request data: {json.dumps(data)}")

    try:
      # Enhanced debugging for product creation
      if endpoint.endswith('/products') and method == 'POST':
        # Check for required fields in each product
        if data and 'items' in data and isinstance(data['items'], list):
          for i, item in enumerate(data['items']):
            # Log each product's data
            logger.info(f"Product {i+1} data: {json.dumps(item)}")

            # Check for critical fields
            required_fields = [
                'barcode', 'title', 'productMainId', 'brandId', 'categoryId',
                'listPrice', 'salePrice', 'vatRate', 'stockCode'
            ]

            missing_fields = [
                field for field in required_fields
                if field not in item or item[field] is None
            ]
            if missing_fields:
              logger.error(
                  f"Product {i+1} missing required fields: {', '.join(missing_fields)}"
              )

            # Verify attributes structure
            if 'attributes' in item:
              if not isinstance(item['attributes'], list):
                logger.error(
                    f"Product {i+1} attributes must be a list, got {type(item['attributes'])}"
                )

              for attr in item['attributes']:
                if not isinstance(attr, dict):
                  logger.error(
                      f"Product {i+1} attribute must be an object, got {type(attr)}"
                  )
                  continue

                if 'attributeId' not in attr or 'attributeValueId' not in attr:
                  logger.error(
                      f"Product {i+1} attribute missing required fields: {attr}"
                  )

      # Log complete request details before sending
      logger.info(f"Making request: {method} {url}")
      logger.info(f"Request headers: {headers}")
      if params:
          logger.info(f"Request params: {params}")
      if data:
          logger.info(f"Request data: {json.dumps(data, default=str, indent=2)}")
      
      # Make the request
      response = requests.request(method=method,
                                  url=url,
                                  headers=headers,
                                  params=params,
                                  json=data,
                                  timeout=30)

      # Log response status and headers
      logger.info(f"Response status: {response.status_code}")
      logger.info(f"Response headers: {dict(response.headers)}")
      
      # Log the full response body for 400 errors to help debugging
      if response.status_code == 400:
          logger.error(f"400 BAD REQUEST ERROR")
          logger.error(f"Request URL: {url}")
          logger.error(f"Request method: {method}")
          logger.error(f"Request headers: {headers}")
          if data:
              logger.error(f"Request data: {json.dumps(data, default=str, indent=2)}")
          if params:
              logger.error(f"Request params: {params}")
          logger.error(f"Response headers: {dict(response.headers)}")
          logger.error(f"Response body: {response.text}")
      # For non-400 responses, just log the first part
      elif response.text:
          try:
              logger.info(f"Response text: {response.text[:1000]}...")  # Show first 1000 chars
          except Exception as e:
              logger.error(f"Error logging response text: {str(e)}")
      
      # Check if the request was successful
      response.raise_for_status()

      # Parse the response JSON
      try:
        result = response.json()
        logger.info(f"Response data: {json.dumps(result)}")
        return result
      except ValueError:
        # If the response is not JSON, return the response text
        logger.info(f"Response text: {response.text}")
        return {"response": response.text}

    except requests.exceptions.RequestException as e:
      logger.error(f"Error making request to Trendyol API: {str(e)}")
      error_details = {}
      if hasattr(e, 'response') and e.response:
        error_details['status_code'] = e.response.status_code
        error_details['response_text'] = e.response.text
        logger.error(f"Response status: {e.response.status_code}")
        logger.error(f"Response headers: {dict(e.response.headers)}")
        logger.error(f"Response content: {e.response.text}")
        
        # For 400 errors, log the request details to help diagnose the issue
        if e.response.status_code == 400:
            logger.error(f"Request URL: {url}")
            logger.error(f"Request method: {method}")
            logger.error(f"Request headers: {headers}")
            if data:
                logger.error(f"Request data: {json.dumps(data, default=str)}")
            if params:
                logger.error(f"Request params: {params}")

        # Try to parse error content if it's JSON
        try:
          error_json = e.response.json()
          error_details['error_json'] = error_json
          logger.error(f"Error JSON: {json.dumps(error_json, indent=2)}")

          if 'errors' in error_json:
            error_messages = []
            for error in error_json['errors']:
              error_msg = error.get('message', 'Unknown error')
              error_code = error.get('code', 'Unknown code')
              error_messages.append(f"{error_code}: {error_msg}")
              logger.error(f"API Error: Code={error_code}, Message={error_msg}")
            error_details['error_messages'] = error_messages
        except Exception as json_err:
          logger.error(f"Error parsing response JSON: {str(json_err)}")
          error_details['parse_error'] = str(json_err)

      # Return an error response object instead of None
      return {"error": True, "message": str(e), "details": error_details}


class BrandsAPI:
  """Trendyol Brands API"""

  def __init__(self, client):
    self.client = client
    
  def _get_brands_endpoint(self):
    """Get the brands endpoint for verification"""
    return '/product/brands'
    
  def get_brands(self, page=0, size=1000):
    """Get all brands from Trendyol"""
    endpoint = self._get_brands_endpoint()
    params = {'page': page, 'size': size}
    return self.client.make_request('GET', endpoint, params=params)

  def _get_brand_by_name_endpoint(self):
    """Get the brand by name endpoint for verification"""
    return '/product/brands/by-name'
    
  def get_brand_by_name(self, name):
    """Get brand by name"""
    endpoint = self._get_brand_by_name_endpoint()
    params = {'name': name}
    return self.client.make_request('GET', endpoint, params=params)


class CategoriesAPI:
  """Trendyol Categories API"""

  def __init__(self, client):
    self.client = client
    
  def _get_categories_endpoint(self):
    """Get the categories endpoint for verification"""
    return '/product-categories'
    
  def _get_category_attributes_endpoint(self, category_id):
    """Get the category attributes endpoint for verification"""
    return f'/product-categories/{category_id}/attributes'

  def get_categories(self):
    """Get all categories from Trendyol"""
    endpoint = self._get_categories_endpoint()
    return self.client.make_request('GET', endpoint)

  def get_category_attributes(self, category_id):
    """Get attributes for a specific category"""
    endpoint = self._get_category_attributes_endpoint(category_id)
    return self.client.make_request('GET', endpoint)


class ProductsAPI:
  """Trendyol Products API"""

  def __init__(self, client):
    self.client = client
    
  def _get_products_endpoint(self):
    """Get the base products endpoint for verification"""
    return f'/integration/product/sellers/{self.client.supplier_id}/products'
    
  def _get_batch_request_endpoint(self, batch_id):
    """Get the batch request endpoint for verification"""
    return f'/integration/product/sellers/{self.client.supplier_id}/products/batch-requests/{batch_id}'

  def create_products(self, products):
    """Create products on Trendyol"""
    endpoint = self._get_products_endpoint()
    return self.client.make_request('POST', endpoint, data={"items": products})

  def update_products(self, products):
    """Update existing products on Trendyol"""
    endpoint = self._get_products_endpoint()
    return self.client.make_request('PUT', endpoint, data={"items": products})

  def delete_products(self, barcodes):
    """Delete products from Trendyol"""
    endpoint = self._get_products_endpoint()
    items = [{"barcode": barcode} for barcode in barcodes]
    return self.client.make_request('DELETE', endpoint, data={"items": items})

  def get_batch_request_status(self, batch_id):
    """Get the status of a batch request"""
    endpoint = self._get_batch_request_endpoint(batch_id)
    return self.client.make_request('GET', endpoint)

  def get_products(self, barcode=None, approved=None, page=0, size=50):
    """Get products from Trendyol"""
    endpoint = self._get_products_endpoint()
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
    
  def _get_price_inventory_endpoint(self):
    """Get the price and inventory endpoint for verification"""
    return f'/integration/inventory/sellers/{self.client.supplier_id}/products/price-and-inventory'

  def update_price_and_inventory(self, items):
    """
        Update price and inventory for products
        
        Args:
            items: List of dictionaries with barcode, quantity, salePrice, and listPrice
                  Example: [{"barcode": "123456", "quantity": 10, "salePrice": 100.0, "listPrice": 120.0}]
        
        Returns:
            Dictionary with batchRequestId if successful
        """
    endpoint = self._get_price_inventory_endpoint()
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
        supplier_id=config.supplier_id or config.
        seller_id,  # Use supplier_id if set, otherwise fall back to seller_id
        api_url=config.base_url,
        user_agent=user_agent)

    return client
  except Exception as e:
    logger.error(f"Error creating Trendyol API client: {str(e)}")
    return None


def fetch_brands() -> List[Dict[str, Any]]:
  """
    Fetch all brands from Trendyol and update the local database.
    Returns a list of brand dictionaries.
    
    If the API connection fails, it will check the database for existing brands.
    """
  client = get_api_client()
  if not client:
    return []

  try:
    # Fetch brands from Trendyol
    response = client.brands.get_brands()

    if not response or 'brands' not in response:
      logger.error("Failed to fetch brands from Trendyol API")
      logger.warning("Using cached brands from database instead")
      
      # Get existing brands from database
      cached_brands = list(TrendyolBrand.objects.filter(is_active=True).values('brand_id', 'name'))
      if cached_brands:
        logger.info(f"Found {len(cached_brands)} brands in database cache")
        # Convert to expected format
        formatted_brands = [
          {'id': brand['brand_id'], 'name': brand['name']} 
          for brand in cached_brands
        ]
        return formatted_brands
      
      logger.error("No cached brands found in database")
      return []

    brands = response.get('brands', [])

    # Update or create brands in our database
    for brand in brands:
      brand_id = brand.get('id')
      name = brand.get('name')

      if brand_id and name:
        TrendyolBrand.objects.update_or_create(brand_id=brand_id,
                                               defaults={
                                                   'name': name,
                                                   'is_active': True
                                               })

    return brands
  except Exception as e:
    logger.error(f"Error fetching brands from Trendyol: {str(e)}")
    
    # Get existing brands from database in case of error
    logger.warning("Using cached brands from database instead")
    cached_brands = list(TrendyolBrand.objects.filter(is_active=True).values('brand_id', 'name'))
    if cached_brands:
      logger.info(f"Found {len(cached_brands)} brands in database cache")
      # Convert to expected format
      formatted_brands = [
        {'id': brand['brand_id'], 'name': brand['name']} 
        for brand in cached_brands
      ]
      return formatted_brands
    
    return []


def fetch_categories() -> List[Dict[str, Any]]:
  """
    Fetch all categories from Trendyol and update the local database.
    Returns a list of category dictionaries.
    
    If the API connection fails, it will check the database for existing categories.
    """
  client = get_api_client()
  if not client:
    return []

  try:
    # Fetch categories from Trendyol
    response = client.categories.get_categories()

    if not response or 'categories' not in response:
      logger.error("Failed to fetch categories from Trendyol API")
      logger.warning("Using cached categories from database instead")
      
      # Get existing categories from database
      cached_categories = list(TrendyolCategory.objects.filter(is_active=True).values('category_id', 'name', 'parent_id', 'path'))
      if cached_categories:
        logger.info(f"Found {len(cached_categories)} categories in database cache")
        # Convert to expected format
        formatted_categories = [
          {'id': cat['category_id'], 'name': cat['name'], 'parentId': cat['parent_id']} 
          for cat in cached_categories
        ]
        return formatted_categories
      
      logger.error("No cached categories found in database")
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

        TrendyolCategory.objects.update_or_create(category_id=category_id,
                                                  defaults={
                                                      'name': name,
                                                      'parent_id': parent_id,
                                                      'path': path,
                                                      'is_active': True
                                                  })

    return categories
  except Exception as e:
    logger.error(f"Error fetching categories from Trendyol: {str(e)}")
    
    # Get existing categories from database in case of error
    logger.warning("Using cached categories from database instead")
    cached_categories = list(TrendyolCategory.objects.filter(is_active=True).values('category_id', 'name', 'parent_id', 'path'))
    if cached_categories:
      logger.info(f"Found {len(cached_categories)} categories in database cache")
      # Convert to expected format
      formatted_categories = [
        {'id': cat['category_id'], 'name': cat['name'], 'parentId': cat['parent_id']} 
        for cat in cached_categories
      ]
      return formatted_categories
    
    return []


class TrendyolCategoryFinder:
  """
    Enhanced category finder with better search capabilities.
    This class handles finding the appropriate product category from Trendyol API
    and manages attribute mapping.
    """

  def __init__(self, api_client=None):
    self.api_client = api_client or get_api_client()
    self._categories_cache = None
    self._attributes_cache = {}

  @property
  def categories(self):
    """Get or fetch categories with caching"""
    if self._categories_cache is None:
      self._categories_cache = self._fetch_all_categories()
    return self._categories_cache

  def _fetch_all_categories(self):
    """Fetch the complete category tree from Trendyol API"""
    if not self.api_client:
      logger.error("No API client available")
      return []

    try:
      # First check database for cached categories
      all_categories = list(
          TrendyolCategory.objects.filter(is_active=True).values(
              'category_id', 'name', 'parent_id'))
      if all_categories:
        logger.info(
            f"Found {len(all_categories)} categories in database cache")
        return self._transform_db_categories(all_categories)

      # If not in database, fetch from API
      logger.info("Fetching categories from Trendyol API")
      response = self.api_client.categories.get_categories()
      if not response or 'categories' not in response:
        logger.error("Failed to fetch categories from API")
        return []

      # Cache categories in the database for future use
      self._cache_categories_in_db(response.get('categories', []))

      return response.get('categories', [])
    except Exception as e:
      logger.error(f"Error fetching categories: {str(e)}")
      return []

  def _transform_db_categories(self, db_categories):
    """Transform flat DB categories into a tree structure"""
    # This is a simplified transformation - in a real implementation
    # you'd construct a full tree structure
    categories = []
    id_to_category = {}

    # First pass: create category objects
    for cat in db_categories:
      category = {
          'id': cat['category_id'],
          'name': cat['name'],
          'parentId': cat['parent_id'],
          'subCategories': []
      }
      id_to_category[cat['category_id']] = category

      # Top-level categories have no parent
      if not cat['parent_id']:
        categories.append(category)

    # Second pass: build hierarchy
    for category_id, category in id_to_category.items():
      parent_id = category['parentId']
      if parent_id and parent_id in id_to_category:
        id_to_category[parent_id]['subCategories'].append(category)

    return categories

  def _cache_categories_in_db(self, categories, parent_id=None, path=''):
    """Cache categories in the database"""
    for category in categories:
      cat_id = category.get('id')
      name = category.get('name', '')

      if not cat_id or not name:
        continue

      # Update or create category
      try:
        new_path = f"{path} > {name}" if path else name
        TrendyolCategory.objects.update_or_create(category_id=cat_id,
                                                  defaults={
                                                      'name': name,
                                                      'parent_id': parent_id,
                                                      'path': new_path,
                                                      'is_active': True
                                                  })

        # Process subcategories
        subcategories = category.get('subCategories', [])
        if subcategories:
          logger.info(
              f"Processing {len(subcategories)} subcategories for {name} (ID: {cat_id})"
          )
          self._cache_categories_in_db(subcategories,
                                       parent_id=cat_id,
                                       path=new_path)
      except Exception as e:
        logger.error(f"Error caching category {name} (ID: {cat_id}): {str(e)}")

  def get_category_attributes(self, category_id):
    """Get attributes for a specific category with caching"""
    if not self.api_client or not category_id:
      return []

    if category_id in self._attributes_cache:
      return self._attributes_cache[category_id]

    try:
      response = self.api_client.categories.get_category_attributes(
          category_id)

      if not response or 'categoryAttributes' not in response:
        logger.error(f"Failed to fetch attributes for category {category_id}")
        return []

      attributes = response.get('categoryAttributes', [])
      self._attributes_cache[category_id] = attributes
      return attributes
    except Exception as e:
      logger.error(f"Error fetching category attributes: {str(e)}")
      return []

  def find_category_id(self, product):
    """Find the most appropriate category ID for a product"""
    # Log product information for debugging
    product_title = product.title if product.title else ""
    product_category = product.category_name if product.category_name else ""
    logger.info(
        f"Finding category for product: '{product_title}' (Category: '{product_category}')"
    )

    # Strategy 1: Use existing category ID if available
    if product.category_id:
      try:
        # Verify the category exists
        TrendyolCategory.objects.get(category_id=product.category_id)
        logger.info(f"Using existing category ID: {product.category_id}")
        return product.category_id
      except TrendyolCategory.DoesNotExist:
        logger.warning(
            f"Category ID {product.category_id} does not exist in database")
        pass

    # Strategy 2: Search by category name from database
    if product.category_name:
      try:
        # Try exact match first
        category = TrendyolCategory.objects.filter(
            name__iexact=product.category_name, is_active=True).first()

        if category:
          logger.info(
              f"Found exact category match in DB: {category.name} (ID: {category.category_id})"
          )
          return category.category_id

        # Try partial match
        category = TrendyolCategory.objects.filter(
            name__icontains=product.category_name, is_active=True).first()

        if category:
          logger.info(
              f"Found partial category match in DB: {category.name} (ID: {category.category_id})"
          )
          return category.category_id

      except Exception as e:
        logger.error(f"Error finding category by name in DB: {str(e)}")

    # Strategy 3: If product has LCWaikiki category, use it
    lcw_category = None
    if product.lcwaikiki_product and product.lcwaikiki_product.category:
      lcw_category = product.lcwaikiki_product.category

      try:
        # Try to find similar category in DB
        category = TrendyolCategory.objects.filter(
            name__icontains=lcw_category, is_active=True).first()

        if category:
          logger.info(
              f"Found category match from LCWaikiki category in DB: {category.name} (ID: {category.category_id})"
          )
          return category.category_id
      except Exception as e:
        logger.error(
            f"Error finding category from LCWaikiki category in DB: {str(e)}")

    # Strategy 4: Search API categories with advanced matching
    search_term = product.category_name or lcw_category
    if search_term:
      category_id = self._find_category_in_api(search_term)
      if category_id:
        logger.info(f"Found category match from API: ID {category_id}")
        return category_id

    # Strategy 5: Use default categories based on keywords in product title/category
    default_categories = {
        'giyim': 522,  # Giyim (Clothing)
        'erkek': 2356,  # Erkek Giyim (Men's Clothing)
        'men': 2356,  # Erkek Giyim (Men's Clothing) - English
        "men's": 2356,  # Erkek Giyim (Men's Clothing) - English
        'kadin': 41,  # Kadın Giyim (Women's Clothing)
        'kadın': 41,  # Kadın Giyim (Women's Clothing)
        'women': 41,  # Kadın Giyim (Women's Clothing) - English
        "women's": 41,  # Kadın Giyim (Women's Clothing) - English
        'çocuk': 674,  # Çocuk Gereçleri (Children's Items)
        'cocuk': 674,  # Çocuk Gereçleri (Children's Items)
        'child': 674,  # Çocuk Gereçleri (Children's Items) - English
        'children': 674,  # Çocuk Gereçleri (Children's Items) - English
        'bebek': 2164,  # Bebek Hediyelik (Baby Items)
        'baby': 2164,  # Bebek Hediyelik (Baby Items) - English
        'ayakkabi': 403,  # Ayakkabı (Shoes)
        'ayakkabı': 403,  # Ayakkabı (Shoes)
        'shoe': 403,  # Ayakkabı (Shoes) - English
        'shoes': 403,  # Ayakkabı (Shoes) - English
        'aksesuar': 368,  # Aksesuar (Accessories)
        'accessory': 368,  # Aksesuar (Accessories) - English
        'accessories': 368,  # Aksesuar (Accessories) - English
        'tisort': 384,  # T-shirt
        'tişört': 384,  # T-shirt
        't-shirt': 384,  # T-shirt - With dash
        'tshirt': 384,  # T-shirt - Without dash
        't shirt': 384,  # T-shirt - With space
        'pantolon': 383,  # Pants
        'pant': 383,  # Pants - English
        'pants': 383,  # Pants - English
        'jean': 383,  # Jeans - English
        'jeans': 383,  # Jeans - English
        'gömlek': 385,  # Shirt
        'gomlek': 385,  # Shirt
        'shirt': 385,  # Shirt - English
        'elbise': 1032,  # Dress
        'dress': 1032,  # Dress - English
        'bluz': 1027,  # Blouse
        'blouse': 1027  # Blouse - English
    }

    # Clean search text - replace punctuation with spaces to improve matching
    import re

    search_text = ' '.join(
        filter(None, [
            product.title and product.title.lower() or '',
            product.category_name and product.category_name.lower() or '',
            lcw_category and lcw_category.lower() or ''
        ]))

    # Replace punctuation with spaces to improve matching
    search_text = re.sub(r'[^\w\s]', ' ', search_text)
    # Normalize spaces
    search_text = ' ' + re.sub(r'\s+', ' ', search_text) + ' '

    logger.info(f"Search text for category matching: '{search_text}'")

    # Special handling for t-shirt - add extra variants
    if 't-shirt' in search_text or 'tshirt' in search_text or 't shirt' in search_text:
      search_text += ' tshirt t-shirt t shirt '
      logger.info(
          f"Enhanced search text with t-shirt variants: '{search_text}'")

    # Special handling for men's/women's - add extra variants
    if "men's" in search_text or 'mens' in search_text or ' men ' in search_text:
      search_text += ' men mens '
      logger.info(f"Enhanced search text with men's variants: '{search_text}'")

    if "women's" in search_text or 'womens' in search_text or ' women ' in search_text:
      search_text += ' women womens '
      logger.info(
          f"Enhanced search text with women's variants: '{search_text}'")

    logger.debug(f"Search text for category matching: '{search_text}'")

    # First, try to find specific item types like t-shirt, pants, etc.
    specific_item_types = [('tshirt', 't-shirt', 't shirt', 'tisort',
                            'tişört'),
                           ('pant', 'pants', 'jean', 'jeans', 'pantolon'),
                           ('shirt', 'gömlek', 'gomlek'), ('dress', 'elbise'),
                           ('blouse', 'bluz')]

    for item_types in specific_item_types:
      for item_type in item_types:
        pattern = f' {item_type} '
        if pattern in search_text:
          # Get the first keyword in the tuple for mapping
          category_id = default_categories.get(item_types[0])
          if category_id:
            try:
              category = TrendyolCategory.objects.get(category_id=category_id)
              logger.info(
                  f"Using specific category based on item type '{item_type}': {category.name} (ID: {category_id})"
              )
              return category_id
            except TrendyolCategory.DoesNotExist:
              continue

    # Then try to find gender/age groups
    audience_types = [('men', "men's", 'erkek'),
                      ('women', "women's", 'kadin', 'kadın'),
                      ('child', 'children', 'çocuk', 'cocuk'),
                      ('baby', 'bebek')]

    for audience in audience_types:
      for audience_type in audience:
        pattern = f' {audience_type} '
        if pattern in search_text:
          # Get the first keyword in the tuple for mapping
          category_id = default_categories.get(audience[0])
          if category_id:
            try:
              category = TrendyolCategory.objects.get(category_id=category_id)
              logger.info(
                  f"Using demographic category based on audience type '{audience_type}': {category.name} (ID: {category_id})"
              )
              return category_id
            except TrendyolCategory.DoesNotExist:
              continue

    # Finally try generic fallbacks for any keyword
    for keyword, category_id in default_categories.items():
      pattern = f' {keyword} '
      if pattern in search_text:
        try:
          category = TrendyolCategory.objects.get(category_id=category_id)
          logger.info(
              f"Using default category based on keyword '{keyword}': {category.name} (ID: {category_id})"
          )
          return category_id
        except TrendyolCategory.DoesNotExist:
          continue

    # Final fallback: Use "Giyim" (Clothing) category as default
    try:
      giyim_category = TrendyolCategory.objects.get(category_id=522)  # Giyim
      logger.info(f"Using fallback category: {giyim_category.name} (ID: 522)")
      return 522
    except TrendyolCategory.DoesNotExist:
      # If even the default category is not found, try any available top-level category
      top_category = TrendyolCategory.objects.filter(
          parent_id__isnull=True).first()
      if top_category:
        logger.info(
            f"Using any available top-level category: {top_category.name} (ID: {top_category.category_id})"
        )
        return top_category.category_id

    # No matching category found
    logger.error(f"No matching category found for product: {product.title}")
    return None

  def _find_category_in_api(self, search_term):
    """Find a category by searching the API data with multiple strategies"""
    if not search_term or not self.categories:
      return None

    search_term = search_term.lower()

    # Strategy 1: Look for exact match
    for category in self.categories:
      # Check top level
      if category.get('name', '').lower() == search_term:
        return category.get('id')

      # Check subcategories recursively
      result = self._search_subcategories_exact(
          category.get('subCategories', []), search_term)
      if result:
        return result

    # Strategy 2: Look for contains match
    for category in self.categories:
      # Check if category name contains search term
      cat_name = category.get('name', '').lower()
      if search_term in cat_name or cat_name in search_term:
        return category.get('id')

      # Check subcategories recursively
      result = self._search_subcategories_contains(
          category.get('subCategories', []), search_term)
      if result:
        return result

    # Strategy 3: Find the best partial match
    best_match = None
    best_match_score = 0.5  # Threshold

    for category in self.categories:
      score = self._calculate_similarity(category.get('name', ''), search_term)
      if score > best_match_score:
        best_match = category
        best_match_score = score

      # Check subcategories
      subcategory_match, subcategory_score = self._search_subcategories_partial(
          category.get('subCategories', []), search_term, best_match_score)

      if subcategory_match and subcategory_score > best_match_score:
        best_match = subcategory_match
        best_match_score = subcategory_score

    if best_match:
      return best_match.get('id')

    # No match found
    return None

  def _search_subcategories_exact(self, subcategories, search_term):
    """Recursively search subcategories for exact name match"""
    for subcategory in subcategories:
      if subcategory.get('name', '').lower() == search_term:
        return subcategory.get('id')

      result = self._search_subcategories_exact(
          subcategory.get('subCategories', []), search_term)
      if result:
        return result

    return None

  def _search_subcategories_contains(self, subcategories, search_term):
    """Recursively search subcategories for containing match"""
    for subcategory in subcategories:
      subcat_name = subcategory.get('name', '').lower()
      if search_term in subcat_name or subcat_name in search_term:
        return subcategory.get('id')

      result = self._search_subcategories_contains(
          subcategory.get('subCategories', []), search_term)
      if result:
        return result

    return None

  def _search_subcategories_partial(self, subcategories, search_term,
                                    threshold):
    """Recursively search subcategories for partial match using similarity score"""
    best_match = None
    best_match_score = threshold

    for subcategory in subcategories:
      score = self._calculate_similarity(subcategory.get('name', ''),
                                         search_term)
      if score > best_match_score:
        best_match = subcategory
        best_match_score = score

      # Search deeper
      deeper_match, deeper_score = self._search_subcategories_partial(
          subcategory.get('subCategories', []), search_term, best_match_score)

      if deeper_match and deeper_score > best_match_score:
        best_match = deeper_match
        best_match_score = deeper_score

    return best_match, best_match_score

  def _calculate_similarity(self, str1: str, str2: str) -> float:
    """
        Calculate similarity between two strings.
        Uses a combination of exact match, contains, and word overlap metrics.
        """
    str1 = str1.lower()
    str2 = str2.lower()

    # Perfect match
    if str1 == str2:
      return 1.0

    # Contains match
    if str1 in str2:
      return 0.9
    if str2 in str1:
      return 0.8

    # Word overlap
    words1 = set(str1.split())
    words2 = set(str2.split())
    common_words = words1.intersection(words2)

    if common_words:
      return 0.5 + (len(common_words) / max(len(words1), len(words2)) * 0.4)

    return 0.0

  def get_required_attributes(self, category_id):
    """
        Get all required attributes for a category with proper filtering.
        Includes attributes that are required or part of variants like size and color.
        """
    if not category_id:
      return []

    attributes = self.get_category_attributes(category_id)
    if not attributes:
      # Try to fetch the attributes directly if they're not in the cache
      try:
        response = self.api_client.categories.get_category_attributes(
            category_id)
        if response and 'categoryAttributes' in response:
          attributes = response.get('categoryAttributes', [])
          logger.info(
              f"Successfully fetched {len(attributes)} attributes for category {category_id}"
          )
          # Update cache
          self._attributes_cache[category_id] = attributes
        else:
          logger.warning(f"No attributes found for category {category_id}")
          return []
      except Exception as e:
        logger.error(
            f"Error fetching attributes for category {category_id}: {str(e)}")
        return []

    # Log the attribute information for debugging
    logger.info(
        f"Processing {len(attributes)} attributes for category {category_id}")

    # Default required attributes for clothing products if none found
    default_attributes = [
        {
            "attribute": {
                "id": 338,
                "name": "Beden"
            },  # Size
            "required":
            True,
            "varianter":
            True,
            "attributeValues": [{
                "id": 4294,
                "name": "XS"
            }, {
                "id": 4295,
                "name": "S"
            }, {
                "id": 4296,
                "name": "M"
            }, {
                "id": 4297,
                "name": "L"
            }, {
                "id": 4298,
                "name": "XL"
            }]
        },
        {
            "attribute": {
                "id": 347,
                "name": "Renk"
            },  # Color
            "required":
            True,
            "varianter":
            True,
            "attributeValues": [{
                "id": 4525,
                "name": "Beyaz"
            }, {
                "id": 4531,
                "name": "Siyah"
            }, {
                "id": 4532,
                "name": "Kırmızı"
            }, {
                "id": 4538,
                "name": "Mavi"
            }]
        }
    ]

    required_attributes = []
    for attr in attributes:
      attribute_info = attr.get('attribute', {})
      attribute_name = attribute_info.get('name', '').lower()
      is_required = attr.get('required', False)
      is_variant = attribute_name in ('beden', 'renk')  # Size, Color
      is_varianter = attr.get('varianter', False)
      allow_custom = attr.get('allowCustom', False)

      # Add attribute if it's required, a variant, or has values
      if is_required or is_variant or is_varianter or attr.get(
          'attributeValues'):
        required_attributes.append(attr)
        logger.debug(
            f"Added attribute: {attribute_name} (Required: {is_required}, Variant: {is_variant})"
        )

    # If no attributes found, use default attributes
    if not required_attributes and category_id in (522, 2356, 41, 674, 383,
                                                   384, 385, 1032):
      logger.warning(
          f"No attributes found for category {category_id}, using defaults")
      return default_attributes

    return required_attributes


def find_best_category_match(product: TrendyolProduct) -> Optional[int]:
  """
    Find the best matching category for a product.
    Returns the category ID if found, None otherwise.
    
    Enhanced implementation that uses the TrendyolCategoryFinder class.
    """
  finder = TrendyolCategoryFinder(get_api_client())
  return finder.find_category_id(product)


def find_best_brand_match(product: TrendyolProduct) -> Optional[int]:
  """
    Find the best matching brand for a product.
    Returns the brand ID if found, None otherwise.
    """
  logger.info(
      f"Finding brand for product: {product.title} (Brand name: {product.brand_name})"
  )

  # If we already have a brand ID, use it
  if product.brand_id:
    # Verify the brand exists
    try:
      TrendyolBrand.objects.get(brand_id=product.brand_id)
      logger.info(f"Using existing brand ID: {product.brand_id}")
      return product.brand_id
    except TrendyolBrand.DoesNotExist:
      logger.warning(f"Brand ID {product.brand_id} does not exist in database")
      pass

  # Try to find by brand name
  if product.brand_name:
    try:
      # Try exact match first
      brand = TrendyolBrand.objects.filter(name__iexact=product.brand_name,
                                           is_active=True).first()

      if brand:
        logger.info(
            f"Found exact brand match: {brand.name} (ID: {brand.brand_id})")
        return brand.brand_id

      # Try partial match
      brand = TrendyolBrand.objects.filter(name__icontains=product.brand_name,
                                           is_active=True).first()

      if brand:
        logger.info(
            f"Found partial brand match: {brand.name} (ID: {brand.brand_id})")
        return brand.brand_id

      # Try with brand name variations
      brand_variations = []

      # Handle LC WAIKIKI / LCW variations
      if 'lcw' in product.brand_name.lower(
      ) or 'waikiki' in product.brand_name.lower():
        brand_variations.extend(['LC WAIKIKI', 'LCW'])

      for variation in brand_variations:
        brand = TrendyolBrand.objects.filter(name__iexact=variation,
                                             is_active=True).first()

        if brand:
          logger.info(
              f"Found brand match using variation '{variation}': {brand.name} (ID: {brand.brand_id})"
          )
          return brand.brand_id

    except Exception as e:
      logger.error(f"Error finding brand by name: {str(e)}")

  # If we have a related LCWaikiki product, assume it's LCWaikiki brand
  if product.lcwaikiki_product:
    try:
      # First try LC WAIKIKI
      brand = TrendyolBrand.objects.filter(name__icontains="WAIKIKI",
                                           is_active=True).first()

      if brand:
        logger.info(
            f"Found LCW brand using related product: {brand.name} (ID: {brand.brand_id})"
        )
        return brand.brand_id

      # Then try LCW
      brand = TrendyolBrand.objects.filter(name__iexact="LCW",
                                           is_active=True).first()

      if brand:
        logger.info(
            f"Found LCW brand using related product: {brand.name} (ID: {brand.brand_id})"
        )
        return brand.brand_id

    except Exception as e:
      logger.error(f"Error finding LCW brand: {str(e)}")

  # If all else fails, try to find any brand and use it as fallback
  try:
    fallback_brand = TrendyolBrand.objects.filter(is_active=True).first()
    if fallback_brand:
      logger.warning(
          f"Using fallback brand: {fallback_brand.name} (ID: {fallback_brand.brand_id})"
      )
      return fallback_brand.brand_id
  except Exception as e:
    logger.error(f"Error finding fallback brand: {str(e)}")

  # No brand found
  logger.error(f"No matching brand found for product: {product.title}")
  return None


def get_required_attributes_for_category(
    category_id: int) -> List[Dict[str, Any]]:
  """
    Get required attributes for a specific category.
    Returns a list of attribute dictionaries.
    
    This is a wrapper for the enhanced TrendyolCategoryFinder's method.
    """
  finder = TrendyolCategoryFinder(get_api_client())
  return finder.get_required_attributes(category_id)


def prepare_product_data(product: TrendyolProduct) -> Dict[str, Any]:
  """
    Prepare product data for Trendyol API.
    Returns a dictionary with the product data.
    """
  # Validate required fields
  if not product.title or not product.barcode or not product.price:
    logger.error(f"Product {product.id} is missing required fields")
    raise ValueError(
        "Product is missing required fields: title, barcode, or price")

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

  # Prepare attributes - Using correct numeric IDs and values
  attributes = []
  if product.attributes:
    if isinstance(product.attributes, dict):
      for key, value in product.attributes.items():
        try:
          # Try to convert attributeId to integer (Trendyol expects integer IDs)
          attr_id = int(key) if key.isdigit() else key
          # Try to convert attributeValueId to integer if possible
          attr_value_id = int(value) if isinstance(value, str) and value.isdigit() else value
          attributes.append({"attributeId": attr_id, "attributeValueId": attr_value_id})
        except (ValueError, TypeError):
          logger.warning(f"Could not convert attribute ID/value to integer: {key}={value}")
    elif isinstance(product.attributes, str):
      try:
        attrs = json.loads(product.attributes)
        if isinstance(attrs, dict):
          for key, value in attrs.items():
            try:
              # Try to convert attributeId to integer (Trendyol expects integer IDs)
              attr_id = int(key) if key.isdigit() else key
              # Try to convert attributeValueId to integer if possible
              attr_value_id = int(value) if isinstance(value, str) and value.isdigit() else value
              attributes.append({"attributeId": attr_id, "attributeValueId": attr_value_id})
            except (ValueError, TypeError):
              logger.warning(f"Could not convert attribute ID/value to integer: {key}={value}")
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
          # Make sure we're using integer IDs
          attr_id_int = int(attr_id) if isinstance(attr_id, str) and attr_id.isdigit() else attr_id
          value_id_int = int(value_id) if isinstance(value_id, str) and value_id.isdigit() else value_id
          attributes.append({
              "attributeId": attr_id_int,
              "attributeValueId": value_id_int
          })

  # Prepare product data
  product_data = {
      "barcode": product.barcode,
      "title": product.title,
      "productMainId": product.product_main_id or product.barcode,
      "brandId": brand_id,
      "categoryId": category_id,
      "stockCode": product.stock_code or product.barcode,
      "quantity": product.quantity or 10,  # Default to 10 if not specified
      # Removed stockUnitType per request
      # Removed dimensionalWeight per request
      "description": product.description
      or product.title,  # Use title as fallback description
      "currencyType": product.currency_type
      or "TRY",  # Default to Turkish Lira
      "listPrice": float(product.price or 0),
      "salePrice": float(product.price or 0),
      "vatRate": 10,  # Fix to 10% VAT as requested
      "cargoCompanyId": 17,  # Fixed cargo company ID as requested
      # Removed shipmentAddressId per request
      # Removed deliveryDuration per request
      # Removed pimCategoryId per request
      "gender": {
          "id": 1  # Default to Unisex
      },
      "attributes": attributes,
  }

  # Only add images if we have any
  if image_urls:
    product_data["images"] = [{"url": url} for url in image_urls if url]

  # Add color attribute if it exists in the attributes
  color_from_attributes = None
  if product.attributes and isinstance(product.attributes,
                                       dict) and 'color' in product.attributes:
    color_from_attributes = product.attributes.get('color')

  if color_from_attributes and not any(
      attr.get("attributeName") == "Renk" for attr in attributes):
    product_data["color"] = color_from_attributes

  # Ensure all numeric values are proper floats/ints
  for key in [
      "quantity", "listPrice", "salePrice", "vatRate"
  ]:
    if key in product_data and product_data[key] is not None:
      try:
        if key in ["listPrice", "salePrice"]:
          product_data[key] = float(product_data[key])
        else:
          product_data[key] = int(product_data[key])
      except (ValueError, TypeError):
        # If conversion fails, use default values
        if key in ["listPrice", "salePrice"]:
          product_data[key] = 0.0
        else:
          product_data[key] = 0

  # Make sure brandId and categoryId are integers
  for key in ["brandId", "categoryId"]:
    if key in product_data and product_data[key] is not None:
      try:
        product_data[key] = int(product_data[key])
      except (ValueError, TypeError):
        logger.error(f"Invalid {key}: {product_data[key]}")
        raise ValueError(f"Invalid {key}: must be an integer")

  return product_data


def create_trendyol_product(product: TrendyolProduct) -> Optional[str]:
  """
    Create a product on Trendyol using the new API structure.
    Returns the batch ID if successful, None otherwise.
    
    This function includes comprehensive error handling with detailed
    error messages to make debugging easier. It validates required fields
    before submission and properly logs all operations.
    """
  client = get_api_client()
  if not client:
    error_message = "No active Trendyol API configuration found"
    logger.error(error_message)
    product.batch_status = 'failed'
    product.status_message = error_message
    product.save()
    return None

  try:
    # Prepare product data
    try:
      product_data = prepare_product_data(product)
    except ValueError as e:
      error_message = f"Error preparing product data: {str(e)}"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    # Validate that required fields are present
    required_fields = [
        'barcode', 'title', 'productMainId', 'brandId', 'categoryId',
        'quantity'
    ]
    missing_fields = [
        field for field in required_fields
        if field not in product_data or product_data[field] is None
    ]

    if missing_fields:
      error_message = f"Product data missing required fields: {', '.join(missing_fields)}"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    # Create the product on Trendyol
    logger.info(
        f"Submitting product '{product.title}' (ID: {product.id}) to Trendyol")
    logger.info(
        f"Product data: {json.dumps(product_data, default=str, indent=2)}")
    response = client.products.create_products([product_data])

    # Handle different response error scenarios
    if not response:
      error_message = "No response from Trendyol API"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    # Check if the response contains an error flag (from our enhanced error handling)
    if isinstance(response, dict) and response.get('error') is True:
      error_message = response.get('message', 'Unknown API error')
      error_details = response.get('details', '')

      # Log detailed error information
      logger.error(f"API error for product ID {product.id}: {error_message}")
      if error_details:
        logger.error(f"Error details: {error_details}")

      # Save detailed error information to the product
      full_error = f"{error_message}"
      if error_details:
        full_error += f" - {error_details}"

      product.batch_status = 'failed'
      product.status_message = full_error[:500]  # Truncate if too long
      product.save()
      return None

    # Check for errors in standard response format
    if isinstance(response,
                  dict) and 'errors' in response and response['errors']:
      errors = response['errors']
      if isinstance(errors, list):
        error_message = f"Failed to create product: {errors[0].get('message', 'Unknown error')}"
      else:
        error_message = f"Failed to create product: {errors}"

      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    if 'batchRequestId' not in response:
      error_message = "Failed to create product on Trendyol: No batch request ID returned"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    batch_id = response.get('batchRequestId')

    # Update product with batch ID and status
    logger.info(
        f"Product '{product.title}' (ID: {product.id}) submitted with batch ID: {batch_id}"
    )
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
      logger.error(
          f"Failed to check batch status for product {product.id} on Trendyol")
      product.batch_status = 'failed'
      product.status_message = "Failed to check batch status: No response from API"
      product.save()
      return 'failed'

    # Check if response is a dictionary or string
    if isinstance(response, dict):
        # Get batch status details
        status = response.get('status', 'failed')

        # Map Trendyol status to our status
        status_mapping = {
            'PROCESSING': 'processing',
            'DONE': 'completed',
            'FAILED': 'failed',
        }

        internal_status = status_mapping.get(status, 'failed')
    else:
        # If it's not a dictionary, handle it as a raw response (like string)
        logger.info(f"Received non-dictionary response: {response}")
        
        # Assume 'processing' status since we got a response but it's not in the expected format
        # This is likely during the initial processing phase
        internal_status = 'processing'

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
        products_response = client.products.get_product_by_barcode(
            product.barcode)
        if products_response and 'content' in products_response and products_response[
            'content']:
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
    logger.error(
        f"Error checking batch status for product {product.id} on Trendyol: {str(e)}"
    )
    product.batch_status = 'failed'
    product.status_message = f"Error checking batch status: {str(e)}"
    product.save()
    return 'failed'


def update_price_and_inventory(product: TrendyolProduct) -> Optional[str]:
  """
    Update only the price and inventory for an existing product on Trendyol.
    This uses the dedicated price and inventory update endpoint.
    
    This function includes comprehensive error handling with detailed
    error messages to make debugging easier. It properly validates
    required fields before submission and logs all operations.
    
    Returns:
        The batch request ID if successful, None otherwise.
    """
  client = get_api_client()
  if not client:
    error_message = "No active Trendyol API configuration found"
    logger.error(f"{error_message} for product ID {product.id}")
    product.batch_status = 'failed'
    product.status_message = error_message
    product.save()
    return None

  try:
    # Validate barcode and quantity
    if not product.barcode:
      error_message = "Missing barcode for price and inventory update"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    if product.quantity < 0:
      error_message = "Invalid quantity (negative) for price and inventory update"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    if product.price <= Decimal('0.00'):
      error_message = "Invalid price (zero or negative) for price and inventory update"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    # Prepare price and inventory data with proper list price
    # List price should always be equal or higher than sale price
    sale_price = float(product.price)
    list_price = max(float(product.price * Decimal('1.05')),
                     sale_price)  # 5% higher for list price, but never lower

    item_data = {
        "barcode": product.barcode,
        "quantity": product.quantity,
        "salePrice": sale_price,
        "listPrice": list_price
    }

    # Update price and inventory on Trendyol
    logger.info(
        f"Updating price and inventory for product '{product.title}' (ID: {product.id}) on Trendyol"
    )
    logger.info(
        f"Price: {sale_price}, List Price: {list_price}, Quantity: {product.quantity}"
    )
    response = client.inventory.update_price_and_inventory([item_data])

    # Handle different response error scenarios
    if not response:
      error_message = "No response from Trendyol API"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    # Check if the response contains an error flag (from our enhanced error handling)
    if isinstance(response, dict) and response.get('error') is True:
      error_message = response.get('message', 'Unknown API error')
      error_details = response.get('details', '')

      # Log detailed error information
      logger.error(f"API error for product ID {product.id}: {error_message}")
      if error_details:
        logger.error(f"Error details: {error_details}")

      # Save detailed error information to the product
      full_error = f"{error_message}"
      if error_details:
        full_error += f" - {error_details}"

      product.batch_status = 'failed'
      product.status_message = full_error[:500]  # Truncate if too long
      product.save()
      return None

    # Check for errors in standard response format
    if isinstance(response,
                  dict) and 'errors' in response and response['errors']:
      errors = response['errors']
      if isinstance(errors, list):
        error_message = f"Failed to update price and inventory: {errors[0].get('message', 'Unknown error')}"
      else:
        error_message = f"Failed to update price and inventory: {errors}"

      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    if 'batchRequestId' not in response:
      error_message = "Failed to update price and inventory: No batch request ID returned"
      logger.error(f"{error_message} for product ID {product.id}")
      product.batch_status = 'failed'
      product.status_message = error_message
      product.save()
      return None

    batch_id = response.get('batchRequestId')

    # Update product with batch ID and status
    logger.info(
        f"Price and inventory update submitted for product '{product.title}' (ID: {product.id}) with batch ID: {batch_id}"
    )
    product.batch_id = batch_id
    product.batch_status = 'processing'
    product.status_message = "Price and inventory update initiated"
    product.last_check_time = timezone.now()
    product.save()

    return batch_id
  except Exception as e:
    error_message = f"Error updating price and inventory: {str(e)}"
    logger.error(f"{error_message} for product ID {product.id}")
    product.batch_status = 'failed'
    product.status_message = error_message
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
            products_response = client.products.get_product_by_barcode(
                product.barcode)
            if products_response and 'content' in products_response and products_response[
                'content']:
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


def batch_process_products(products, process_func, batch_size=10, delay=0.5):
  """
    Process a batch of products using the provided function.
    
    Args:
        products: List of products to process
        process_func: Function to apply to each product
        batch_size: Number of products to process in one batch
        delay: Delay in seconds between processing each product
        
    Returns:
        Tuple of (success_count, error_count, batch_ids)
    """
  success_count = 0
  error_count = 0
  batch_ids = []

  total = len(products)
  logger.info(f"Processing {total} products in batches of {batch_size}")

  for i, product in enumerate(products):
    try:
      # Apply the processing function
      result = process_func(product)

      # Check the result
      if result:
        success_count += 1
        # If the function returns a batch ID, add it to the list
        if isinstance(result, str):
          batch_ids.append(result)
      else:
        error_count += 1

      # Log progress
      if (i + 1) % 5 == 0 or i == total - 1:
        logger.info(
            f"Processed {i + 1}/{total} products: {success_count} succeeded, {error_count} failed"
        )

      # Add delay to avoid overwhelming the API
      if delay > 0 and i < total - 1:
        time.sleep(delay)

      # Take a longer break after each batch to avoid rate limits
      if (i + 1) % batch_size == 0 and i < total - 1:
        logger.info(
            f"Batch complete. Taking a short break to avoid rate limits...")
        time.sleep(delay * 4)  # Longer pause between batches

    except Exception as e:
      logger.error(f"Error processing product: {str(e)}")
      error_count += 1

  return success_count, error_count, batch_ids


def lcwaikiki_to_trendyol_product(lcw_product) -> Optional[TrendyolProduct]:
  """
    Convert an LCWaikiki product to a Trendyol product.
    Returns the created or updated Trendyol product instance.
    
    This is an enhanced version with improved product code extraction and
    barcode generation to ensure uniqueness and Trendyol compatibility.
    It now also handles brand lookups and attribute mapping.
    """
  if not lcw_product:
    return None

  try:
    # Check if a Trendyol product already exists for this LCWaikiki product
    trendyol_product = TrendyolProduct.objects.filter(
        lcwaikiki_product=lcw_product).first()

    # Extract and format product code properly
    product_code = None
    if lcw_product.product_code:
      # Clean up product code - only allow alphanumeric characters
      product_code = re.sub(r'[^a-zA-Z0-9]', '', lcw_product.product_code)
      # Ensure it's not empty after cleaning
      if not product_code:
        product_code = None

    # Generate a unique barcode that meets Trendyol requirements
    # Trendyol requires unique barcode with alphanumeric chars
    barcode = None
    if product_code:
      barcode = f"LCW{product_code}"
    else:
      # If no product code, create a unique identifier based on ID and timestamp
      timestamp = int(time.time())
      barcode = f"LCW{lcw_product.id}{timestamp}"

    # Ensure barcode is alphanumeric and meets Trendyol requirements
    barcode = re.sub(r'[^a-zA-Z0-9]', '', barcode)
    # Cap length to avoid potential issues with very long barcodes
    barcode = barcode[:32]

    # Get the price with proper discount handling
    price = lcw_product.price or Decimal('0.00')
    if lcw_product.discount_ratio and lcw_product.discount_ratio > 0:
      # Apply discount if available
      discount = Decimal(lcw_product.discount_ratio) / Decimal('100')
      price = price * (Decimal('1.00') - discount)

    # Process images with better error handling
    images = []
    if lcw_product.images:
      try:
        if isinstance(lcw_product.images, str):
          # Try to parse JSON string
          images = json.loads(lcw_product.images)
        elif isinstance(lcw_product.images, list):
          images = lcw_product.images

        # Ensure all image URLs are strings and properly formatted
        images = [str(img) for img in images if img and 'http' in str(img)]

        # Fix image URLs that don't have proper protocol
        for i, img in enumerate(images):
          if img and not img.startswith(('http://', 'https://')):
            images[i] = f"https:{img}" if img.startswith(
                '//') else f"https://{img}"
      except json.JSONDecodeError:
        logger.warning(
            f"Failed to decode images JSON for product {lcw_product.id}")
      except Exception as e:
        logger.warning(
            f"Error processing images for product {lcw_product.id}: {str(e)}")

    # If no images found, use a default placeholder image
    if not images:
      images = [
          "https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20224/5841125/l_20224-w4bi51z8-ct5_a.jpg"
      ]
      logger.warning(
          f"No valid images found for product {lcw_product.id}, using placeholder"
      )

    # Get quantity with fallback
    quantity = 10  # Default to 10 for better Trendyol acceptance
    if hasattr(lcw_product, 'get_total_stock'):
      try:
        stock = lcw_product.get_total_stock()
        if stock and stock > 0:
          quantity = stock
      except Exception as e:
        logger.warning(
            f"Error getting total stock for product {lcw_product.id}: {str(e)}"
        )

    # Find the appropriate brand ID in the Trendyol system
    brand_id = None
    try:
      # Try to find the LCW brand in our database
      lcw_brand = TrendyolBrand.objects.filter(name__icontains="LCW",
                                               is_active=True).first()

      if lcw_brand:
        brand_id = lcw_brand.brand_id
        logger.info(f"Found brand: {lcw_brand.name} (ID: {brand_id})")
      else:
        # Try to fetch brands if none found
        logger.info(
            "No LCW brand found in database, fetching from Trendyol...")
        fetch_brands()

        # Try again after fetching
        lcw_brand = TrendyolBrand.objects.filter(name__icontains="LCW",
                                                 is_active=True).first()

        if lcw_brand:
          brand_id = lcw_brand.brand_id
          logger.info(
              f"Found brand after fetch: {lcw_brand.name} (ID: {brand_id})")
        else:
          # If still not found, use any available brand
          any_brand = TrendyolBrand.objects.filter(is_active=True).first()
          if any_brand:
            brand_id = any_brand.brand_id
            logger.warning(
                f"Using fallback brand: {any_brand.name} (ID: {brand_id})")
    except Exception as e:
      logger.error(
          f"Error finding brand for product {lcw_product.id}: {str(e)}")

    # Prepare basic attributes based on product data
    attributes = {}

    # Add color attribute if available
    if hasattr(lcw_product, 'color') and lcw_product.color:
      attributes["color"] = lcw_product.color

    # Add size attributes if available (placeholder for now)
    # We'll add a proper implementation for size mapping later

    # Find category information
    category_id = None
    if trendyol_product and trendyol_product.category_id:
      category_id = trendyol_product.category_id
    else:
      # Try to find a category based on the product's category name
      category_name = lcw_product.category or ""
      try:
        if category_name:
          # Try to find a matching category
          if "tişört" in category_name.lower(
          ) or "t-shirt" in category_name.lower():
            # Look for T-shirt category
            t_shirt_category = TrendyolCategory.objects.filter(
                name__icontains="Tişört", is_active=True).first()

            if t_shirt_category:
              category_id = t_shirt_category.category_id
              logger.info(
                  f"Found T-shirt category: {t_shirt_category.name} (ID: {category_id})"
              )
          else:
            # Generic search
            words = category_name.split()
            for word in words:
              if len(word) > 3:  # Skip short words
                matching_category = TrendyolCategory.objects.filter(
                    name__icontains=word, is_active=True).first()

                if matching_category:
                  category_id = matching_category.category_id
                  logger.info(
                      f"Found category for '{word}': {matching_category.name} (ID: {category_id})"
                  )
                  break
      except Exception as e:
        logger.error(
            f"Error finding category for product {lcw_product.id}: {str(e)}")

    # If category still not found, try to fetch categories
    if not category_id:
      try:
        logger.info("No category found, fetching from Trendyol...")
        fetch_categories()

        # Default to a standard clothing category if available
        default_category = TrendyolCategory.objects.filter(
            name__icontains="Giyim", is_active=True).first()

        if default_category:
          category_id = default_category.category_id
          logger.warning(
              f"Using default category: {default_category.name} (ID: {category_id})"
          )
      except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")

    if not trendyol_product:
      # Store color in attributes if it exists
      if hasattr(lcw_product, 'color') and lcw_product.color:
        if not attributes:
          attributes = {}
        attributes['color'] = lcw_product.color

      # Create a new Trendyol product with enhanced data
      trendyol_product = TrendyolProduct.objects.create(
          title=lcw_product.title or "LC Waikiki Product",
          description=lcw_product.description or lcw_product.title
          or "LC Waikiki Product Description",
          barcode=barcode,
          product_main_id=product_code or barcode,
          stock_code=product_code or barcode,
          brand_name="LCW",
          brand_id=brand_id,
          category_name=lcw_product.category or "Clothing",
          category_id=category_id,
          pim_category_id=category_id,  # Use same as category_id initially
          price=price or Decimal('100.00'),  # Fallback price if none provided
          quantity=quantity,
          image_url=images[0] if images else "",
          additional_images=images[1:] if len(images) > 1 else [],
          attributes=attributes,
          lcwaikiki_product=lcw_product,
          batch_status='pending',
          status_message="Created from LCWaikiki product",
          currency_type="TRY",  # Turkish Lira
          vat_rate=18  # Default VAT rate in Turkey
      )
      logger.info(
          f"Created new Trendyol product from LCW product {lcw_product.id} with barcode {barcode}"
      )
    else:
      # Update existing Trendyol product with latest LCWaikiki data
      trendyol_product.title = lcw_product.title or trendyol_product.title or "LC Waikiki Product"
      trendyol_product.description = lcw_product.description or lcw_product.title or trendyol_product.description or "LC Waikiki Product Description"
      trendyol_product.price = price or trendyol_product.price or Decimal(
          '100.00')
      trendyol_product.quantity = quantity
      trendyol_product.brand_id = brand_id or trendyol_product.brand_id
      trendyol_product.category_id = category_id or trendyol_product.category_id
      trendyol_product.pim_category_id = category_id or trendyol_product.pim_category_id

      # Update attributes and add color if it exists
      if hasattr(lcw_product, 'color') and lcw_product.color:
        if not attributes:
          attributes = {}
        attributes['color'] = lcw_product.color

      trendyol_product.attributes = attributes

      # Only update barcode if it's not already been used with Trendyol
      if not trendyol_product.trendyol_id and not trendyol_product.batch_status == 'completed':
        trendyol_product.barcode = barcode
        trendyol_product.product_main_id = product_code or barcode
        trendyol_product.stock_code = product_code or barcode

      # Update images if available
      if images:
        trendyol_product.image_url = images[0]
        trendyol_product.additional_images = images[1:] if len(
            images) > 1 else []

      trendyol_product.save()
      logger.info(
          f"Updated Trendyol product {trendyol_product.id} from LCW product {lcw_product.id}"
      )

    return trendyol_product
  except Exception as e:
    logger.error(
        f"Error converting LCWaikiki product to Trendyol product: {str(e)}")
    logger.exception(e)  # Log full traceback for debugging
    return None
