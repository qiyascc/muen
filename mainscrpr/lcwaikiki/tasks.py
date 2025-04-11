import logging
import json
import re
import time
import random
import requests
import xml.etree.ElementTree as ET
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import (
    Product, ProductSize, City, Store, SizeStoreStock
)

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
        self.max_retries = 5
        self.retry_delay = 5

    def _get_random_proxy(self):
        """Get a random proxy from settings"""
        if not settings.PROXY_LIST:
            return None
        return random.choice(settings.PROXY_LIST)

    def _get_headers(self):
        """Generate request headers with random user agent"""
        user_agent = random.choice(self.USER_AGENTS)
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.lcw.com/',
            'User-Agent': user_agent,
        }

    def fetch(self, url, max_proxy_attempts=None):
        """Fetch URL content with retry and proxy rotation logic"""
        if max_proxy_attempts is None:
            max_proxy_attempts = len(settings.PROXY_LIST) if settings.PROXY_LIST else 1

        proxy_attempts = 0
        proxies_tried = set()

        while proxy_attempts < max_proxy_attempts:
            # Get a proxy that hasn't been tried yet if possible
            available_proxies = [p for p in settings.PROXY_LIST if p not in proxies_tried] if settings.PROXY_LIST else [None]
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

    def post(self, url, data, headers=None, max_proxy_attempts=None):
        """POST request with retry and proxy rotation logic"""
        if max_proxy_attempts is None:
            max_proxy_attempts = len(settings.PROXY_LIST) if settings.PROXY_LIST else 1

        proxy_attempts = 0
        proxies_tried = set()

        while proxy_attempts < max_proxy_attempts:
            # Get a proxy that hasn't been tried yet if possible
            available_proxies = [p for p in settings.PROXY_LIST if p not in proxies_tried] if settings.PROXY_LIST else [None]
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

    def get_meta_content(self, meta_tags, name):
        """Extract content from meta tags"""
        for tag in meta_tags:
            name_match = re.search(r'name=["\']?([^"\'>\s]+)', tag, re.IGNORECASE)
            property_match = re.search(r'property=["\']?([^"\'>\s]+)', tag, re.IGNORECASE)
            content_match = re.search(r'content=["\']?([^"\'>]+)', tag, re.IGNORECASE)

            tag_name = name_match.group(1) if name_match else property_match.group(1) if property_match else None
            content = content_match.group(1) if content_match else ''

            if tag_name == name:
                return content
        return ''

    def extract_description(self, html_content):
        """Extract product description from HTML with XPath"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # This is an approximation of XPath: /html/body/div[3]/div/div[4]/div[1]/div[2]/div[2]/div[2]/div[6]/div/div/div/div[1]/div[2]
            # We'll use CSS selectors instead, but with a fallback approach to find the product description

            # First attempt: Try to find by specific class names commonly used for product descriptions
            description_div = soup.select_one('#collapseOne > div')

            # If not found, try broader approach
            if not description_div:
                main_content = soup.select_one('.product-detail-container, .product-details, .product-content')
                if main_content:
                    # Look for description section within main content
                    description_div = main_content.select_one('div.detail-desc, div.description, div.product-description')

            # If still not found, fall back to generic approach based on content structure
            if not description_div:
                for div in soup.select('div.row div.col div'):
                    if len(div.find_all('p')) > 0 or len(div.get_text().strip()) > 100:
                        # This might be the description if it has paragraphs or substantial text
                        description_div = div
                        break

            if description_div:
                # Remove the first h5 tag inside description_div, if it exists
                h5_tag = description_div.find('h5')
                if h5_tag:
                    h5_tag.decompose()

                # Remove all p tags that contain "Satıcı:" or "Marka:"
                for p_tag in description_div.find_all('p'):
                    if "Satıcı:" in p_tag.get_text() or "Marka:" in p_tag.get_text():
                        p_tag.decompose()

                # Return HTML content as string
                return str(description_div)
            else:
                logger.warning("Product description div not found")
                return ""

        except Exception as e:
            logger.error(f"Error extracting product description: {str(e)}")
            return ""

    def parse_product(self, response):
        """Parse product data from response"""
        try:
            product_url = response.url

            json_data = self.extract_json_data(response)
            meta_tags = re.findall(r'<meta\s+([^>]+)>', response.text, re.IGNORECASE)
            if not json_data:
                logger.error(f"No JSON data found for {product_url}")
                return None

            product_sizes = json_data.get('ProductSizes', [])
            price = float(str(json_data.get('ProductPrices', {}).get('Price', '0')).replace(' TL', '').replace(',', '.').strip() or 0)
            product_code = self.get_meta_content(meta_tags, 'ProductCodeColorCode')

            # Extract description from HTML using the provided XPath equivalent
            from config.utils import apply_price_configuration
            price = apply_price_configuration(price)
            description = self.extract_description(response.text)

            product_data = {
                "url": product_url,
                "title": json_data.get('PageTitle', ''),
                "category": json_data.get('CategoryName', ''),
                "description": description,
                "product_code": product_code, 
                "color": json_data.get('Color', ''),
                "price": price,
                "discount_ratio": json_data.get('ProductPrices', {}).get('DiscountRatio', 0),
                "in_stock": json_data.get('IsInStock', False),
                "images": [
                    img_url for pic in json_data.get('Pictures', [])
                    for img_size in ['ExtraMedium600', 'ExtraMedium800', 'MediumImage', 'SmallImage']
                    if (img_url := pic.get(img_size))
                ],
                "status": "success",
                "sizes": []
            }

            for size in product_sizes:
                size_info = {
                    "size_name": size.get('Size', {}).get('Value', ''),
                    "size_id": size.get('Size', {}).get('SizeId', ''),
                    "size_general_stock": size.get('Stock', 0),
                    "product_option_size_reference": size.get('UrunOptionSizeRef', 0),
                    "barcode_list": size.get('BarcodeList', []),
                    "city_stock": {}
                }

                # Get inventory data if there's stock
                if size_info['size_general_stock'] > 0:
                    inventory_data = self.get_inventory(product_url, size_info['product_option_size_reference'])
                    if inventory_data:
                        city_stock = {}
                        for store in inventory_data.get('storeInventoryInfos', []):
                            city_id = str(store.get('StoreCityId'))
                            city_name = store.get('StoreCityName')

                            if city_id not in city_stock:
                                city_stock[city_id] = {
                                    "name": city_name,
                                    "stock": 0,
                                    "stores": []
                                }

                            store_info = {
                                "store_code": store.get('StoreCode', ''),
                                "store_name": store.get('StoreName', ''),
                                "store_address": {
                                    "location_with_words": store.get('Address', ''),
                                    "location_with_coordinants": [
                                        store.get('Lattitude', ''),
                                        store.get('Longitude', '')
                                    ]
                                },
                                "store_phone": store.get('StorePhone', ''),
                                "store_county": store.get('StoreCountyName', ''),
                                "stock": store.get('Quantity', 0)
                            }

                            city_stock[city_id]['stores'].append(store_info)
                            city_stock[city_id]['stock'] += store.get('Quantity', 0)

                        size_info['city_stock'] = city_stock

                product_data['sizes'].append(size_info)

            return product_data

        except Exception as e:
            logger.error(f"Error parsing product {response.url}: {str(e)}")
            return None

    def get_inventory(self, product_url, product_option_size_reference):
        """Get inventory data for a specific size"""
        try:
            response = self.post(
                url=self.INVENTORY_API_URL,
                data={
                    "cityId": self.DEFAULT_CITY_ID,
                    "countyIds": [],
                    "urunOptionSizeRef": str(product_option_size_reference)
                },
                headers={
                    'Content-Type': 'application/json',
                    'Referer': product_url
                }
            )

            if response and response.status_code == 200:
                return json.loads(response.text)

            return None

        except Exception as e:
            logger.error(f"Error getting inventory data: {str(e)}")
            return None

def fetch_sitemap_urls():
    """Fetch URLs from sitemap API"""
    try:
        sitemap_api_url = f"/api/{settings.CURRENTLY_API_VERSION}/lcwaikiki/product-sitemap/"
        # Get base URL from settings or use a default
        base_url = getattr(settings, 'BASE_API_URL', 'http://localhost:8000')

        full_url = f"{base_url.rstrip('/')}{sitemap_api_url}"
        logger.info(f"Fetching sitemap URLs from: {full_url}")

        response = requests.get(full_url)
        if response.status_code == 200:
            data = response.json()
            return data.get('urls', [])
        else:
            logger.error(f"Failed to fetch sitemap URLs: HTTP {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching sitemap URLs: {str(e)}")
        return []


def fetch_product_urls():
    """Fetch available product URLs from the API"""
    try:
        product_urls_api = f"/api/lcwaikiki/product/urls/available/"
        # Get base URL from settings or use a default
        base_url = getattr(settings, 'BASE_API_URL', 'http://localhost:8000')

        full_url = f"{base_url.rstrip('/')}{product_urls_api}"
        logger.info(f"Fetching product URLs from: {full_url}")

        response = requests.get(full_url)
        if response.status_code == 200:
            data = response.json()
            # Extract URLs from the response structure
            return [item['url'] for item in data.get('urls', [])]
        else:
            logger.error(f"Failed to fetch product URLs: HTTP {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching product URLs: {str(e)}")
        return []


def process_product(url, thread_id=0):
    """Process a single product"""
    logger.info(f"Thread {thread_id}: Processing product {url}")

    try:
        # Skip if product already exists and was recently processed
        existing_product = Product.objects.filter(url=url).first()
        if existing_product and (timezone.now() - existing_product.timestamp).days < 1:
            logger.info(f"Thread {thread_id}: Skipping recently processed product {url}")
            return

        scraper = ProductScraper()
        response = scraper.fetch(url)

        if not response:
            logger.error(f"Thread {thread_id}: Failed to fetch product {url}")

            # Update or create product with error status
            with transaction.atomic():
                Product.objects.update_or_create(
                    url=url,
                    defaults={"status": "error"}
                )

            return

        product_data = scraper.parse_product(response)

        if not product_data:
            logger.error(f"Thread {thread_id}: Failed to parse product {url}")

            # Update or create product with error status
            with transaction.atomic():
                Product.objects.update_or_create(
                    url=url,
                    defaults={"status": "error"}
                )

            return

        # Save product data to database
        with transaction.atomic():
            # Create or update product
            product, created = Product.objects.update_or_create(
                url=product_data['url'],
                defaults={
                    "title": product_data['title'],
                    "category": product_data['category'],
                    "description": product_data['description'],
                    "product_code": product_data['product_code'],
                    "color": product_data['color'],
                    "price": product_data['price'],
                    "discount_ratio": product_data['discount_ratio'],
                    "in_stock": product_data['in_stock'],
                    "images": product_data['images'],
                    "status": product_data['status'],
                    "timestamp": timezone.now()
                }
            )

            # Delete existing sizes to avoid duplicates
            if not created:
                ProductSize.objects.filter(product=product).delete()

            # Create sizes
            for size_data in product_data['sizes']:
                product_size = ProductSize.objects.create(
                    product=product,
                    size_name=size_data['size_name'],
                    size_id=size_data['size_id'],
                    size_general_stock=size_data['size_general_stock'],
                    product_option_size_reference=size_data['product_option_size_reference'],
                    barcode_list=size_data['barcode_list']
                )

                # Create city stock data
                for city_id, city_data in size_data.get('city_stock', {}).items():
                    # Create or get city
                    city, _ = City.objects.get_or_create(
                        city_id=city_id,
                        defaults={"name": city_data['name']}
                    )

                    # Create stores and inventory
                    for store_data in city_data['stores']:
                        store, _ = Store.objects.update_or_create(
                            store_code=store_data['store_code'],
                            defaults={
                                "store_name": store_data['store_name'],
                                "city": city,
                                "store_county": store_data['store_county'],
                                "store_phone": store_data['store_phone'],
                                "address": store_data['store_address']['location_with_words'],
                                "latitude": store_data['store_address']['location_with_coordinants'][0],
                                "longitude": store_data['store_address']['location_with_coordinants'][1]
                            }
                        )

                        # Create stock entry
                        from config.utils import apply_stock_configuration
                        original_stock = store_data['stock']
                        mapped_stock = apply_stock_configuration(original_stock)
                        SizeStoreStock.objects.update_or_create(
                            product_size=product_size,
                            store=store,
                            defaults={"stock": mapped_stock}
                        )

        logger.info(f"Thread {thread_id}: Successfully processed product {url}")

    except Exception as e:
        logger.error(f"Thread {thread_id}: Error processing product {url}: {str(e)}")

        # Update or create product with error status
        with transaction.atomic():
            Product.objects.update_or_create(
                url=url,
                defaults={"status": "error"}
            )

def worker_thread(product_queue, thread_id):
    """Worker thread function"""
    while not product_queue.empty():
        try:
            url = product_queue.get(block=False)
            process_product(url, thread_id)
            product_queue.task_done()
        except queue.Empty:
            break
        except Exception as e:
            logger.error(f"Thread {thread_id}: Error in worker thread: {str(e)}")
            product_queue.task_done()

def fetch_product_data():
    """Main function to fetch and update product data"""
    try:
        # Fetch sitemap URLs
        sitemap_urls = fetch_sitemap_urls()

        if not sitemap_urls:
            logger.error("No sitemap URLs available")
            return False

        # Create a queue for product URLs
        product_queue = queue.Queue()

        # Fetch and queue all product URLs
        for sitemap_url_data in sitemap_urls:
            url = sitemap_url_data.get("url")

            if not url:
                continue

            product_urls = fetch_product_urls(url)

            for product_url_data in product_urls:
                product_url = product_url_data.get("url")

                if product_url:
                    product_queue.put(product_url)

        total_products = product_queue.qsize()
        logger.info(f"Queued {total_products} products for processing")

        # Create worker threads
        num_threads = min(5, total_products)
        threads = []

        for i in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(product_queue, i))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        logger.info("Product data fetch completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error fetching product data: {str(e)}")
        return False