import logging
import json
import time
import datetime
import sys
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.conf import settings

from lcwaikiki.models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl
from lcwaikiki.product_models import Product, ProductSize, City, Store, SizeStoreStock
from lcwaikiki.product_scraper import ProductScraper

# Configure logging for better visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('lcwaikiki.sync_products')

class Command(BaseCommand):
    help = 'Synchronizes product data with URLs and updates only changed data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            default=10,
            type=int,
            help='Number of products to process in each batch',
        )
        parser.add_argument(
            '--max-items',
            default=100,
            type=int,
            help='Maximum number of items to process in a single run',
        )
        parser.add_argument(
            '--check-deleted',
            action='store_true',
            help='Check for deleted products',
        )
        parser.add_argument(
            '--check-new',
            action='store_true',
            help='Check for new products',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing products',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Perform all sync operations',
        )

    def handle(self, *args, **options):
        batch_size = options.get('batch_size', 10)
        max_items = options.get('max_items', 100)
        check_deleted = options.get('check_deleted', False) or options.get('all', False)
        check_new = options.get('check_new', False) or options.get('all', False)
        update_existing = options.get('update_existing', False) or options.get('all', False)
        
        # If no specific operation is selected, do all operations
        if not any([check_deleted, check_new, update_existing, options.get('all', False)]):
            check_deleted = check_new = update_existing = True
        
        self.stdout.write(self.style.SUCCESS('Starting product synchronization...'))
        self.stdout.write(self.style.SUCCESS(f'Batch size: {batch_size}, Max items per operation: {max_items}'))
        
        scraper = ProductScraper()
        
        # Process new URLs
        if check_new:
            self.process_new_urls(scraper, batch_size, max_items)
            
        # Update existing products
        if update_existing:
            self.update_existing_products(scraper, batch_size, max_items)
            
        # Check for deleted products
        if check_deleted:
            self.check_deleted_products(scraper, max_items)
            
        self.stdout.write(self.style.SUCCESS('Product synchronization completed successfully'))

    def process_new_urls(self, scraper, batch_size, max_items=100):
        """Process new product URLs and add them to the database"""
        self.stdout.write(self.style.NOTICE('Checking for new product URLs...'))
        
        try:
            # Get new URLs from the database, limited by max_items
            new_urls = list(ProductNewUrl.objects.all().values_list('url', flat=True)[:max_items])
            count = len(new_urls)
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS('No new URLs to process'))
                return
                
            self.stdout.write(self.style.SUCCESS(f'Found {count} new URLs to process (limited to {max_items})'))
            
            # Process URLs in batches with small delay between batches
            processed_count = 0
            success_count = 0
            
            for i in range(0, count, batch_size):
                batch = new_urls[i:i+batch_size]
                
                for url in batch:
                    try:
                        # Process the product URL and save to database
                        success = scraper.process_product_url(url)
                        
                        if success:
                            success_count += 1
                            
                            # Extract page_id and product_id_in_page from the URL
                            # Example: https://www.lcw.com/tr-TR/TR/p/erkek-slim-fit-jean-pantolon-9W5417Z8-H89
                            url_parts = url.split('/')
                            
                            if len(url_parts) >= 2:
                                product_part = url_parts[-1]
                                page_id = product_part.split('-')[-1] if '-' in product_part else 'unknown'
                                product_id_in_page = product_part.split('-')[0] if '-' in product_part else product_part
                                
                                # Add to available URLs
                                ProductAvailableUrl.objects.get_or_create(
                                    page_id=page_id,
                                    product_id_in_page=product_id_in_page,
                                    defaults={
                                        'url': url,
                                        'last_checking': timezone.now()
                                    }
                                )
                                
                                # Remove from new URLs
                                ProductNewUrl.objects.filter(url=url).delete()
                                
                                self.stdout.write(self.style.SUCCESS(f'Successfully processed new URL: {url}'))
                            else:
                                self.stdout.write(self.style.WARNING(f'Could not parse URL format: {url}'))
                        else:
                            self.stdout.write(self.style.ERROR(f'Failed to process new URL: {url}'))
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing URL {url}: {str(e)}'))
                        
                    processed_count += 1
                    
                # Print progress
                self.stdout.write(self.style.SUCCESS(
                    f'Progress: {processed_count}/{count} URLs processed, {success_count} successful'
                ))
                
                # Add a small delay between batches
                if i + batch_size < count:
                    time.sleep(1)
                    
            self.stdout.write(self.style.SUCCESS(
                f'Completed new URL processing: {processed_count}/{count} URLs processed, {success_count} successful'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error processing new URLs: {str(e)}'))

    def update_existing_products(self, scraper, batch_size, max_items=100):
        """Update existing products with only changed data"""
        self.stdout.write(self.style.NOTICE('Updating existing products...'))
        
        try:
            # Get all available product URLs
            available_urls = list(ProductAvailableUrl.objects.all().values_list('url', flat=True))
            count = len(available_urls)
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS('No existing products to update'))
                return
                
            self.stdout.write(self.style.SUCCESS(f'Found {count} existing products to check for updates'))
            
            # Get products ordered by oldest timestamp first, limited by max_items
            products_to_update = list(Product.objects.all().order_by('timestamp').values_list('url', flat=True)[:max_items])
            update_count = len(products_to_update)
            
            if update_count == 0:
                self.stdout.write(self.style.SUCCESS('No existing products to update'))
                return
                
            self.stdout.write(self.style.SUCCESS(f'Processing {update_count} products for updates'))
            
            # Process products in batches
            processed_count = 0
            updated_count = 0
            unchanged_count = 0
            
            for i in range(0, update_count, batch_size):
                batch = products_to_update[i:i+batch_size]
                
                for url in batch:
                    try:
                        # Get the existing product
                        try:
                            existing_product = Product.objects.get(url=url)
                        except Product.DoesNotExist:
                            self.stdout.write(self.style.WARNING(f'Product not found for URL: {url}'))
                            continue
                            
                        # Fetch the current product data
                        response = scraper.fetch(url)
                        
                        if not response:
                            self.stdout.write(self.style.ERROR(f'Failed to fetch product data for URL: {url}'))
                            continue
                            
                        # Extract product data
                        product_data = scraper.extract_product_data(response)
                        
                        if not product_data:
                            self.stdout.write(self.style.ERROR(f'Failed to extract product data for URL: {url}'))
                            continue
                            
                        # Check what's changed and only update changed fields
                        changes = {}
                        
                        # Check basic product fields
                        product_fields = [
                            'title', 'category', 'price', 'discount_ratio', 'in_stock', 
                            'color', 'description', 'images'
                        ]
                        
                        for field in product_fields:
                            new_value = product_data['product'].get(field)
                            old_value = getattr(existing_product, field)
                            
                            # For JSONField (images)
                            if field == 'images':
                                if set(new_value) != set(old_value):
                                    changes[field] = new_value
                            # For other fields
                            elif new_value != old_value and new_value is not None:
                                changes[field] = new_value
                                
                        # Check if any product data has changed
                        if changes:
                            # Only update changed fields
                            for field, value in changes.items():
                                setattr(existing_product, field, value)
                                
                            # Update timestamp
                            existing_product.timestamp = timezone.now()
                            existing_product.save()
                            
                            self.stdout.write(self.style.SUCCESS(
                                f'Updated product {existing_product.title} with changes: {", ".join(changes.keys())}'
                            ))
                            updated_count += 1
                        else:
                            unchanged_count += 1
                            
                        # Now check and update size information
                        new_sizes = product_data['sizes']
                        existing_sizes = list(existing_product.sizes.all())
                        
                        # Check for changed or new sizes
                        for new_size_data in new_sizes:
                            size_name = new_size_data['size_name']
                            matching_size = next((s for s in existing_sizes if s.size_name == size_name), None)
                            
                            if matching_size:
                                # Update existing size only if data has changed
                                size_changed = False
                                
                                if new_size_data.get('size_id') and new_size_data['size_id'] != matching_size.size_id:
                                    matching_size.size_id = new_size_data['size_id']
                                    size_changed = True
                                    
                                new_stock = new_size_data.get('size_general_stock', 0)
                                if new_stock != matching_size.size_general_stock:
                                    matching_size.size_general_stock = new_stock
                                    size_changed = True
                                    
                                if size_changed:
                                    matching_size.save()
                                    self.stdout.write(self.style.SUCCESS(
                                        f'Updated size {size_name} for product {existing_product.title}'
                                    ))
                            else:
                                # Create new size
                                ProductSize.objects.create(
                                    product=existing_product,
                                    size_name=size_name,
                                    size_id=new_size_data.get('size_id'),
                                    size_general_stock=new_size_data.get('size_general_stock', 0),
                                    product_option_size_reference=new_size_data.get('product_option_size_reference')
                                )
                                self.stdout.write(self.style.SUCCESS(
                                    f'Added new size {size_name} to product {existing_product.title}'
                                ))
                                
                        # Check for sizes that are no longer available
                        current_size_names = [s['size_name'] for s in new_sizes]
                        for existing_size in existing_sizes:
                            if existing_size.size_name not in current_size_names:
                                existing_size.delete()
                                self.stdout.write(self.style.SUCCESS(
                                    f'Removed size {existing_size.size_name} from product {existing_product.title}'
                                ))
                                
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error updating product {url}: {str(e)}'))
                        
                    processed_count += 1
                    
                # Print progress
                self.stdout.write(self.style.SUCCESS(
                    f'Progress: {processed_count}/{update_count} products processed, '
                    f'{updated_count} updated, {unchanged_count} unchanged'
                ))
                
                # Add a small delay between batches
                if i + batch_size < update_count:
                    time.sleep(1)
                    
            self.stdout.write(self.style.SUCCESS(
                f'Completed product updates: {processed_count}/{update_count} products processed, '
                f'{updated_count} updated, {unchanged_count} unchanged'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error updating existing products: {str(e)}'))

    def check_deleted_products(self, scraper):
        """Check for deleted products and update their status"""
        self.stdout.write(self.style.NOTICE('Checking for deleted products...'))
        
        try:
            # Get the list of deleted URLs from the database
            deleted_urls = list(ProductDeletedUrl.objects.all().values_list('url', flat=True))
            count = len(deleted_urls)
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS('No deleted URLs to process'))
                return
                
            self.stdout.write(self.style.SUCCESS(f'Found {count} deleted URLs to process'))
            
            # Process deleted URLs
            processed_count = 0
            
            for url in deleted_urls:
                try:
                    # Check if a product exists with this URL
                    try:
                        product = Product.objects.get(url=url)
                        
                        # Mark product as deleted
                        product.status = 'deleted'
                        product.in_stock = False
                        product.save()
                        
                        self.stdout.write(self.style.SUCCESS(f'Marked product as deleted: {url}'))
                        
                        # Remove from ProductAvailableUrl
                        ProductAvailableUrl.objects.filter(url=url).delete()
                        
                    except Product.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'No product found for deleted URL: {url}'))
                        
                    # Remove from deleted URLs since it's been processed
                    ProductDeletedUrl.objects.filter(url=url).delete()
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error processing deleted URL {url}: {str(e)}'))
                    
                processed_count += 1
                
                # Print progress every 10 items
                if processed_count % 10 == 0:
                    self.stdout.write(self.style.SUCCESS(
                        f'Progress: {processed_count}/{count} deleted URLs processed'
                    ))
                    
            self.stdout.write(self.style.SUCCESS(
                f'Completed processing deleted URLs: {processed_count}/{count} processed'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking deleted products: {str(e)}'))