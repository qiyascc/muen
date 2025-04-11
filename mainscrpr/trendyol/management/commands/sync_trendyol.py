import logging
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from datetime import timedelta

from lcwaikiki.models import Product as LCWProduct
from trendyol.models import TrendyolProduct
from trendyol.api_client import update_product_from_lcwaikiki, create_trendyol_product, check_product_batch_status

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Synchronize products with Trendyol marketplace'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--max-items',
            type=int,
            default=100,
            help='Maximum number of products to process in a single run'
        )
        parser.add_argument(
            '--check-pending',
            action='store_true',
            help='Check status of pending products'
        )
        parser.add_argument(
            '--sync-new',
            action='store_true',
            help='Synchronize new products with Trendyol'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing products on Trendyol'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Trendyol synchronization...'))
        
        max_items = options.get('max_items', 100)
        check_pending = options.get('check_pending', False)
        sync_new = options.get('sync_new', False)
        update_existing = options.get('update_existing', False)
        
        # Default behavior: do everything if no specific options provided
        if not (check_pending or sync_new or update_existing):
            check_pending = sync_new = update_existing = True
        
        # Process operations
        processed_count = 0
        
        try:
            # Step 1: Check pending products
            if check_pending:
                self.stdout.write('Checking pending product uploads...')
                processed_count += self.check_pending_products(max_items)
            
            # Step 2: Synchronize new products from LCWaikiki to Trendyol
            if sync_new:
                self.stdout.write('Finding new products to sync with Trendyol...')
                processed_count += self.sync_new_products(max_items)
            
            # Step 3: Update existing products if they've changed
            if update_existing:
                self.stdout.write('Checking for product updates...')
                processed_count += self.update_existing_products(max_items)
                
            self.stdout.write(self.style.SUCCESS(f'Trendyol synchronization completed. Processed {processed_count} items.'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during Trendyol synchronization: {str(e)}'))
            logger.error(f'Error during Trendyol synchronization: {str(e)}', exc_info=True)
            return False
            
        return True
    
    def check_pending_products(self, max_items):
        """Check status of pending Trendyol products"""
        pending_products = TrendyolProduct.objects.filter(
            batch_id__isnull=False,
            batch_status__in=['pending', 'processing']
        ).order_by('last_check_time')[:max_items]
        
        count = 0
        for product in pending_products:
            try:
                if product.needs_status_check():
                    self.stdout.write(f"Checking status for: {product.title}")
                    check_product_batch_status(product)
                    count += 1
                    # Add a small delay to avoid overwhelming the API
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error checking product {product.id}: {str(e)}")
        
        return count
    
    def sync_new_products(self, max_items):
        """Find new LCWaikiki products and create them on Trendyol"""
        # Find LCWaikiki products that aren't linked to Trendyol products yet
        with transaction.atomic():
            lcw_products = LCWProduct.objects.filter(
                in_stock=True,
                status='active'
            ).exclude(
                trendyol_products__isnull=False
            ).order_by('-timestamp')[:max_items]
            
            count = 0
            for lcw_product in lcw_products:
                try:
                    self.stdout.write(f"Creating Trendyol product for: {lcw_product.title}")
                    
                    # Create Trendyol product from LCWaikiki product
                    trendyol_product = update_product_from_lcwaikiki(lcw_product)
                    if trendyol_product:
                        # Submit to Trendyol API
                        batch_id = create_trendyol_product(trendyol_product)
                        if batch_id:
                            self.stdout.write(self.style.SUCCESS(f"Successfully submitted to Trendyol, batch ID: {batch_id}"))
                            count += 1
                    
                    # Add a small delay to avoid overwhelming the API
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error creating Trendyol product for {lcw_product.id}: {str(e)}")
            
            return count
    
    def update_existing_products(self, max_items):
        """Update existing Trendyol products if their LCWaikiki counterparts have changed"""
        cutoff_time = timezone.now() - timedelta(hours=12)
        
        # Find Trendyol products with recently updated LCWaikiki products
        trendyol_products = TrendyolProduct.objects.filter(
            lcwaikiki_product__isnull=False,
            lcwaikiki_product__timestamp__gt=cutoff_time,
            batch_status='completed'  # Only update products that were successfully created
        ).exclude(
            # Avoid products that were recently synced
            last_sync_time__gt=cutoff_time
        ).order_by('last_sync_time')[:max_items]
        
        count = 0
        for trendyol_product in trendyol_products:
            try:
                lcw_product = trendyol_product.lcwaikiki_product
                
                # Check if price or stock has changed
                lcw_price = lcw_product.price or 0
                trendyol_price = trendyol_product.price or 0
                
                lcw_in_stock = lcw_product.in_stock
                trendyol_in_stock = trendyol_product.quantity > 0
                
                if abs(float(lcw_price) - float(trendyol_price)) > 0.01 or lcw_in_stock != trendyol_in_stock:
                    self.stdout.write(f"Updating Trendyol product: {trendyol_product.title}")
                    
                    # Update the Trendyol product from LCWaikiki data
                    trendyol_product.from_lcwaikiki_product(lcw_product)
                    trendyol_product.save()
                    
                    # Submit for update (recreate the product)
                    batch_id = create_trendyol_product(trendyol_product)
                    if batch_id:
                        self.stdout.write(self.style.SUCCESS(f"Successfully updated on Trendyol, batch ID: {batch_id}"))
                        count += 1
                    
                    # Add a small delay to avoid overwhelming the API
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error updating Trendyol product {trendyol_product.id}: {str(e)}")
        
        return count