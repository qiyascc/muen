import requests
import json
import uuid
import logging
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
import time
from decimal import Decimal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trendyol_integration.log'),
        logging.StreamHandler()
    ]
)
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
    brand_id: int  # Modified to use brand_id directly
    category_id: int  # Modified to use category_id directly
    quantity: int
    stock_code: str
    price: Decimal
    sale_price: Decimal  # Often same as price
    description: str
    image_url: str
    additional_images: List[str] = None
    attributes: List[Dict] = None
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
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Making {method} request to {url}")
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {str(e)}")
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                time.sleep(RETRY_DELAY * (attempt + 1))
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Dict) -> Dict:
        logger.debug(f"Sending POST data: {json.dumps(data, default=str)}")
        return self._make_request('POST', endpoint, json=data)

class TrendyolProductManager:
    """Handles product creation and management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
    
    def create_product(self, product_data: ProductData) -> str:
        """Create a new product on Trendyol"""
        try:
            payload = self._build_product_payload(product_data)
            logger.info(f"Submitting product creation request for {product_data.title}")
            
            response = self.api.post(
                f"product/sellers/{self.api.config.seller_id}/products", 
                payload
            )
            
            if 'batchRequestId' in response:
                logger.info(f"Product creation batch initiated with ID: {response['batchRequestId']}")
                return response['batchRequestId']
            else:
                logger.warning(f"Unexpected response format: {response}")
                return None
        except Exception as e:
            logger.error(f"Product creation failed: {str(e)}")
            raise
    
    def check_batch_status(self, batch_id: str) -> Dict:
        """Check the status of a batch operation"""
        try:
            return self.api.get(f"product/sellers/{self.api.config.seller_id}/products/batch-requests/{batch_id}")
        except Exception as e:
            logger.error(f"Failed to check batch status: {str(e)}")
            raise
    
    def _build_product_payload(self, product: ProductData) -> Dict:
        """Construct the complete product payload"""
        # Prepare images in required format
        images = [{"url": product.image_url}]
        if product.additional_images:
            for img_url in product.additional_images:
                if img_url:  # Skip empty URLs
                    images.append({"url": img_url})
        
        # Construct the payload
        return {
            "items": [{
                "barcode": product.barcode,
                "title": product.title,
                "productMainId": product.product_main_id,
                "brandId": product.brand_id,
                "categoryId": product.category_id,
                "quantity": product.quantity,
                "stockCode": product.stock_code,
                "dimensionalWeight": product.dimensional_weight,
                "description": product.description,
                "currencyType": product.currency_type,
                "listPrice": float(product.price),
                "salePrice": float(product.sale_price or product.price),
                "vatRate": product.vat_rate,
                "images": images,
                "attributes": product.attributes if product.attributes else []
            }]
        }
    
    def get_category_attributes(self, category_id: int) -> List[Dict]:
        """Get attributes for a specific category"""
        try:
            data = self.api.get(f"product/product-categories/{category_id}/attributes")
            return data.get('categoryAttributes', [])
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            return []
    
    def update_price_and_inventory(self, products: List[Dict]) -> Dict:
        """Update price and inventory for multiple products"""
        try:
            payload = {"items": products}
            return self.api.post(f"product/sellers/{self.api.config.seller_id}/products/price-and-inventory", payload)
        except Exception as e:
            logger.error(f"Failed to update price and inventory: {str(e)}")
            raise
    
    def fetch_brands(self, name: Optional[str] = None) -> List[Dict]:
        """Fetch brands from Trendyol, optionally filtered by name"""
        endpoint = "product/brands"
        if name:
            from urllib.parse import quote
            endpoint = f"product/brands/by-name?name={quote(name)}"
        
        try:
            return self.api.get(endpoint)
        except Exception as e:
            logger.error(f"Failed to fetch brands: {str(e)}")
            return []
    
    def fetch_categories(self) -> List[Dict]:
        """Fetch all categories from Trendyol"""
        try:
            data = self.api.get("product/product-categories")
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            return []