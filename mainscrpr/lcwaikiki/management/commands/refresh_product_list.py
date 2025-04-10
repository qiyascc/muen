import os
import signal
import sys
import json
import re
import math
import time
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from tqdm.auto import tqdm
from loguru import logger

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from lcwaikiki.models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl

# ---------------------------- Config ---------------------------- #
class ScraperConfig:
    BASE_URL = "https://www.lcw.com"
    API_BASE_URL = "https://5d5f0d6a-7ad1-460e-bcb2-7db84ebc77ff-00-30mgnzeqj65wp.kirk.replit.dev"
    BRANDS_ENDPOINT = "/api/v1/lcwaikiki/config/brands/"
    AVAILABLE_URLS_ENDPOINT = "/api/lcwaikiki/product/urls/available/"
    NEW_URLS_ENDPOINT = "/api/lcwaikiki/product/urls/new/"
    DELETED_URLS_ENDPOINT = "/api/lcwaikiki/product/urls/deleted/"
    MAX_WORKERS = 12
    REQUEST_TIMEOUT = 20
    RETRY_STRATEGY = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['GET']
    )
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    DATA_FILE = 'products.json'
    CHECKPOINT_FILE = '.scraper_state'
    CHECKPOINT_INTERVAL = 3

# ---------------------------- Extra Tools ---------------------------- #
class ScraperUtils:
    @staticmethod
    def setup_logging():
        logger.remove()
        # Log to stderr
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
            level="INFO",
            colorize=True
        )
        
        # Also log to file for dashboard display
        os.makedirs('logs', exist_ok=True)
        logger.add(
            'logs/scraper.log',
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            level="INFO",
            rotation="10 MB",  # Rotate when file reaches 10MB
            retention="1 week"  # Keep logs for 1 week
        )

    @staticmethod
    def retry_on_failure(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(3):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1} failed: {str(e)}")
                    time.sleep(2 ** attempt)
            raise Exception(f"All attempts failed for {func.__name__}")
        return wrapper

# ---------------------------- API Manager ---------------------------- #
class APIManager:
    def __init__(self):
        self.session = RequestSession()
    
    @ScraperUtils.retry_on_failure
    def get_brands(self) -> List[str]:
        # Get brands from Django database instead of API
        try:
            config = Config.objects.first()
            if config and config.brands:
                return config.brands
        except Exception as e:
            logger.error(f"Error getting brands from database: {str(e)}")
        
        # Fallback to API if database access fails
        url = f"{ScraperConfig.API_BASE_URL}{ScraperConfig.BRANDS_ENDPOINT}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('brands', [])

    @ScraperUtils.retry_on_failure
    def get_available_urls(self) -> List[Dict]:
        # Get available URLs from Django database
        try:
            available_urls = ProductAvailableUrl.objects.all()
            return [{
                'page_id': item.page_id,
                'product_id_in_page': item.product_id_in_page,
                'url': item.url,
                'last_checking': item.last_checking.strftime('%Y-%m-%dT%H:%M:%SZ')
            } for item in available_urls]
        except Exception as e:
            logger.error(f"Error getting available URLs from database: {str(e)}")
            return []

    @ScraperUtils.retry_on_failure
    def post_available_urls(self, urls: List[Dict]):
        # Save available URLs to Django database in batches
        current_time = timezone.now()
        batch_size = 100
        total_processed = 0
        
        try:
            # Process in batches to avoid database locking
            for i in range(0, len(urls), batch_size):
                batch = urls[i:i+batch_size]
                
                # Create new entries
                for url_data in batch:
                    ProductAvailableUrl.objects.update_or_create(
                        page_id=url_data['page_id'],
                        product_id_in_page=url_data['product_id_in_page'],
                        defaults={
                            'url': url_data['url'],
                            'last_checking': current_time
                        }
                    )
                
                total_processed += len(batch)
                logger.info(f"Processed batch {i//batch_size + 1}: {total_processed}/{len(urls)} available URLs")
                
                # Add a small delay between batches to prevent database locking
                time.sleep(0.5)
                
            logger.success(f"Updated {total_processed} available URLs in database")
        except Exception as e:
            logger.error(f"Error saving available URLs to database: {str(e)}")

    @ScraperUtils.retry_on_failure
    def post_new_urls(self, new_urls: List[Dict]):
        # Save new URLs to Django database
        current_time = timezone.now()
        batch_size = 100
        total_processed = 0
        
        try:
            # Process in batches
            for i in range(0, len(new_urls), batch_size):
                batch = new_urls[i:i+batch_size]
                
                # Check and prepare batch
                bulk_new_urls = []
                for url_data in batch:
                    # Check if it doesn't already exist
                    if not ProductNewUrl.objects.filter(url=url_data['url']).exists():
                        bulk_new_urls.append(ProductNewUrl(
                            url=url_data['url'],
                            last_checking=current_time
                        ))
                
                # Create batch
                if bulk_new_urls:
                    ProductNewUrl.objects.bulk_create(bulk_new_urls)
                    total_processed += len(bulk_new_urls)
                    logger.info(f"Processed batch {i//batch_size + 1}: {total_processed} new URLs")
                
                # Add delay between batches
                time.sleep(0.5)
            
            if total_processed > 0:
                logger.success(f"Added {total_processed} new URLs to database")
        except Exception as e:
            logger.error(f"Error saving new URLs to database: {str(e)}")

    @ScraperUtils.retry_on_failure
    def post_deleted_urls(self, deleted_urls: List[Dict]):
        # Save deleted URLs to Django database
        current_time = timezone.now()
        batch_size = 100
        total_processed = 0
        
        try:
            # Process in batches
            for i in range(0, len(deleted_urls), batch_size):
                batch = deleted_urls[i:i+batch_size]
                
                # Check and prepare batch
                bulk_deleted_urls = []
                for url_data in batch:
                    # Check if it doesn't already exist
                    if not ProductDeletedUrl.objects.filter(url=url_data['url']).exists():
                        bulk_deleted_urls.append(ProductDeletedUrl(
                            url=url_data['url'],
                            last_checking=current_time
                        ))
                
                # Create batch
                if bulk_deleted_urls:
                    ProductDeletedUrl.objects.bulk_create(bulk_deleted_urls)
                    total_processed += len(bulk_deleted_urls)
                    logger.info(f"Processed batch {i//batch_size + 1}: {total_processed} deleted URLs")
                
                # Add delay between batches
                time.sleep(0.5)
            
            if total_processed > 0:
                logger.success(f"Added {total_processed} deleted URLs to database")
        except Exception as e:
            logger.error(f"Error saving deleted URLs to database: {str(e)}")

# ---------------------------- Session Management ---------------------------- #
class RequestSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.mount(
            'https://',
            HTTPAdapter(
                max_retries=ScraperConfig.RETRY_STRATEGY,
                pool_maxsize=ScraperConfig.MAX_WORKERS*2
            )
        )
        self.session.headers.update(ScraperConfig.HEADERS)

    @ScraperUtils.retry_on_failure
    def get(self, url: str) -> requests.Response:
        response = self.session.get(
            url, 
            timeout=ScraperConfig.REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response

# ---------------------------- Data Management ---------------------------- #
class DataManager:
    def __init__(self):
        self.data_file = ScraperConfig.DATA_FILE
        self.checkpoint_file = ScraperConfig.CHECKPOINT_FILE
        self._processed_urls: Set[str] = set()
        self._completed_pages: Set[int] = set()
        self._products: List[Dict] = []
        self._load_state()

    def _load_state(self):
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r') as f:
                    state = json.load(f)
                    self._completed_pages = set(state['completed_pages'])
                    self._processed_urls = set(state['processed_urls'])
        except Exception as e:
            logger.error(f"State load error: {str(e)}")

    def save_checkpoint(self):
        state = {
            'completed_pages': list(self._completed_pages),
            'processed_urls': list(self._processed_urls),
        }
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(state, f)
            self._save_products()
        except Exception as e:
            logger.error(f"Checkpoint save error: {str(e)}")

    def _save_products(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self._products, f, ensure_ascii=False, indent=2)

    def add_products(self, page: int, products: List[Dict]):
        new_products = []
        for product in products:
            if product['url'] not in self._processed_urls:
                self._processed_urls.add(product['url'])
                new_products.append(product)
        
        self._products.extend(new_products)
        self._completed_pages.add(page)
        logger.debug(f"Page {page} processed: {len(new_products)} new products")

# ---------------------------- Main Scraper Class ---------------------------- #
class ProductScraper:
    def __init__(self):
        self.session = RequestSession()
        self.data_manager = DataManager()
        self.total_pages = 0
        self._stop_requested = False
        self.brands = []
        self._setup_signal_handlers()
        self._get_brands()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._graceful_shutdown)
        signal.signal(signal.SIGTERM, self._graceful_shutdown)

    def _graceful_shutdown(self, signum, frame):
        logger.info("Initiating graceful shutdown...")
        self._stop_requested = True

    def _get_brands(self):
        api_manager = APIManager()
        try:
            self.brands = api_manager.get_brands()
            logger.success(f"Database'den {len(self.brands)} marka alındı")
        except Exception as e:
            logger.error(f"Marka listesi alınamadı: {str(e)}")
            self.brands = [
                'lcwaikiki-classic', 'lcw-modest', 'lcwaikiki-basic',
                'lcw-casual', 'lcw-vision', 'xside-active', 'lcw-dream',
                'lcwaikiki-maternity', 'lcw-grace', 'lcw-limited', 'xside',
                'lcw-jeans', 'lcwaikiki-formal', 'lcw-outdoor', 'lcw-baby',
                'lc-waikiki', 'lcw-accessories', 'lcw-comfort', 'lcw-eco',
                'lcw-home', 'lcw-kids', 'lcw-limitless', 'lcw-swimwear', 'lcw-teen'
            ]
            logger.warning("Fallback marka listesi kullanılıyor")

    def _extract_product_count(self, soup: BeautifulSoup) -> Optional[int]:
        try:
            count_element = soup.find('span', {'class': 'product-list-heading__product-count'})
            if count_element:
                count_text = count_element.find('p').get_text(strip=True)
                return int(re.search(r'\d+', count_text.replace('.', '')).group())
        except Exception as e:
            logger.warning(f"Product count extraction error: {str(e)}")
        return None

    def _extract_per_page(self, soup: BeautifulSoup) -> Optional[int]:
        try:
            pagination_info = soup.find('div', {'class': 'paginator__info-text'})
            if pagination_info:
                per_page_text = pagination_info.find(
                    'span', {'class': 'paginator__info-text-viewed-products'}
                ).get_text(strip=True)
                return int(per_page_text)
        except Exception as e:
            logger.warning(f"Items per page extraction error: {str(e)}")
        return None

    def get_total_pages(self) -> int:
        if not self.brands:
            logger.error("Marka listesi boş, sayfa hesaplanamıyor")
            return 0
            
        url = f"{ScraperConfig.BASE_URL}/giyim-u-300009?marka={','.join(self.brands)}"
        
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            product_count = self._extract_product_count(soup) or 38400
            per_page = self._extract_per_page(soup) or 96

            total_pages = math.ceil(product_count / per_page)
            logger.info(f"Product count: {product_count} | Per page: {per_page} | Total pages: {total_pages}")
            return total_pages
            
        except Exception as e:
            logger.error(f"Page calculation error: {str(e)}")
            return math.ceil(38400 / 96)

    def scrape_page(self, page: int) -> List[Dict]:
        if page in self.data_manager._completed_pages or self._stop_requested:
            return []

        url = f"{ScraperConfig.BASE_URL}/giyim-u-300009?marka={','.join(self.brands)}&page={page}"
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            products = []
            
            for position, product_card in enumerate(soup.select('div.product-card'), 1):
                link = product_card.find('a', href=True)
                if link:
                    product_url = ScraperConfig.BASE_URL + link['href']
                    products.append({
                        'page': page,
                        'position': position,
                        'url': product_url
                    })
            
            return products
        except Exception as e:
            logger.error(f"Page {page} error: {str(e)}")
            return []

    def _sync_with_database(self):
        logger.info("Starting database synchronization...")
        api_manager = APIManager()
        current_time = timezone.now()
        
        try:
            existing_urls = api_manager.get_available_urls()
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            existing_urls = []
        
        # Format scraped products
        formatted_products = [{
            "page_id": str(p['page']),
            "product_id_in_page": str(p['position']),
            "url": p['url'],
            "last_checking": current_time
        } for p in self.data_manager._products]

        # Update available URLs
        try:
            api_manager.post_available_urls(formatted_products)
            logger.success(f"Updated {len(formatted_products)} URLs in database")
        except Exception as e:
            logger.error(f"Failed to update available URLs: {str(e)}")
            return

        # Find new and deleted URLs
        existing_url_set = {u['url'] for u in existing_urls}
        current_url_set = {u['url'] for u in formatted_products}

        new_urls = [u for u in formatted_products if u['url'] not in existing_url_set]
        deleted_urls = [{"url": u['url'], "last_checking": current_time} 
                      for u in existing_urls if u['url'] not in current_url_set]

        # Post new URLs
        if new_urls:
            try:
                api_manager.post_new_urls(new_urls)
                logger.success(f"Posted {len(new_urls)} new URLs to database")
            except Exception as e:
                logger.error(f"Failed to post new URLs: {str(e)}")

        # Post deleted URLs
        if deleted_urls:
            try:
                api_manager.post_deleted_urls(deleted_urls)
                logger.success(f"Posted {len(deleted_urls)} deleted URLs to database")
            except Exception as e:
                logger.error(f"Failed to post deleted URLs: {str(e)}")

    def run(self):
        ScraperUtils.setup_logging()
        logger.info("Starting product scraper...")
        
        self.total_pages = self.get_total_pages()
        if self.total_pages == 0:
            logger.error("Scraping işlemi başlatılamadı")
            return
            
        logger.info(f"Total pages to scrape: {self.total_pages}")
        
        with tqdm(total=self.total_pages, desc="Scraping pages") as progress:
            with ThreadPoolExecutor(max_workers=ScraperConfig.MAX_WORKERS) as executor:
                futures = {}
                last_checkpoint = time.time()
                
                try:
                    current_page = 1
                    while current_page <= self.total_pages and not self._stop_requested:
                        if current_page not in self.data_manager._completed_pages:
                            future = executor.submit(self.scrape_page, current_page)
                            futures[future] = current_page
                        
                        for future in as_completed(futures):
                            page = futures.pop(future)
                            products = future.result()
                            self.data_manager.add_products(page, products)
                            progress.update(1)
                        
                        if time.time() - last_checkpoint > ScraperConfig.CHECKPOINT_INTERVAL:
                            self.data_manager.save_checkpoint()
                            last_checkpoint = time.time()
                        
                        current_page += 1
                    
                    # Process remaining futures
                    for future in as_completed(futures):
                        page = futures[future]
                        products = future.result()
                        self.data_manager.add_products(page, products)
                        progress.update(1)
                    
                except Exception as e:
                    logger.critical(f"Critical error: {str(e)}")
                finally:
                    self.data_manager.save_checkpoint()
        
        # Sync with database after scraping completes
        self._sync_with_database()
        
        logger.info(f"Scraping completed! Total products: {len(self.data_manager._products)}")
        if os.path.exists(ScraperConfig.CHECKPOINT_FILE):
            os.remove(ScraperConfig.CHECKPOINT_FILE)

from django.db import close_old_connections
class Command(BaseCommand):
    help = 'Refreshes the product list by scraping LCWaikiki website'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting product list refresh...'))
        close_old_connections()
        
        # Create default config if it doesn't exist
        try:
            config, created = Config.objects.get_or_create(
                name='default',
                defaults={'brands': [
                    'lcwaikiki-classic', 'lcw-modest', 'lcwaikiki-basic',
                    'lcw-casual', 'lcw-vision', 'xside-active', 'lcw-dream',
                    'lcwaikiki-maternity', 'lcw-grace', 'lcw-limited', 'xside',
                    'lcw-jeans', 'lcwaikiki-formal', 'lcw-outdoor', 'lcw-baby',
                    'lc-waikiki', 'lcw-accessories', 'lcw-comfort', 'lcw-eco',
                    'lcw-home', 'lcw-kids', 'lcw-limitless', 'lcw-swimwear', 'lcw-teen'
                ]}
            )
            if created:
                self.stdout.write(self.style.SUCCESS('Created default config with brands'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating default config: {str(e)}'))
        
        # Run the scraper
        try:
            scraper = ProductScraper()
            scraper.run()
            self.stdout.write(self.style.SUCCESS('Product list refresh completed successfully'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error refreshing product list: {str(e)}'))