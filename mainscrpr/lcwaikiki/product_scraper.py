import logging
import json
import re
import time
import random
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .product_models import Product, ProductSize, City, Store, SizeStoreStock
from .models import ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl, Config

# Configure logging for better readability
logger = logging.getLogger(__name__)

class ProductScraper:
    """LCWaikiki product scraper with improved proxy and user agent handling"""
    
    # Define a list of common user agents
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPad; CPU OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1'
    ]
    
    DEFAULT_CITY_ID = "865"
    INVENTORY_API_URL = "https://www.lcw.com/tr-TR/TR/ajax/Model/GetStoreInventoryMultiple"
    
    def __init__(self):
        self.session = requests.Session()
        # Get active configuration
        try:
            self.config = Config.objects.filter(is_active=True).first()
            if not self.config:
                self.config = Config.objects.first()  # Fallback to any config
                
            # Get scraper configuration from Config model if available
            if self.config and 'scraper_config' in self.config.brands:
                scraper_config = self.config.brands.get('scraper_config', {})
                self.max_retries = scraper_config.get('max_retries', 5)
                self.retry_delay = scraper_config.get('retry_delay', 5)
                self.default_timeout = scraper_config.get('timeout', 30)
                self.max_proxy_attempts = scraper_config.get('max_proxy_attempts', 3)
            else:
                # Default values
                self.max_retries = 5
                self.retry_delay = 5
                self.default_timeout = 30
                self.max_proxy_attempts = 3
                
            # Get city configuration
            if self.config:
                self.default_city_id = self.config.default_city_id
            else:
                self.default_city_id = self.DEFAULT_CITY_ID
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            # Default values if configuration loading fails
            self.max_retries = 5
            self.retry_delay = 5
            self.default_timeout = 30
            self.max_proxy_attempts = 3
            self.default_city_id = self.DEFAULT_CITY_ID
            self.config = None
            
        self.proxy_list = getattr(settings, 'PROXY_LIST', [])
        
    def _get_random_proxy(self):
        """Get a random proxy from settings"""
        if not self.proxy_list:
            return None
        return random.choice(self.proxy_list)
    
    def _get_headers(self):
        """Generate request headers with random user agent"""
        user_agent = random.choice(self.USER_AGENTS)
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.lcw.com/',
            'User-Agent': user_agent,
        }
        
    def fetch(self, url, max_proxy_attempts=3):
        """Fetch URL content with retry and proxy rotation logic"""
        if max_proxy_attempts is None:
            max_proxy_attempts = len(self.proxy_list) if self.proxy_list else 1
            
        proxy_attempts = 0
        proxies_tried = set()
        
        while proxy_attempts < max_proxy_attempts:
            # Get a proxy that hasn't been tried yet if possible
            available_proxies = [p for p in self.proxy_list if p not in proxies_tried] if self.proxy_list else [None]
            if not available_proxies:
                logger.warning("All proxies have been tried without success")
                break
                
            proxy = random.choice(available_proxies)
            proxies = {"http": proxy, "https": proxy} if proxy else None
            
            if proxy:
                proxies_tried.add(proxy)
            
            # Update headers with new random user agent for each attempt
            self.session.headers.update(self._get_headers())
            
            logger.info(f"Proxy attempt {proxy_attempts + 1}/{max_proxy_attempts}: {proxy}")
            
            # Try up to max_retries times with this proxy
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = self.session.get(
                        url, 
                        proxies=proxies, 
                        timeout=30,
                        allow_redirects=True,
                        verify=True
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Successfully fetched {url}")
                        return response
                    
                    elif response.status_code == 403:
                        logger.warning(f"Access denied (403) with proxy {proxy}, attempt {attempt}")
                        if attempt == self.max_retries:
                            break  # Try next proxy
                        time.sleep(self.retry_delay * attempt)  # Exponential backoff
                        
                    else:
                        logger.warning(f"HTTP {response.status_code} with proxy {proxy}, attempt {attempt}")
                        response.raise_for_status()
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request error with proxy {proxy}, attempt {attempt}: {str(e)}")
                    if attempt == self.max_retries:
                        break  # Try next proxy
                    time.sleep(self.retry_delay * attempt)  # Exponential backoff
            
            proxy_attempts += 1
        
        logger.error("All proxy attempts failed")
        return None
    
    def post(self, url, data, headers=None, max_proxy_attempts=3):
        """POST request with retry and proxy rotation logic"""
        if max_proxy_attempts is None:
            max_proxy_attempts = len(self.proxy_list) if self.proxy_list else 1
            
        proxy_attempts = 0
        proxies_tried = set()
        
        while proxy_attempts < max_proxy_attempts:
            # Get a proxy that hasn't been tried yet if possible
            available_proxies = [p for p in self.proxy_list if p not in proxies_tried] if self.proxy_list else [None]
            if not available_proxies:
                logger.warning("All proxies have been tried without success")
                break
                
            proxy = random.choice(available_proxies)
            proxies = {"http": proxy, "https": proxy} if proxy else None
            
            if proxy:
                proxies_tried.add(proxy)
            
            # Update headers with new random user agent for each attempt
            if headers is None:
                headers = {}
            headers.update(self._get_headers())
            
            logger.info(f"Proxy attempt {proxy_attempts + 1}/{max_proxy_attempts}: {proxy}")
            
            # Try up to max_retries times with this proxy
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = self.session.post(
                        url, 
                        json=data,
                        headers=headers,
                        proxies=proxies, 
                        timeout=30,
                        allow_redirects=True,
                        verify=True
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Successfully posted to {url}")
                        return response
                    
                    elif response.status_code == 403:
                        logger.warning(f"Access denied (403) with proxy {proxy}, attempt {attempt}")
                        if attempt == self.max_retries:
                            break  # Try next proxy
                        time.sleep(self.retry_delay * attempt)  # Exponential backoff
                        
                    else:
                        logger.warning(f"HTTP {response.status_code} with proxy {proxy}, attempt {attempt}")
                        response.raise_for_status()
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request error with proxy {proxy}, attempt {attempt}: {str(e)}")
                    if attempt == self.max_retries:
                        break  # Try next proxy
                    time.sleep(self.retry_delay * attempt)  # Exponential backoff
            
            proxy_attempts += 1
        
        logger.error("All proxy attempts failed")
        return None

    def fetch_inventory(self, product_option_size_ref, referer_url, city_id=None):
        """
        Fetch inventory information for a specific product size reference.
        This method uses the store inventory API to get stock information for all stores.
        
        Args:
            product_option_size_ref: The product option size reference ID
            referer_url: The product URL to use as referer
            city_id: The city ID to check inventory for (defaults to self.default_city_id)
            
        Returns:
            dict: The JSON response from the inventory API, or None if the request failed
        """
        if not city_id:
            city_id = self.default_city_id
            
        try:
            headers = {
                'User-Agent': random.choice(self.USER_AGENTS),
                'Content-Type': 'application/json',
                'Referer': referer_url
            }
            
            data = {
                "cityId": str(city_id),
                "countyIds": [],
                "urunOptionSizeRef": str(product_option_size_ref)
            }
            
            logger.info(f"Fetching inventory for product_option_size_ref={product_option_size_ref}, city_id={city_id}")
            response = self.post(self.INVENTORY_API_URL, data, headers)
            
            if response and response.status_code == 200:
                try:
                    result = response.json()
                    if result:
                        logger.info(f"Successfully fetched inventory: {len(result.get('storeInventoryInfos', []))} stores found")
                        return result
                except Exception as e:
                    logger.error(f"Error parsing inventory JSON: {str(e)}")
            else:
                logger.warning(f"Failed to fetch inventory: HTTP {response.status_code if response else 'No response'}")
                
            return None
        except Exception as e:
            logger.error(f"Error fetching inventory: {str(e)}")
            return None
    
    def process_inventory_data(self, product_size, inventory_data):
        """
        Process inventory data from the API and update the database.
        This method will create or update City and Store records as needed.
        
        Args:
            product_size: The ProductSize model instance to update
            inventory_data: The inventory data from the API
            
        Returns:
            bool: True if the inventory was successfully processed, False otherwise
        """
        try:
            if not inventory_data or 'storeInventoryInfos' not in inventory_data:
                logger.warning("No store inventory information found")
                return False
                
            # Get active cities from configuration
            active_cities = self.config.active_cities if self.config else ['865']
            
            # Dictionary to track cities and their total stock
            city_stocks = {}
            
            # Process each store
            for store_data in inventory_data.get('storeInventoryInfos', []):
                city_id = str(store_data.get('StoreCityId'))
                city_name = store_data.get('StoreCityName')
                
                # Skip cities that are not in the active list
                if city_id not in active_cities:
                    continue
                
                # Create or get city
                city, _ = City.objects.get_or_create(
                    city_id=city_id,
                    defaults={'name': city_name}
                )
                
                # Create or update store
                store, _ = Store.objects.update_or_create(
                    store_code=store_data.get('StoreCode', ''),
                    defaults={
                        'store_name': store_data.get('StoreName', ''),
                        'city': city,
                        'store_county': store_data.get('StoreCountyName', ''),
                        'store_phone': store_data.get('StorePhone', ''),
                        'address': store_data.get('Address', ''),
                        'latitude': store_data.get('Lattitude', ''),
                        'longitude': store_data.get('Longitude', '')
                    }
                )
                
                # Store stock quantity
                stock_quantity = store_data.get('Quantity', 0)
                
                # Create or update store stock
                SizeStoreStock.objects.update_or_create(
                    product_size=product_size,
                    store=store,
                    defaults={'stock': stock_quantity}
                )
                
                # Track city stock
                if city_id not in city_stocks:
                    city_stocks[city_id] = 0
                city_stocks[city_id] += stock_quantity
            
            # Update product size total stock based on city stocks
            total_stock = sum(city_stocks.values())
            if total_stock > 0:
                product_size.size_general_stock = total_stock
                product_size.save(update_fields=['size_general_stock'])
                
            return True
        except Exception as e:
            logger.error(f"Error processing inventory data: {str(e)}")
            return False
            
    def extract_json_data(self, response):
        """Extract product JSON data from the response"""
        try:
            script_tags = re.findall(r'<script[^>]*>(.*?)</script>', response.text, re.DOTALL)
            
            for script in script_tags:
                try:
                    pattern = r'cartOperationViewModel\s*=\s*({.*?});'
                    match = re.search(pattern, script, re.DOTALL)
                    if match:
                        json_str = match.group(1).strip()
                        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                        json_str = re.sub(r',\s*}', '}', json_str)
                        json_str = re.sub(r',\s*]', ']', json_str)
                        
                        return json.loads(json_str)
                except Exception as e:
                    logger.error(f"JSON parsing error: {str(e)}")
                    continue
            
            logger.warning(f"No valid JSON data found in response")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting JSON data: {str(e)}")
            return None
        
    def extract_product_data(self, response):
        """Extract all product data from the response"""
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            json_data = self.extract_json_data(response)
            product_url = response.url
            
            # Extract basic product information
            product_data = {
                'url': product_url,
                'title': soup.select_one('h1.product-title').text.strip() if soup.select_one('h1.product-title') else None,
                'category': None,  # To be extracted from breadcrumbs
                'price': None,
                'discount_ratio': None,
                'in_stock': False,
                'images': [],
                'status': 'active'
            }
            
            # Extract product code
            product_code_elem = soup.select_one('.product-code')
            if product_code_elem:
                product_code_text = product_code_elem.text.strip()
                product_code_match = re.search(r'([A-Z0-9]+)', product_code_text)
                if product_code_match:
                    product_data['product_code'] = product_code_match.group(1)
            
            # Extract color
            color_elem = soup.select_one('.selected-color')
            if color_elem:
                product_data['color'] = color_elem.text.strip()
            
            # Extract price information
            price_elem = soup.select_one('.price-regular')
            if price_elem:
                try:
                    price_text = price_elem.text.strip()
                    # Remove TL (Turkish Lira) and any other currency symbols
                    price_text = re.sub(r'[^0-9,.]', '', price_text)
                    # For Turkish format: Replace dots used as thousand separators and commas as decimal points
                    # Handle numbers like 1.299,99 
                    if ',' in price_text:
                        # If comma is used as decimal separator
                        price_text = price_text.replace('.', '') # Remove thousand separators
                        price_text = price_text.replace(',', '.') # Convert comma to dot for decimal
                    
                    product_data['price'] = float(price_text)
                except ValueError as e:
                    logger.warning(f"Could not parse price from '{price_elem.text.strip()}': {str(e)}")
                    # Use a default value as fallback if parsing fails
                    product_data['price'] = 0
            
            # Extract discount ratio
            discount_elem = soup.select_one('.discount-rate')
            if discount_elem:
                discount_text = discount_elem.text.strip()
                discount_match = re.search(r'(\d+)', discount_text)
                if discount_match:
                    product_data['discount_ratio'] = float(discount_match.group(1)) / 100.0
            
            # Extract availability
            product_data['in_stock'] = 'out of stock' not in soup.text.lower()
            
            # Extract images
            image_elems = soup.select('.product-image img')
            for img in image_elems:
                if 'src' in img.attrs:
                    img_url = img['src']
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    product_data['images'].append(img_url)
            
            # Extract description
            description_elem = soup.select_one('#collapseOne')
            if description_elem:
                product_data['description'] = description_elem.decode_contents().strip()
            
            # Extract size information
            sizes = []
            size_elems = soup.select('.size-list .size')
            for size_elem in size_elems:
                size_id = size_elem.get('data-id', '')
                size_name = size_elem.text.strip()
                in_stock = 'disabled' not in size_elem.get('class', [])
                
                sizes.append({
                    'size_id': size_id,
                    'size_name': size_name,
                    'in_stock': in_stock,
                    'size_general_stock': 1 if in_stock else 0  # Default value, will be updated if API data is available
                })
            
            return {
                'product': product_data,
                'sizes': sizes
            }
            
        except Exception as e:
            logger.error(f"Error extracting product data: {str(e)}")
            return None

    def save_product_data(self, product_data):
        """Save product data to database"""
        try:
            with transaction.atomic():
                # Create or update product
                product, created = Product.objects.update_or_create(
                    url=product_data['product']['url'],
                    defaults={
                        'title': product_data['product'].get('title'),
                        'category': product_data['product'].get('category'),
                        'description': product_data['product'].get('description'),
                        'product_code': product_data['product'].get('product_code'),
                        'color': product_data['product'].get('color'),
                        'price': product_data['product'].get('price'),
                        'discount_ratio': product_data['product'].get('discount_ratio'),
                        'in_stock': product_data['product'].get('in_stock', False),
                        'images': product_data['product'].get('images', []),
                        'status': product_data['product'].get('status', 'active')
                    }
                )
                
                # Create or update sizes
                for size_data in product_data['sizes']:
                    size, size_created = ProductSize.objects.update_or_create(
                        product=product,
                        size_name=size_data['size_name'],
                        defaults={
                            'size_id': size_data.get('size_id'),
                            'size_general_stock': size_data.get('size_general_stock', 0),
                            'product_option_size_reference': size_data.get('product_option_size_reference'),
                            'barcode_list': size_data.get('barcode_list', [])
                        }
                    )
                
                return product
                
        except Exception as e:
            logger.error(f"Error saving product data: {str(e)}")
            return None

    def process_product_url(self, url):
        """Process a single product URL"""
        try:
            logger.info(f"Processing product URL: {url}")
            response = self.fetch(url)
            
            if not response:
                logger.error(f"Failed to fetch product URL: {url}")
                return False
                
            # Try to extract JSON data first for better product information
            json_data = self.extract_json_data(response)
            
            # Extract product data from HTML
            product_data = self.extract_product_data(response)
            
            if not product_data:
                logger.error(f"Failed to extract product data from URL: {url}")
                return False
            
            # Use JSON data if available to enrich product information
            if json_data:
                # Enhance product data with JSON information
                if 'ModelName' in json_data:
                    product_data['product']['title'] = json_data['ModelName']
                
                if 'CategoryName' in json_data:
                    product_data['product']['category'] = json_data['CategoryName']
                
                if 'ProductId' in json_data:
                    product_data['product']['product_code'] = json_data['ProductId']
                
                if 'Color' in json_data:
                    product_data['product']['color'] = json_data['Color']
                
                # Update pricing information
                product_prices = json_data.get('ProductPrices', {})
                if product_prices:
                    if 'Price' in product_prices:
                        product_data['product']['price'] = float(product_prices['Price'] or 0)
                    if 'DiscountRatio' in product_prices:
                        product_data['product']['discount_ratio'] = float(product_prices['DiscountRatio'] or 0) / 100
                
                # Add size and stock information
                if 'ProductSizes' in json_data and json_data['ProductSizes']:
                    # Reset sizes array with more accurate data
                    product_data['sizes'] = []
                    
                    for size_info in json_data['ProductSizes']:
                        size_obj = {
                            'size_name': size_info.get('Size', {}).get('Value', ''),
                            'size_id': size_info.get('Size', {}).get('SizeId', ''),
                            'size_general_stock': size_info.get('Stock', 0),
                            'product_option_size_reference': size_info.get('UrunOptionSizeRef', ''),
                            'barcode_list': size_info.get('BarcodeList', []),
                            'in_stock': size_info.get('Stock', 0) > 0
                        }
                        product_data['sizes'].append(size_obj)
            
            # Save the product data
            product = self.save_product_data(product_data)
            
            if not product:
                logger.error(f"Failed to save product data for URL: {url}")
                return False
            
            # Check if we need to fetch inventory data for sizes
            if self.config and self.config.use_stores:
                try:
                    # Fetch inventory data for each size with stock
                    for size_data in product_data['sizes']:
                        if size_data.get('in_stock') and size_data.get('product_option_size_reference'):
                            # Get ProductSize object
                            product_size = ProductSize.objects.filter(
                                product=product,
                                size_name=size_data['size_name']
                            ).first()
                            
                            if product_size:
                                # Fetch inventory data for this size
                                inventory_data = self.fetch_inventory(
                                    product_option_size_ref=size_data['product_option_size_reference'],
                                    referer_url=url
                                )
                                
                                if inventory_data:
                                    # Process inventory data to update city and store stock
                                    self.process_inventory_data(product_size, inventory_data)
                except Exception as e:
                    logger.error(f"Error fetching inventory data for {url}: {str(e)}")
                    # Continue processing even if inventory fetch fails
            
            logger.info(f"Successfully processed product URL: {url}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing product URL {url}: {str(e)}")
            return False

    def process_available_urls(self, batch_size=10, max_urls=None):
        """Process available product URLs from ProductAvailableUrl model"""
        try:
            # Get available URLs
            query = ProductAvailableUrl.objects.all().order_by('-last_checking')
            
            if max_urls:
                query = query[:max_urls]
                
            total_urls = query.count()
            logger.info(f"Processing {total_urls} available product URLs")
            
            success_count = 0
            error_count = 0
            
            # Process in batches to avoid overwhelming resources
            for i in range(0, total_urls, batch_size):
                batch = query[i:i+batch_size]
                
                with ThreadPoolExecutor(max_workers=min(5, batch_size)) as executor:
                    results = list(executor.map(
                        lambda url_obj: self.process_product_url(url_obj.url),
                        batch
                    ))
                
                batch_success = results.count(True)
                batch_errors = results.count(False)
                
                success_count += batch_success
                error_count += batch_errors
                
                logger.info(f"Batch {i//batch_size + 1}: {batch_success} successful, {batch_errors} errors")
                
                # Add a small delay between batches
                time.sleep(2)
            
            logger.info(f"Completed processing {total_urls} URLs: {success_count} successful, {error_count} errors")
            return success_count, error_count
            
        except Exception as e:
            logger.error(f"Error processing available URLs: {str(e)}")
            return 0, 0

    def run_scheduled_update(self):
        """Run a scheduled update of product data"""
        logger.info("Starting scheduled product data update")
        try:
            # Process available URLs
            success_count, error_count = self.process_available_urls()
            
            # Check for deleted products
            self.check_for_deleted_products()
            
            logger.info(f"Scheduled update completed: {success_count} products updated, {error_count} errors")
            return success_count
            
        except Exception as e:
            logger.error(f"Error during scheduled update: {str(e)}")
            return 0

    def check_for_deleted_products(self):
        """Check for products that have been deleted"""
        try:
            # Get all deleted URLs
            deleted_urls = ProductDeletedUrl.objects.values_list('url', flat=True)
            
            # Find products that match deleted URLs
            deleted_products = Product.objects.filter(url__in=deleted_urls)
            
            # Mark products as deleted
            count = deleted_products.update(status='deleted')
            
            logger.info(f"Marked {count} products as deleted")
            return count
            
        except Exception as e:
            logger.error(f"Error checking for deleted products: {str(e)}")
            return 0