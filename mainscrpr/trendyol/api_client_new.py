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

        # Debug request payload for POST requests
        if method == 'POST' and 'json' in kwargs:
          print(
              f"[DEBUG-API] İSTEK PAYLOAD: {json.dumps(kwargs.get('json', {}), indent=2, ensure_ascii=False)}"
          )

        response = self.session.request(method, url, **kwargs)

        # Debug response details
        print(f"[DEBUG-API] YANIT KODU: {response.status_code}")
        print(f"[DEBUG-API] YANIT HEADERS: {dict(response.headers)}")

        # Print response content (truncated if too long)
        resp_text = response.text[:1000] + '...' if len(
            response.text) > 1000 else response.text
        print(f"[DEBUG-API] YANIT İÇERİĞİ: {resp_text}")

        # More detailed error logging
        if response.status_code >= 400:
          print(f"[DEBUG-API] HATA DETAYI: Kod {response.status_code}")
          try:
            if 'application/json' in response.headers.get('Content-Type', ''):
              error_data = response.json()
              print(
                  f"[DEBUG-API] JSON HATA DETAYI: {json.dumps(error_data, indent=2, ensure_ascii=False)}"
              )
          except Exception as e:
            print(f"[DEBUG-API] JSON çözümlenemedi: {str(e)}")

        response.raise_for_status()

        # Handle empty response
        if not response.text:
          return {}

        # Try to parse JSON
        try:
          return response.json()
        except json.JSONDecodeError as e:
          logger.error(f"Failed to parse JSON response: {str(e)}")
          return {"error": "Invalid JSON response", "text": response.text}

      except requests.exceptions.RequestException as e:
        if attempt == MAX_RETRIES - 1:
          logger.error(
              f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
          # Return empty dict instead of raising exception
          return {"error": f"Request failed: {str(e)}"}

        logger.warning(f"Attempt {attempt + 1} failed, retrying...")
        time.sleep(RETRY_DELAY * (attempt + 1))

  def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
    return self._make_request('GET', endpoint, params=params)

  def post(self, endpoint: str, data: Dict) -> Dict:
    # Debug logging for request body
    print(
        f"[DEBUG-API] POST isteği gövdesi (JSON): {json.dumps(data, indent=2, ensure_ascii=False)}"
    )
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

  def find_best_category(self, search_term: str, deep_search: bool = True) -> int:
    """Find the most relevant category for a given search term using multiple strategies"""
    try:
      categories = self.category_cache
      if not categories:
        raise ValueError("Empty category list received from API")

      # Strategy 1: Try for exact match first (case insensitive)
      leaf_categories = self._get_all_leaf_categories(categories)
      search_term_lower = search_term.lower()
      
      # Try exact match
      for cat in leaf_categories:
        if search_term_lower == cat['name'].lower():
          logger.info(f"Found exact match category: {cat['name']} (ID: {cat['id']})")
          return cat['id']
      
      # Strategy 2: Try substring match - if the search term is fully contained in category name
      for cat in leaf_categories:
        if search_term_lower in cat['name'].lower():
          logger.info(f"Found substring match category: {cat['name']} (ID: {cat['id']})")
          return cat['id']
      
      # Strategy 3: Try partial match - each word in search term is contained in category
      if deep_search:
        search_words = search_term_lower.split()
        best_match = None
        best_match_score = 0
        
        for cat in leaf_categories:
          cat_name_lower = cat['name'].lower()
          match_score = 0
          
          # Count how many words from search term appear in this category
          for word in search_words:
            if word in cat_name_lower:
              match_score += 1
          
          # Calculate what percentage of search words matched
          match_percentage = match_score / len(search_words) if search_words else 0
          
          # If this is the best match so far, save it
          if match_score > 0 and match_percentage > best_match_score:
            best_match = cat
            best_match_score = match_percentage
        
        # If we found a partial match with at least 50% of words matching
        if best_match and best_match_score >= 0.5:
          logger.info(f"Found partial match category: {best_match['name']} (ID: {best_match['id']}) with score {best_match_score:.2f}")
          return best_match['id']
      
      # Strategy 4: Try to find category by removing words from search term one by one
      if deep_search and ' ' in search_term:
        # Try with fewer words
        words = search_term.split()
        for i in range(len(words) - 1, 0, -1):
          for combo in [words[:i], words[-i:]]:  # Try both beginning and ending parts
            shorter_term = ' '.join(combo)
            logger.info(f"Trying with shorter term: '{shorter_term}'")
            try:
              return self.find_best_category(shorter_term, False)  # No recursive deep search
            except ValueError:
              continue
      
      # Strategy 5: Try individual words
      if deep_search and ' ' in search_term:
        for word in search_words:
          if len(word) > 3:  # Only try with meaningful words
            logger.info(f"Trying with single word: '{word}'")
            try:
              return self.find_best_category(word, False)  # No recursive deep search
            except ValueError:
              continue
      
      # Log information about available categories to help debugging
      logger.warning(f"No category found for '{search_term}'. Available categories at top level:")
      for i, cat in enumerate(categories[:10]):  # Log first 10 top-level categories
        logger.warning(f"  {i+1}. {cat['name']} (ID: {cat['id']})")
      
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

      # Debug log the full category attributes
      print(
          f"[DEBUG-API] Kategori {category_id} için özellikler: {json.dumps(category_attrs, indent=2, ensure_ascii=False)[:1000]}..."
      )

      # Look specifically for color attribute as it's often required
      color_attr = None
      required_attrs = []

      # First pass - identify required attributes
      for attr in category_attrs.get('categoryAttributes', []):
        attr_name = attr['attribute']['name']
        attr_id = attr['attribute']['id']
        is_required = attr.get('required', False)

        if is_required:
          required_attrs.append(f"{attr_name} (ID: {attr_id})")

        # Check if this is a color attribute (important for Trendyol)
        if attr_name.lower() in ['renk', 'color', 'colour']:
          color_attr = attr
          print(
              f"[DEBUG-API] Renk özelliği bulundu: {attr_name} (ID: {attr_id})"
          )

      # Log required attributes
      if required_attrs:
        print(f"[DEBUG-API] Zorunlu özellikler: {', '.join(required_attrs)}")

      # Process all attributes
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

      # Add special handling for color if it's required but not found
      if color_attr and not any(
          a.get('attributeName', '').lower() in ['renk', 'color', 'colour']
          for a in attributes):
        print(
            "[DEBUG-API] Renk özelliği zorunlu fakat eklenmemiş. Manuel olarak ekleniyor."
        )
        color_attribute = {
            "attributeId": color_attr['attribute']['id'],
            "attributeName": color_attr['attribute']['name']
        }

        if color_attr.get('attributeValues') and len(
            color_attr['attributeValues']) > 0:
          color_attribute["attributeValueId"] = color_attr['attributeValues'][
              0]['id']
          color_attribute["attributeValue"] = color_attr['attributeValues'][0][
              'name']
        else:
          color_attribute["customAttributeValue"] = "Karışık Renkli"

        attributes.append(color_attribute)

      # Debug log the final attributes
      print(
          f"[DEBUG-API] Oluşturulan özellikler: {json.dumps(attributes, indent=2, ensure_ascii=False)}"
      )

      return attributes
    except Exception as e:
      logger.error(
          f"Failed to get attributes for category {category_id}: {str(e)}")
      print(f"[DEBUG-API] Kategori özellikleri alınırken hata: {str(e)}")
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
          vat_rate=10  # Default VAT rate in Turkey
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

  # Clean up description - remove any "Satıcı:" text and related HTML
  description = trendyol_product.description
  if description:
    import re
    # Remove p tag containing "Satıcı:" text
    description = re.sub(r'<p[^>]*>.*?Satıcı:.*?</p>', '', description, flags=re.DOTALL)
    # Also remove just the b tag with "Satıcı:" if it exists
    description = re.sub(r'<b[^>]*>.*?Satıcı:.*?</b>', '', description, flags=re.DOTALL)
    print(f"[DEBUG-API] Açıklama temizlendi: {description[:200]}...")
    
  # Clean up product title - normalize spaces
  title = trendyol_product.title
  if title:
    import re
    # Replace multiple spaces with a single space
    title = re.sub(r'\s+', ' ', title.strip())
    print(f"[DEBUG-API] Ürün adı temizlendi: '{title}'")
  else:
    title = trendyol_product.title

  # Get required attributes for the category
  product_manager = get_product_manager()
  attributes = product_manager._get_attributes_for_category(
      trendyol_product.category_id)

  # Construct the payload
  payload = {
      "barcode": trendyol_product.barcode,
      "title": title,  # Use cleaned title
      "productMainId": trendyol_product.product_main_id,
      "brandId": trendyol_product.brand_id,
      "categoryId": trendyol_product.category_id,
      "quantity": trendyol_product.quantity,
      "stockCode": trendyol_product.stock_code,
      "dimensionalWeight": 1,  # Default value
      "description": description,  # Use cleaned description
      "currencyType": trendyol_product.currency_type or "TRY",
      "listPrice": float(trendyol_product.price),
      "salePrice":
      float(trendyol_product.price),  # Use the same price if no discount
      "vatRate": trendyol_product.vat_rate or 10,
      "images": [{
          "url": trendyol_product.image_url
      }],
      "attributes": attributes
  }

  # Add additional images if available
  if trendyol_product.additional_images:
    for img in trendyol_product.additional_images:
      payload["images"].append({"url": img})
  print(payload)

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
