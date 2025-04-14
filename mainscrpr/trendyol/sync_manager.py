"""
Synchronization manager for Trendyol integration.
This module handles automated synchronization between LCWaikiki and Trendyol.
"""
import logging
import time
from django.db import transaction
from django.utils import timezone

from lcwaikiki.models import Product as LCWaikikiProduct
from .models import TrendyolProduct, TrendyolCategory, TrendyolBrand
from .trendyol_client import TrendyolClient

logger = logging.getLogger(__name__)

class TrendyolSyncManager:
    """
    Manager for synchronizing products between LCWaikiki and Trendyol
    """
    
    def __init__(self):
        """Initialize the sync manager"""
        self.client = TrendyolClient()
    
    def sync_products(self, max_items=100, batch_size=10, 
                    include_failed=False, dry_run=False):
        """
        Synchronize products from LCWaikiki to Trendyol
        
        Args:
            max_items: Maximum number of items to process
            batch_size: Number of items to process in each batch
            include_failed: Whether to include previously failed products
            dry_run: If True, don't actually submit to Trendyol
            
        Returns:
            tuple: (success_count, failed_count, total_count)
        """
        logger.info(f"Starting product synchronization...")
        logger.info(f"Batch size: {batch_size}, Max items per operation: {max_items}")
        
        # Ensure we have API client initialized
        if not self.client.api_client:
            logger.error("API client not initialized, cannot sync products")
            return 0, 0, 0
        
        # Ensure we have categories and brands
        self._ensure_base_data()
        
        # Get LCWaikiki products that need to be synced to Trendyol
        products_to_sync = self._get_products_to_sync(max_items, include_failed)
        
        if not products_to_sync:
            logger.info("No products need synchronization")
            return 0, 0, 0
        
        logger.info(f"Found {len(products_to_sync)} products to synchronize")
        
        success_count = 0
        failed_count = 0
        
        # Process products in batches
        for i in range(0, len(products_to_sync), batch_size):
            batch = products_to_sync[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} of {(len(products_to_sync)-1)//batch_size + 1}")
            
            for lcw_product in batch:
                try:
                    result = self._sync_single_product(lcw_product, dry_run)
                    if result:
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error synchronizing product {lcw_product.id}: {str(e)}")
                    failed_count += 1
            
            # Brief pause between batches to avoid rate limiting
            if i + batch_size < len(products_to_sync):
                time.sleep(0.5)
        
        logger.info(f"Synchronization complete: {success_count} successful, {failed_count} failed")
        return success_count, failed_count, len(products_to_sync)
    
    def check_batch_statuses(self, max_items=100):
        """
        Check status of pending batches
        
        Args:
            max_items: Maximum number of batches to check
            
        Returns:
            int: Number of batches checked
        """
        if not self.client.api_client:
            logger.error("API client not initialized, cannot check batches")
            return 0
        
        # Get products with pending batch status
        pending_products = TrendyolProduct.objects.filter(
            batch_status='pending', 
            batch_id__isnull=False
        ).order_by('-updated_at')[:max_items]
        
        if not pending_products:
            logger.info("No pending batches to check")
            return 0
        
        count = 0
        unique_batch_ids = {}  # Using dict to preserve order
        
        # Collect unique batch IDs
        for product in pending_products:
            if product.batch_id and product.batch_id not in unique_batch_ids:
                unique_batch_ids[product.batch_id] = product
        
        # Check each batch status
        for batch_id, product in unique_batch_ids.items():
            try:
                status = self.client.check_batch_status(batch_id)
                count += 1
                
                # Pause briefly between requests
                if count < len(unique_batch_ids):
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Error checking batch {batch_id}: {str(e)}")
        
        logger.info(f"Checked {count} batch statuses")
        return count
    
    def _ensure_base_data(self):
        """Ensure categories and brands are loaded from API"""
        # Check if we have categories
        if TrendyolCategory.objects.count() == 0:
            logger.info("No categories found, fetching from API...")
            self.client.fetch_and_store_categories()
        
        # Check if we have brands
        if TrendyolBrand.objects.count() == 0:
            logger.info("No brands found, fetching from API...")
            self.client.fetch_and_store_brands()
    
    def _get_products_to_sync(self, limit, include_failed):
        """
        Get LCWaikiki products that need to be synced to Trendyol
        
        Args:
            limit: Maximum number of products to return
            include_failed: Whether to include previously failed products
            
        Returns:
            list: LCWaikiki product instances
        """
        # Find LCWaikiki products that haven't been synced to Trendyol yet
        lcw_products = LCWaikikiProduct.objects.filter(
            is_active=True,
            is_available=True,
            price__gt=0
        )
        
        # Exclude products that already have a successful Trendyol product
        synced_product_ids = TrendyolProduct.objects.filter(
            batch_status='completed',
            lcwaikiki_product__isnull=False
        ).values_list('lcwaikiki_product_id', flat=True)
        
        if not include_failed:
            # Also exclude products that have failed Trendyol products
            failed_product_ids = TrendyolProduct.objects.filter(
                batch_status='failed',
                lcwaikiki_product__isnull=False
            ).values_list('lcwaikiki_product_id', flat=True)
            
            lcw_products = lcw_products.exclude(id__in=list(failed_product_ids))
        
        # Exclude already synced products
        lcw_products = lcw_products.exclude(id__in=list(synced_product_ids))
        
        # Limit the result set
        return lcw_products.order_by('-created_at')[:limit]
    
    def _sync_single_product(self, lcw_product, dry_run=False):
        """
        Synchronize a single LCWaikiki product to Trendyol
        
        Args:
            lcw_product: LCWaikiki product instance
            dry_run: If True, don't actually submit to Trendyol
            
        Returns:
            bool: Success status
        """
        try:
            # Check if we already have a Trendyol product for this LCWaikiki product
            trendyol_product = TrendyolProduct.objects.filter(
                lcwaikiki_product=lcw_product
            ).first()
            
            # If no existing product, create a new one
            if not trendyol_product:
                with transaction.atomic():
                    trendyol_product = TrendyolProduct.objects.create(
                        title=lcw_product.title or "LC Waikiki Product",
                        description=lcw_product.description or lcw_product.title or "LC Waikiki Product Description",
                        barcode=lcw_product.barcode or f"LCW-{lcw_product.id}",
                        product_main_id=lcw_product.product_code or f"LCW-{lcw_product.id}",
                        stock_code=lcw_product.product_code or f"LCW-{lcw_product.id}",
                        brand_name="LCW",
                        brand_id=7651,  # Default LC Waikiki brand ID
                        category_name=lcw_product.category or "Clothing",
                        image_url=lcw_product.image_url if hasattr(lcw_product, 'image_url') else "",
                        lcwaikiki_product=lcw_product,
                        batch_status='new',
                        status_message="Created from LCWaikiki product",
                        currency_type="TRY",
                        vat_rate=18
                    )
            
            # If we're doing a dry run, stop here
            if dry_run:
                logger.info(f"Dry run - would submit product {lcw_product.id} to Trendyol")
                return True
            
            # Submit to Trendyol
            result = self.client.create_or_update_product(trendyol_product)
            
            if result:
                logger.info(f"Successfully synchronized product {lcw_product.id} to Trendyol")
                return True
            else:
                logger.error(f"Failed to synchronize product {lcw_product.id} to Trendyol")
                return False
                
        except Exception as e:
            logger.error(f"Error synchronizing product {lcw_product.id}: {str(e)}")
            return False