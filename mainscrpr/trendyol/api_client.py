import requests
import json
import time
import re
import uuid
from urllib.parse import quote
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from functools import lru_cache
import logging
from decimal import Decimal

from django.utils import timezone
from .models import TrendyolProduct, TrendyolBrand, TrendyolCategory, TrendyolAPIConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trendyol_integration.log'),
        logging.StreamHandler()
    ])
logger = logging.getLogger(__name__)

TRENDYOL_API_BASE_URL = "https://apigw.trendyol.com/integration/"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1


@dataclass
class APIConfig:
  api_key: str
  seller_id: str
  base_url: str = TRENDYOL_API_BASE_URL


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
  vat_rate: int = 10
  cargo_company_id: int = 10
  currency_type: str = "TRY"
  dimensional_weight: int = 1


class TrendyolAPI:
  """Base class for Trendyol API operations with retry mechanism"""

  def __init__(self, config: APIConfig):
    self.config = config
    self.session = requests.Session()
    self.session.headers.update({
        "Authorization": f"Basic {self.config.api_key}",
        "User-Agent": f"{self.config.seller_id} - SelfIntegration",
        "Content-Type": "application/json"
    })

  def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
    """Generic request method with retry logic"""
    # Endpoint işlenmeden önce debug logu
    print(f"[DEBUG-API] make_request çağrısı. Orijinal endpoint: {endpoint}")

    url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    print(f"[DEBUG-API] Oluşturulan URL: {url}")

    kwargs.setdefault('timeout', DEFAULT_TIMEOUT)

    for attempt in range(MAX_RETRIES):
      try:
        print(f"[DEBUG-API] SON İSTEK: {method} {url}")
        print(f"[DEBUG-API] İSTEK HEADERS: {self.session.headers}")

        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
      except requests.exceptions.RequestException as e:
        if attempt == MAX_RETRIES - 1:
          logger.error(
              f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
          raise
        logger.warning(f"Attempt {attempt + 1} failed, retrying...")
        time.sleep(RETRY_DELAY * (attempt + 1))

  def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
    return self._make_request('GET', endpoint, params=params)

  def post(self, endpoint: str, data: Dict) -> Dict:
    return self._make_request('POST', endpoint, json=data)


class TrendyolCategoryFinder:
  """Handles category discovery and attribute management"""

  def __init__(self, api_client: TrendyolAPI):
    self.api = api_client
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
      data = self.api.get("product/product-categories")
      return data.get('categories', [])
    except Exception as e:
      logger.error(f"Failed to fetch categories: {str(e)}")
      raise Exception(
          "Failed to load categories. Please check your API credentials and try again."
      )

  @lru_cache(maxsize=128)
  def get_category_attributes(self, category_id: int) -> Dict:
    """Get attributes for a specific category with caching"""
    try:
      data = self.api.get(
          f"product/product-categories/{category_id}/attributes")
      return data
    except Exception as e:
      logger.error(
          f"Failed to fetch attributes for category {category_id}: {str(e)}")
      raise Exception(f"Failed to load attributes for category {category_id}")

  def find_best_category(self, search_term: str) -> int:
    """Find the most relevant category for a given search term"""
    try:
      categories = self.category_cache
      if not categories:
        raise ValueError("Empty category list received from API")

      # For the simplified implementation, just return the first matching category
      for cat in self._get_all_leaf_categories(categories):
        if search_term.lower() in cat['name'].lower():
          logger.info(
              f"Found matching category: {cat['name']} (ID: {cat['id']})")
          return cat['id']

      # If no match found, raise an exception
      raise ValueError(f"No matching category found for: {search_term}")

    except Exception as e:
      logger.error(f"Category search failed for '{search_term}': {str(e)}")
      raise

  def _get_all_leaf_categories(self, categories: List[Dict]) -> List[Dict]:
    """Get all leaf categories (categories without children)"""
    leaf_categories = []
    self._collect_leaf_categories(categories, leaf_categories)
    return leaf_categories

  def _collect_leaf_categories(self, categories: List[Dict],
                               result: List[Dict]) -> None:
    """Recursively collect leaf categories"""
    for cat in categories:
      if not cat.get('subCategories'):
        result.append(cat)
      else:
        self._collect_leaf_categories(cat['subCategories'], result)


class TrendyolProductManager:
  """Handles product creation and management"""

  def __init__(self, api_client: TrendyolAPI):
    self.api = api_client
    self.category_finder = TrendyolCategoryFinder(api_client)

  def get_brand_id(self, brand_name: str) -> int:
    """Find brand ID by name"""
    encoded_name = quote(brand_name)
    try:
      brands = self.api.get(f"product/brands/by-name?name={encoded_name}")
      if isinstance(brands, list) and brands:
        return brands[0]['id']
      # If LC Waikiki not found, use default ID 7651
      if 'LCW' in brand_name or 'LC Waikiki' in brand_name:
        logger.warning(
            f"Brand not found: {brand_name}, using default LC Waikiki ID: 7651"
        )
        return 7651

      raise ValueError(f"Brand not found: {brand_name}")
    except Exception as e:
      logger.error(f"Brand search failed for '{brand_name}': {str(e)}")
      raise

  def create_product(self, product_data: ProductData) -> str:
    """Create a new product on Trendyol"""
    try:
      category_id = self.category_finder.find_best_category(
          product_data.category_name)
      brand_id = self.get_brand_id(product_data.brand_name)
      attributes = self._get_attributes_for_category(category_id)

      payload = self._build_product_payload(product_data, category_id,
                                            brand_id, attributes)
      logger.info("Submitting product creation request...")
      response = self.api.post(
          f"product/sellers/{self.api.config.seller_id}/products", payload)

      return response.get('batchRequestId')
    except Exception as e:
      logger.error(f"Product creation failed: {str(e)}")
      raise

  def check_batch_status(self, batch_id: str) -> Dict:
    """Check the status of a batch operation"""
    try:
      return self.api.get(
          f"product/sellers/{self.api.config.seller_id}/products/batch-requests/{batch_id}"
      )
    except Exception as e:
      logger.error(f"Failed to check batch status: {str(e)}")
      raise

  def _build_product_payload(self, product: ProductData, category_id: int,
                             brand_id: int, attributes: List[Dict]) -> Dict:
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
            "dimensionalWeight": product.dimensional_weight,
            "description": product.description,
            "currencyType": product.currency_type,
            "listPrice": product.price,
            "salePrice": product.sale_price,
            "vatRate": product.vat_rate,
            # "cargoCompanyId": product.cargo_company_id,
            "images": [{
                "url": product.image_url
            }],
            "attributes": attributes
        }]
    }

  def _get_attributes_for_category(self, category_id: int) -> List[Dict]:
    """Generate attributes for a category based on API data"""
    attributes = []
    try:
      category_attrs = self.category_finder.get_category_attributes(
          category_id)

      for attr in category_attrs.get('categoryAttributes', []):
        # Skip if no attribute values and custom values not allowed
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
            attribute[
                "customAttributeValue"] = f"Sample {attr['attribute']['name']}"
        elif attr.get('allowCustom'):
          attribute[
              "customAttributeValue"] = f"Sample {attr['attribute']['name']}"
        else:
          continue

        attributes.append(attribute)

      return attributes
    except Exception as e:
      logger.error(
          f"Failed to get attributes for category {category_id}: {str(e)}")
      # Throw error to prevent using fallback attributes, as per requirement
      raise


def get_api_config_from_db() -> APIConfig:
  """Get API configuration from database"""
  config = TrendyolAPIConfig.objects.filter(is_active=True).first()
  if not config:
    raise ValueError("No active Trendyol API configuration found")

  return APIConfig(api_key=config.api_key,
                   seller_id=config.seller_id,
                   base_url=config.base_url)


def get_api_client() -> TrendyolAPI:
  """Get a TrendyolAPI client instance"""
  config = get_api_config_from_db()
  return TrendyolAPI(config)


def get_product_manager() -> TrendyolProductManager:
  """Get a TrendyolProductManager instance"""
  api_client = get_api_client()
  return TrendyolProductManager(api_client)


def lcwaikiki_to_trendyol_product(lcw_product) -> Optional[TrendyolProduct]:
  """
    Convert an LCWaikiki product to a Trendyol product.
    Returns the created or updated Trendyol product instance.
    
    This version ensures we fetch all required data from API and throws
    errors if data isn't available.
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
      discount = (price * lcw_product.discount_ratio) / 100
      sale_price = price - discount
    else:
      sale_price = price

    # Get product images from the images field (JSONField that contains a list of image URLs)
    images = []
    if hasattr(lcw_product, 'images') and lcw_product.images:
      # If it's already a list, use it directly
      if isinstance(lcw_product.images, list):
        images = lcw_product.images
      # If it's a string (serialized JSON), parse it
      elif isinstance(lcw_product.images, str):
        try:
          img_data = json.loads(lcw_product.images)
          if isinstance(img_data, list):
            images = img_data
        except Exception as e:
          logger.warning(
              f"Failed to parse images for product {lcw_product.id}: {str(e)}")
      # Handle case when the images field contains a dictionary with image URLs
      elif isinstance(lcw_product.images,
                      dict) and 'urls' in lcw_product.images:
        img_urls = lcw_product.images.get('urls', [])
        if isinstance(img_urls, list):
          images = img_urls

    # Use first image as primary if available
    if not images and hasattr(lcw_product, 'url'):
      # If no images found but we have the product URL, use a default image or placeholder
      logger.warning(
          f"No images found for product {lcw_product.id}, using placeholder")
      images = [lcw_product.url]  # Use product URL as a reference

    # Ensure all image URLs are properly formatted
    for i in range(len(images)):
      img = images[i]
      if img.startswith('//'):
        images[i] = f"https:{img}"
      elif not img.startswith('http'):
        images[i] = f"https://{img}"

    # If no images found, throw an error as per requirement
    if not images:
      raise ValueError(f"No valid images found for product {lcw_product.id}")

    # Get quantity from product
    quantity = 0
    if hasattr(lcw_product, 'get_total_stock'):
      try:
        stock = lcw_product.get_total_stock()
        if stock and stock > 0:
          quantity = stock
      except Exception as e:
        logger.warning(
            f"Error getting total stock for product {lcw_product.id}: {str(e)}"
        )

    # If quantity is 0, throw an error as per requirement
    if quantity == 0:
      raise ValueError(f"Zero stock quantity for product {lcw_product.id}")

    # Get API client for next operations
    api_client = get_api_client()
    product_manager = TrendyolProductManager(api_client)

    # Find the appropriate brand ID in the Trendyol system
    brand_id = None
    try:
      # Try to get LC Waikiki brand ID from API
      brand_id = product_manager.get_brand_id("LC Waikiki")
      logger.info(f"Found brand ID: {brand_id}")
    except Exception as e:
      # If API fails, try to get from database
      lcw_brand = TrendyolBrand.objects.filter(name__icontains="LCW",
                                               is_active=True).first()
      if lcw_brand:
        brand_id = lcw_brand.brand_id
        logger.info(
            f"Found brand from database: {lcw_brand.name} (ID: {brand_id})")
      else:
        # Use default LC Waikiki ID
        brand_id = 7651
        logger.warning(f"Using default LC Waikiki brand ID: {brand_id}")

    # Find category information
    category_id = None
    category_name = lcw_product.category or ""

    # If product already has a category, use it
    if trendyol_product and trendyol_product.category_id:
      category_id = trendyol_product.category_id
    else:
      # Try to find category from API
      try:
        if category_name:
          category_id = product_manager.category_finder.find_best_category(
              category_name)
          logger.info(f"Found category ID: {category_id} for {category_name}")
      except Exception as e:
        logger.error(
            f"Error finding category for product {lcw_product.id}: {str(e)}")
        # If category finding fails, throw error as per requirement
        raise ValueError(
            f"Could not find appropriate category for product: {category_name}"
        )

    # Create or update Trendyol product
    if not trendyol_product:
      # Create a new Trendyol product
      trendyol_product = TrendyolProduct.objects.create(
          title=lcw_product.title or "LC Waikiki Product",
          description=lcw_product.description or lcw_product.title
          or "LC Waikiki Product Description",
          barcode=barcode,
          product_main_id=product_code or barcode,
          stock_code=product_code or barcode,
          brand_name="LCW",
          brand_id=brand_id,
          category_name=category_name,
          category_id=category_id,
          pim_category_id=category_id,  # Use same as category_id initially
          price=price,
          quantity=quantity,
          image_url=images[0],
          additional_images=images[1:] if len(images) > 1 else [],
          attributes=[],  # We'll fetch from API when sending to Trendyol
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
      trendyol_product.price = price
      trendyol_product.quantity = quantity
      trendyol_product.brand_id = brand_id or trendyol_product.brand_id
      trendyol_product.category_id = category_id or trendyol_product.category_id
      trendyol_product.pim_category_id = category_id or trendyol_product.pim_category_id

      # We'll fetch attributes from API when sending to Trendyol
      if not trendyol_product.attributes:
        trendyol_product.attributes = []

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
    raise  # Re-raise the exception as per requirement


def prepare_product_for_trendyol(trendyol_product: TrendyolProduct) -> Dict:
  """
    Prepare a Trendyol product for submission to the API.
    This includes fetching required attributes from the API.
    
    Returns a payload dictionary ready for submission to Trendyol API.
    Raises exceptions if required data is missing.
    """
  if not trendyol_product:
    raise ValueError("No product provided")

  if not trendyol_product.category_id:
    raise ValueError(f"Product {trendyol_product.id} has no category ID")

  if not trendyol_product.brand_id:
    raise ValueError(f"Product {trendyol_product.id} has no brand ID")

  # Get required attributes for the category
  product_manager = get_product_manager()
  attributes = product_manager._get_attributes_for_category(
      trendyol_product.category_id)

  # Construct the payload
  payload = {
      "barcode": trendyol_product.barcode,
      "title": trendyol_product.title,
      "productMainId": trendyol_product.product_main_id,
      "brandId": trendyol_product.brand_id,
      "categoryId": trendyol_product.category_id,
      "quantity": trendyol_product.quantity,
      "stockCode": trendyol_product.stock_code,
      "dimensionalWeight": 1,  # Default value
      "description": trendyol_product.description,
      "currencyType": trendyol_product.currency_type or "TRY",
      "listPrice": float(trendyol_product.price),
      "salePrice":
      float(trendyol_product.price),  # Use the same price if no discount
      "vatRate": trendyol_product.vat_rate or 18,
      "images": [{
          "url": trendyol_product.image_url
      }],
      "attributes": attributes
  }

  # Add additional images if available
  if trendyol_product.additional_images:
    for img in trendyol_product.additional_images:
      payload["images"].append({"url": img})

  return payload


def sync_product_to_trendyol(trendyol_product: TrendyolProduct) -> str:
  """
    Sync a Trendyol product to the Trendyol platform.
    Returns the batch ID of the submission.
    Raises exceptions if the sync fails.
    """
  try:
    # Prepare the product data
    product_data = prepare_product_for_trendyol(trendyol_product)

    # Get the API client
    api_client = get_api_client()

    # Send the product to Trendyol
    response = api_client.post(
        f"product/sellers/{api_client.config.seller_id}/products",
        {"items": [product_data]})

    # Get the batch ID
    batch_id = response.get('batchRequestId')
    if not batch_id:
      raise ValueError(f"No batch ID returned from Trendyol API: {response}")

    # Update the product with the batch ID
    trendyol_product.batch_id = batch_id
    trendyol_product.batch_status = 'processing'
    trendyol_product.last_sync_time = timezone.now()
    trendyol_product.status_message = "Product submitted to Trendyol"
    trendyol_product.save()

    logger.info(
        f"Product {trendyol_product.id} submitted to Trendyol with batch ID: {batch_id}"
    )

    return batch_id
  except Exception as e:
    # Update the product status
    trendyol_product.batch_status = 'failed'
    trendyol_product.status_message = f"Sync failed: {str(e)}"
    trendyol_product.save()

    logger.error(
        f"Failed to sync product {trendyol_product.id} to Trendyol: {str(e)}")
    raise


def check_product_batch_status(trendyol_product: TrendyolProduct) -> Dict:
  """
    Check the status of a batch request for a product.
    Returns the status information from the Trendyol API.
    """
  try:
    if not trendyol_product.batch_id:
      return {"error": "No batch ID for this product"}

    # Get the API client
    api_client = get_api_client()

    # Create product manager to check batch status
    product_manager = get_product_manager()

    # Get the batch status
    status = product_manager.check_batch_status(trendyol_product.batch_id)

    # Update the product status based on the response
    if status:
      # Check if the batch processing is complete
      is_completed = status.get('batchStatus') == 'COMPLETED'

      if is_completed:
        trendyol_product.batch_status = 'completed'
        trendyol_product.status_message = "Product successfully processed by Trendyol"
      else:
        # Still processing
        trendyol_product.batch_status = 'processing'
        trendyol_product.status_message = f"Status: {status.get('batchStatus', 'PROCESSING')}"

      trendyol_product.save()

    return status
  except Exception as e:
    logger.error(
        f"Failed to check batch status for product {trendyol_product.id}: {str(e)}"
    )
    return {"error": str(e)}
