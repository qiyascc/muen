import logging
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from tqdm import tqdm

# Fix the import to reference the correct module
from lcwaikiki.product_models import Product, ProductSize
from trendyol.models import TrendyolProduct
from trendyol.api_client_new import lcwaikiki_to_trendyol_product, sync_product_to_trendyol, get_product_manager
from trendyol import api_client

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Synchronize products with Trendyol'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--max-items',
            type=int,
            default=50,
            help='Maximum number of items to process in one run'
        )
        
    def handle(self, *args, **options):
        max_items = options['max_items']
        
        self.stdout.write(self.style.SUCCESS(f"Starting Trendyol synchronization (max_items={max_items})"))
        
        # First, make sure we have the latest brands and categories
        self.fetch_reference_data()
        
        # Then check LCWaikiki products that need to be synced
        self.sync_lcwaikiki_products(max_items)
        
        # Finally, check existing Trendyol products for updates
        self.check_trendyol_product_status(max_items)
        
        self.stdout.write(self.style.SUCCESS("Trendyol synchronization completed"))
        
    def fetch_reference_data(self):
        """
        Fetch brands and categories from Trendyol.
        """
        try:
            self.stdout.write("Initializing API connections...")
            
            # Get the product manager which contains the category finder
            product_manager = get_product_manager()
            self.stdout.write(self.style.SUCCESS("Successfully initialized API connections"))
            
            # Fetch categories to populate the cache
            if product_manager and hasattr(product_manager, 'category_finder'):
                self.stdout.write("Fetching categories from Trendyol...")
                categories = product_manager.category_finder.category_cache()
                self.stdout.write(self.style.SUCCESS(f"Fetched {len(categories)} categories"))
            else:
                self.stdout.write(self.style.WARNING("Could not find category finder, using old API client"))
                # Fallback to old API client
                categories = api_client.fetch_categories()
                self.stdout.write(self.style.SUCCESS(f"Fetched {len(categories)} categories using old API client"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching reference data: {str(e)}"))
            
    def sync_lcwaikiki_products(self, max_items):
        """
        Check for LCWaikiki products that need to be synced to Trendyol.
        This includes handling variants (different sizes) as separate products.
        """
        try:
            # Get LCWaikiki products that are in stock and have no Trendyol product
            lcw_products = Product.objects.filter(
                in_stock=True,
                status='active'
            ).exclude(
                trendyolproduct__isnull=False
            ).order_by('-timestamp')[:max_items]
            
            if not lcw_products:
                self.stdout.write("No new LCWaikiki products to sync")
                return
            
            self.stdout.write(f"Found {lcw_products.count()} LCWaikiki products to sync")
            
            processed_count = 0
            with tqdm(total=len(lcw_products), desc="Processing LCWaikiki products") as progress_bar:
                for lcw_product in lcw_products:
                    try:
                        # Check if product has sizes
                        product_sizes = ProductSize.objects.filter(product=lcw_product)
                        
                        if product_sizes.exists():
                            # Process each size as a separate variant
                            self.stdout.write(f"Processing {product_sizes.count()} size variants for {lcw_product.title}")
                            
                            for size in product_sizes:
                                try:
                                    with transaction.atomic():
                                        # Create variant data with size and stock
                                        variant_data = {
                                            'size': size.name,
                                            'stock': size.stock
                                        }
                                        
                                        # Convert LCWaikiki product size variant to Trendyol product
                                        trendyol_product = lcwaikiki_to_trendyol_product(
                                            lcw_product, variant_data=variant_data)
                                        
                                        if trendyol_product:
                                            # Try to sync with Trendyol
                                            sync_product_to_trendyol(trendyol_product)
                                            self.stdout.write(self.style.SUCCESS(
                                                f"Synced product variant {lcw_product.title} - {size.name} with stock {size.stock}"))
                                        else:
                                            self.stdout.write(self.style.WARNING(
                                                f"Could not create Trendyol product for variant {lcw_product.title} - {size.name}"))
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(
                                        f"Error syncing product variant {lcw_product.title} - {size.name}: {str(e)}"))
                                
                                # Small delay between size variants to avoid API rate limits
                                time.sleep(0.2)
                        else:
                            # Process as a single product without variants
                            with transaction.atomic():
                                # Convert LCWaikiki product to Trendyol product
                                trendyol_product = lcwaikiki_to_trendyol_product(lcw_product)
                                
                                if trendyol_product:
                                    # Try to sync with Trendyol
                                    sync_product_to_trendyol(trendyol_product)
                                    self.stdout.write(self.style.SUCCESS(f"Synced product {lcw_product.title}"))
                                else:
                                    self.stdout.write(self.style.WARNING(f"Could not create Trendyol product for {lcw_product.title}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error syncing product {lcw_product.title}: {str(e)}"))
                    finally:
                        progress_bar.update(1)
                        # Small delay to avoid API rate limits
                        time.sleep(0.5)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error in sync_lcwaikiki_products: {str(e)}"))
    
    def check_trendyol_product_status(self, max_items):
        """
        Check the status of existing Trendyol products.
        """
        try:
            # Get Trendyol products that have a batch ID and are in processing state
            processing_products = TrendyolProduct.objects.filter(
                batch_status='processing',
                batch_id__isnull=False
            ).order_by('last_check_time')[:max_items//2]
            
            if processing_products:
                self.stdout.write(f"Checking status for {processing_products.count()} processing products")
                
                with tqdm(total=len(processing_products), desc="Checking processing products") as progress_bar:
                    for product in processing_products:
                        try:
                            # Use the new product manager to check batch status
                            product_manager = get_product_manager()
                            status = product_manager.check_batch_status(product.batch_id)
                            self.stdout.write(f"Product {product.title} status: {status}")
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Error checking status for {product.title}: {str(e)}"))
                        finally:
                            progress_bar.update(1)
                            # Small delay to avoid API rate limits
                            time.sleep(0.5)
            else:
                self.stdout.write("No processing products to check")
            
            # Check for products that need data updates
            # Products with LCWaikiki relationship that have been updated recently
            update_products = TrendyolProduct.objects.filter(
                Q(lcwaikiki_product__isnull=False),
                ~Q(batch_status='processing'),
            ).order_by('last_sync_time')[:max_items//2]
            
            if update_products:
                self.stdout.write(f"Checking for updates in {update_products.count()} products")
                
                with tqdm(total=len(update_products), desc="Checking for updates") as progress_bar:
                    for product in update_products:
                        try:
                            if product.lcwaikiki_product:
                                # Check if LCWaikiki product has been updated since last sync
                                if (not product.last_sync_time or 
                                    product.lcwaikiki_product.timestamp > product.last_sync_time):
                                    
                                    # Check if this is a variant product
                                    if product.variant_key:
                                        # Find the size object that matches the variant key
                                        size = ProductSize.objects.filter(
                                            product=product.lcwaikiki_product,
                                            name=product.variant_key
                                        ).first()
                                        
                                        if size:
                                            # Create variant data with size and stock
                                            variant_data = {
                                                'size': size.name,
                                                'stock': size.stock
                                            }
                                            
                                            # Update Trendyol product from LCWaikiki data with variant info
                                            updated_product = lcwaikiki_to_trendyol_product(
                                                product.lcwaikiki_product, variant_data=variant_data)
                                        else:
                                            # If size no longer exists, skip the update
                                            self.stdout.write(self.style.WARNING(
                                                f"Size {product.variant_key} no longer exists for product {product.title}"))
                                            continue
                                    else:
                                        # Update Trendyol product from LCWaikiki data (no variant)
                                        updated_product = lcwaikiki_to_trendyol_product(product.lcwaikiki_product)
                                    
                                    if updated_product:
                                        # Sync with Trendyol
                                        sync_product_to_trendyol(updated_product)
                                        self.stdout.write(self.style.SUCCESS(f"Updated product {product.title}"))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Error updating product {product.title}: {str(e)}"))
                        finally:
                            progress_bar.update(1)
                            # Small delay to avoid API rate limits
                            time.sleep(0.5)
            else:
                self.stdout.write("No products to update")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error in check_trendyol_product_status: {str(e)}"))