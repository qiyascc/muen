import logging
import json
import re
import time
import random
import requests
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.management.base import BaseCommand

from scraper_apps.lcwaikiki.product_api.models import (Product, ProductSize,
                                                       Store, SizeStoreStock,
                                                       ProductAvailableUrl,
                                                       ProductDeletedUrl,
                                                       ProductNewUrl, Config)

logger = logging.getLogger(__name__)


class ProductScraper:
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
    self.config = Config.objects.first()

  def _get_random_proxy(self):
    if not settings.PROXY_LIST:
      return None
    return random.choice(settings.PROXY_LIST)

  def _get_headers(self):
    user_agent = random.choice(self.USER_AGENTS)
    return {
        'Accept':
        'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.lcw.com/',
        'User-Agent': user_agent,
    }

  def _apply_price_configuration(self, price):
    if not price or not self.config or not self.config.price_config:
      return price

    try:
      price = float(price)
      rules = self.config.price_config.get('rules', [])
      default_multiplier = self.config.price_config.get(
          'default_multiplier', 1.8)

      multiplier = default_multiplier
      for rule in rules:
        if 'max_price' in rule and price <= rule['max_price']:
          multiplier = rule['multiplier']
          break
        if 'min_price' in rule and price >= rule['min_price']:
          multiplier = rule['multiplier']
          break

      return round(price * multiplier, 2)
    except Exception as e:
      logger.error(f"Error applying price configuration: {str(e)}")
      return price

  def _apply_stock_configuration(self, stock):
    # You can add stock configuration logic here if needed
    return stock

  def fetch(self, url, max_proxy_attempts=None):
    if max_proxy_attempts is None:
      max_proxy_attempts = len(
          settings.PROXY_LIST) if settings.PROXY_LIST else 1

    proxy_attempts = 0
    proxies_tried = set()

    while proxy_attempts < max_proxy_attempts:
      available_proxies = [
          p for p in settings.PROXY_LIST if p not in proxies_tried
      ] if settings.PROXY_LIST else [None]
      if not available_proxies:
        logger.warning("All proxies have been tried without success")
        break

      proxy = random.choice(available_proxies)
      proxies = {"http": proxy, "https": proxy} if proxy else None

      if proxy:
        proxies_tried.add(proxy)

      self.session.headers.update(self._get_headers())

      logger.info(
          f"Proxy attempt {proxy_attempts + 1}/{max_proxy_attempts}: {proxy}")

      for attempt in range(1, self.max_retries + 1):
        try:
          response = self.session.get(url,
                                      proxies=proxies,
                                      timeout=30,
                                      allow_redirects=True,
                                      verify=True)

          if response.status_code == 200:
            logger.info(f"Successfully fetched {url}")
            return response

          elif response.status_code == 403:
            logger.warning(
                f"Access denied (403) with proxy {proxy}, attempt {attempt}")
            if attempt == self.max_retries:
              break
            time.sleep(self.retry_delay * attempt)

          else:
            logger.warning(
                f"HTTP {response.status_code} with proxy {proxy}, attempt {attempt}"
            )
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
          logger.warning(
              f"Request error with proxy {proxy}, attempt {attempt}: {str(e)}")
          if attempt == self.max_retries:
            break
          time.sleep(self.retry_delay * attempt)

      proxy_attempts += 1

    logger.error("All proxy attempts failed")
    return None

  def post(self, url, data, headers=None, max_proxy_attempts=None):
    if max_proxy_attempts is None:
      max_proxy_attempts = len(
          settings.PROXY_LIST) if settings.PROXY_LIST else 1

    proxy_attempts = 0
    proxies_tried = set()

    while proxy_attempts < max_proxy_attempts:
      available_proxies = [
          p for p in settings.PROXY_LIST if p not in proxies_tried
      ] if settings.PROXY_LIST else [None]
      if not available_proxies:
        logger.warning("All proxies have been tried without success")
        break

      proxy = random.choice(available_proxies)
      proxies = {"http": proxy, "https": proxy} if proxy else None

      if proxy:
        proxies_tried.add(proxy)

      if headers is None:
        headers = {}
      headers.update(self._get_headers())

      logger.info(
          f"Proxy attempt {proxy_attempts + 1}/{max_proxy_attempts}: {proxy}")

      for attempt in range(1, self.max_retries + 1):
        try:
          response = self.session.post(url,
                                       json=data,
                                       headers=headers,
                                       proxies=proxies,
                                       timeout=30,
                                       allow_redirects=True,
                                       verify=True)

          if response.status_code == 200:
            logger.info(f"Successfully posted to {url}")
            return response

          elif response.status_code == 403:
            logger.warning(
                f"Access denied (403) with proxy {proxy}, attempt {attempt}")
            if attempt == self.max_retries:
              break
            time.sleep(self.retry_delay * attempt)

          else:
            logger.warning(
                f"HTTP {response.status_code} with proxy {proxy}, attempt {attempt}"
            )
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
          logger.warning(
              f"Request error with proxy {proxy}, attempt {attempt}: {str(e)}")
          if attempt == self.max_retries:
            break
          time.sleep(self.retry_delay * attempt)

      proxy_attempts += 1

    logger.error("All proxy attempts failed")
    return None

  def extract_json_data(self, response):
    try:
      script_tags = re.findall(r'<script[^>]*>(.*?)</script>', response.text,
                               re.DOTALL)

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
    for tag in meta_tags:
      name_match = re.search(r'name=["\']?([^"\'>\s]+)', tag, re.IGNORECASE)
      property_match = re.search(r'property=["\']?([^"\'>\s]+)', tag,
                                 re.IGNORECASE)
      content_match = re.search(r'content=["\']?([^"\'>]+)', tag,
                                re.IGNORECASE)

      tag_name = name_match.group(1) if name_match else property_match.group(
          1) if property_match else None
      content = content_match.group(1) if content_match else ''

      if tag_name == name:
        return content
    return ''

  def extract_description(self, html_content):
    try:
      soup = BeautifulSoup(html_content, 'html.parser')
      description_div = soup.select_one('#collapseOne > div')

      if not description_div:
        main_content = soup.select_one(
            '.product-detail-container, .product-details, .product-content')
        if main_content:
          description_div = main_content.select_one(
              'div.detail-desc, div.description, div.product-description')

      if not description_div:
        for div in soup.select('div.row div.col div'):
          if len(div.find_all('p')) > 0 or len(div.get_text().strip()) > 100:
            description_div = div
            break

      if description_div:
        h5_tag = description_div.find('h5')
        if h5_tag:
          h5_tag.decompose()

        for p_tag in description_div.find_all('p'):
          if "Satıcı:" in p_tag.get_text() or "Marka:" in p_tag.get_text():
            p_tag.decompose()

        return str(description_div)
      else:
        logger.warning("Product description div not found")
        return ""

    except Exception as e:
      logger.error(f"Error extracting product description: {str(e)}")
      return ""

  def parse_product(self, response):
    try:
      product_url = response.url

      json_data = self.extract_json_data(response)
      meta_tags = re.findall(r'<meta\s+([^>]+)>', response.text, re.IGNORECASE)
      if not json_data:
        logger.error(f"No JSON data found for {product_url}")
        return None

      product_sizes = json_data.get('ProductSizes', [])
      original_price = float(
          str(json_data.get('ProductPrices', {}).get('Price', '0')).replace(
              ' TL', '').replace(',', '.').strip() or 0)
      price = self._apply_price_configuration(original_price)
      product_code = self.get_meta_content(meta_tags, 'ProductCodeColorCode')
      description = self.extract_description(response.text)

      product_data = {
          "url":
          product_url,
          "title":
          json_data.get('PageTitle', ''),
          "category":
          json_data.get('CategoryName', ''),
          "description":
          description,
          "product_code":
          product_code,
          "color":
          json_data.get('Color', ''),
          "original_price":
          original_price,
          "price":
          price,
          "discount_ratio":
          json_data.get('ProductPrices', {}).get('DiscountRatio', 0),
          "in_stock":
          json_data.get('IsInStock', False),
          "images": [
              img_url for pic in json_data.get('Pictures', [])
              for img_size in [
                  'ExtraMedium600', 'ExtraMedium800', 'MediumImage',
                  'SmallImage'
              ] if (img_url := pic.get(img_size))
          ],
          "status":
          "success",
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

        if size_info['size_general_stock'] > 0:
          inventory_data = self.get_inventory(
              product_url, size_info['product_option_size_reference'])
          if inventory_data:
            city_stock = {}
            for store in inventory_data.get('storeInventoryInfos', []):
              city_id = str(store.get('StoreCityId'))

              store_info = {
                  "store_code": store.get('StoreCode', ''),
                  "store_name": store.get('StoreName', ''),
                  "store_address": {
                      "location_with_words":
                      store.get('Address', ''),
                      "location_with_coordinants":
                      [store.get('Lattitude', ''),
                       store.get('Longitude', '')]
                  },
                  "store_phone": store.get('StorePhone', ''),
                  "store_county": store.get('StoreCountyName', ''),
                  "stock": store.get('Quantity', 0)
              }

              city_stock[city_id] = city_stock.get(
                  city_id, {
                      "name": store.get('StoreCityName', ''),
                      "stock": 0,
                      "stores": []
                  })

              city_stock[city_id]['stores'].append(store_info)
              city_stock[city_id]['stock'] += store.get('Quantity', 0)

            size_info['city_stock'] = city_stock

        product_data['sizes'].append(size_info)

      return product_data

    except Exception as e:
      logger.error(f"Error parsing product {response.url}: {str(e)}")
      return None

  def get_inventory(self, product_url, product_option_size_reference):
    try:
      response = self.post(url=self.INVENTORY_API_URL,
                           data={
                               "cityId":
                               self.DEFAULT_CITY_ID,
                               "countyIds": [],
                               "urunOptionSizeRef":
                               str(product_option_size_reference)
                           },
                           headers={
                               'Content-Type': 'application/json',
                               'Referer': product_url
                           })

      if response and response.status_code == 200:
        return json.loads(response.text)

      return None

    except Exception as e:
      logger.error(f"Error getting inventory data: {str(e)}")
      return None


class Command(BaseCommand):
  help = 'Refresh product data from LC Waikiki'

  def handle(self, *args, **options):
    self.stdout.write(self.style.SUCCESS('Starting product data refresh...'))
    success = self.fetch_product_data()
    if success:
      self.stdout.write(
          self.style.SUCCESS('Product data refresh completed successfully'))
    else:
      self.stdout.write(self.style.ERROR('Product data refresh failed'))

  def fetch_available_urls(self):
    """Fetch available product URLs from API"""
    try:
      api_url = "https://5d5f0d6a-7ad1-460e-bcb2-7db84ebc77ff-00-30mgnzeqj65wp.kirk.replit.dev/api/lcwaikiki/product/urls/available/"
      response = requests.get(api_url)

      if response.status_code == 200:
        data = response.json()
        return data.get('urls', [])
      else:
        logger.error(
            f"Failed to fetch available URLs: HTTP {response.status_code}")
        return []
    except Exception as e:
      logger.error(f"Error fetching available URLs: {str(e)}")
      return []

  def process_product(self, url, thread_id=0):
    """Process a single product"""
    logger.info(f"Thread {thread_id}: Processing product {url}")

    try:
      existing_product = Product.objects.filter(url=url).first()
      if existing_product and (timezone.now() - existing_product.last_checking
                               ).total_seconds() < 3600:
        logger.info(
            f"Thread {thread_id}: Skipping recently checked product {url}")
        return

      scraper = ProductScraper()
      response = scraper.fetch(url)

      if not response:
        logger.error(f"Thread {thread_id}: Failed to fetch product {url}")
        Product.objects.update_or_create(url=url,
                                         defaults={
                                             "status": "error",
                                             "last_checking": timezone.now()
                                         })
        return

      product_data = scraper.parse_product(response)

      if not product_data:
        logger.error(f"Thread {thread_id}: Failed to parse product {url}")
        Product.objects.update_or_create(url=url,
                                         defaults={
                                             "status": "error",
                                             "last_checking": timezone.now()
                                         })
        return

      with transaction.atomic():
        product, created = Product.objects.update_or_create(
            url=product_data['url'],
            defaults={
                "title": product_data['title'],
                "category": product_data['category'],
                "description": product_data['description'],
                "product_code": product_data['product_code'],
                "color": product_data['color'],
                "original_price": product_data['original_price'],
                "price": product_data['price'],
                "discount_ratio": product_data['discount_ratio'],
                "in_stock": product_data['in_stock'],
                "images": product_data['images'],
                "status": product_data['status'],
                "last_checking": timezone.now()
            })

        if not created:
          ProductSize.objects.filter(product=product).delete()

        for size_data in product_data['sizes']:
          product_size = ProductSize.objects.create(
              product=product,
              size_name=size_data['size_name'],
              size_id=size_data['size_id'],
              size_general_stock=size_data['size_general_stock'],
              product_option_size_reference=size_data[
                  'product_option_size_reference'],
              barcode_list=size_data['barcode_list'])

          for city_id, city_data in size_data.get('city_stock', {}).items():
            for store_data in city_data['stores']:
              store, _ = Store.objects.update_or_create(
                  store_code=store_data['store_code'],
                  defaults={
                      "store_name":
                      store_data['store_name'],
                      "city_id":
                      city_id,
                      "store_county":
                      store_data['store_county'],
                      "store_phone":
                      store_data['store_phone'],
                      "address":
                      store_data['store_address']['location_with_words'],
                      "latitude":
                      store_data['store_address']['location_with_coordinants']
                      [0],
                      "longitude":
                      store_data['store_address']['location_with_coordinants']
                      [1]
                  })

              original_stock = store_data['stock']
              mapped_stock = scraper._apply_stock_configuration(original_stock)
              SizeStoreStock.objects.update_or_create(
                  product_size=product_size,
                  store=store,
                  defaults={
                      "original_stock": original_stock,
                      "stock": mapped_stock
                  })

      logger.info(f"Thread {thread_id}: Successfully processed product {url}")

    except Exception as e:
      logger.error(
          f"Thread {thread_id}: Error processing product {url}: {str(e)}")
      Product.objects.update_or_create(url=url,
                                       defaults={
                                           "status": "error",
                                           "last_checking": timezone.now()
                                       })

  def worker_thread(self, product_queue, thread_id):
    """Worker thread function"""
    while not product_queue.empty():
      try:
        url = product_queue.get(block=False)
        self.process_product(url, thread_id)
        product_queue.task_done()
      except queue.Empty:
        break
      except Exception as e:
        logger.error(f"Thread {thread_id}: Error in worker thread: {str(e)}")
        product_queue.task_done()

  def fetch_product_data(self):
    """Main function to fetch and update product data"""
    try:
      available_urls = self.fetch_available_urls()

      if not available_urls:
        logger.error("No available product URLs found")
        return False

      product_queue = queue.Queue()
      for url_data in available_urls:
        product_queue.put(url_data['url'])

      total_products = product_queue.qsize()
      logger.info(f"Queued {total_products} products for processing")

      num_threads = min(5, total_products)
      threads = []

      for i in range(num_threads):
        thread = threading.Thread(target=self.worker_thread,
                                  args=(product_queue, i))
        threads.append(thread)
        thread.start()

      for thread in threads:
        thread.join()

      logger.info("Product data fetch completed successfully")
      return True

    except Exception as e:
      logger.error(f"Error fetching product data: {str(e)}")
      return False
