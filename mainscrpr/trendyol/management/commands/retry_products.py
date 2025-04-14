"""
Management command to retry all pending or failed product submissions to Trendyol
"""

import logging
import time
from django.core.management.base import BaseCommand
from django.db.models import Q
from trendyol.models import TrendyolProduct
from trendyol.improved_api_client import sync_product_to_trendyol, update_trendyol_product_status, get_api_client

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Retry pending or failed product submissions to Trendyol'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of products to process'
        )
        
        parser.add_argument(
            '--status',
            type=str,
            choices=['pending', 'failed', 'all'],
            default='all',
            help='Which status type to retry'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Just count products, don\'t actually process them'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        status = options['status']
        dry_run = options['dry_run']
        
        # Prepare filter conditions
        if status == 'pending':
            query = Q(batch_status='pending')
        elif status == 'failed':
            query = Q(batch_status='failed')
        else:  # 'all'
            query = Q(batch_status='pending') | Q(batch_status='failed')
            
        # Also check for empty attributes
        query = query | Q(attributes=[]) | Q(attributes__isnull=True)
            
        products = TrendyolProduct.objects.filter(query).order_by('-id')[:limit]
        count = products.count()
        
        self.stdout.write(f"Found {count} products to retry")
        
        if dry_run:
            self.stdout.write("Dry run completed")
            return
            
        # Check API client availability
        client = get_api_client()
        if not client:
            self.stdout.write(self.style.ERROR("API client not available. Check Trendyol API configuration."))
            return
            
        success_count = 0
        error_count = 0
        
        # Begin processing
        self.stdout.write("Starting product retry process...")
        
        for i, product in enumerate(products, 1):
            try:
                self.stdout.write(f"[{i}/{count}] Processing product {product.id}: {product.title[:50]}...")
                
                # If product is 'processing', just check status
                if product.batch_status == 'processing' and product.batch_id:
                    self.stdout.write(f"Checking status for product {product.id} with batch ID {product.batch_id}")
                    status = update_trendyol_product_status(product)
                    
                    if status == 'completed':
                        self.stdout.write(self.style.SUCCESS(f"Product {product.id} completed successfully"))
                        success_count += 1
                    elif status == 'failed':
                        self.stdout.write(self.style.WARNING(f"Product {product.id} failed: {product.status_message}"))
                        error_count += 1
                    else:
                        self.stdout.write(f"Product {product.id} still processing")
                else:
                    # Otherwise, try to submit the product
                    result = sync_product_to_trendyol(product)
                    
                    if result:
                        self.stdout.write(self.style.SUCCESS(f"Product {product.id} submitted successfully"))
                        success_count += 1
                    else:
                        self.stdout.write(self.style.WARNING(f"Product {product.id} submission failed: {product.status_message}"))
                        error_count += 1
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing product {product.id}: {str(e)}"))
                error_count += 1
                
            # Sleep briefly to avoid rate limiting
            time.sleep(0.2)
            
        # Summary
        self.stdout.write("Retry process completed")
        self.stdout.write(f"Successfully processed: {success_count}")
        self.stdout.write(f"Errors: {error_count}")