"""
Management command to synchronize multiple products with Trendyol
using OpenAI to optimize product data.

This command accepts optional filters and will process a batch of products,
using OpenAI to optimize their attributes before sending to Trendyol.

Usage:
    python manage.py sync_trendyol_with_ai [--limit=10] [--skip=0] [--batch_size=5]
"""

import logging
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from trendyol.models import TrendyolProduct
from trendyol.openai_processor import create_trendyol_product_with_ai

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Synchronize Trendyol products with AI optimization'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10, 
                            help='Maximum number of products to process')
        parser.add_argument('--skip', type=int, default=0,
                            help='Number of products to skip')
        parser.add_argument('--batch_size', type=int, default=5,
                            help='Number of products to process in a batch')
        parser.add_argument('--retry_failed', action='store_true',
                            help='Retry previously failed products')
        parser.add_argument('--delay', type=int, default=2,
                            help='Delay in seconds between API calls')

    def handle(self, *args, **options):
        limit = options['limit']
        skip = options['skip']
        batch_size = options['batch_size']
        retry_failed = options['retry_failed']
        delay = options['delay']
        
        self.stdout.write(self.style.SUCCESS(
            f'Starting AI-powered Trendyol synchronization: '
            f'limit={limit}, skip={skip}, batch_size={batch_size}'
        ))
        
        # Build query to get products that need processing
        query = Q()
        
        if retry_failed:
            # Include products that have failed
            query |= Q(batch_status='failed')
        else:
            # Products that have never been synchronized
            query |= Q(batch_id__isnull=True)
            # Products that are not in pending or processing state
            query &= ~Q(batch_status__in=['pending', 'processing'])
        
        # Get products, ordered by creation date (oldest first)
        products = TrendyolProduct.objects.filter(query).order_by('created_at')[skip:skip+limit]
        
        total_products = products.count()
        self.stdout.write(self.style.SUCCESS(f'Found {total_products} products to process'))
        
        if total_products == 0:
            return
        
        success_count = 0
        error_count = 0
        current_batch = 0
        
        # Process products in batches
        for i, product in enumerate(products):
            try:
                self.stdout.write(f'Processing {i+1}/{total_products}: {product.title}')
                
                # Use OpenAI to process and submit product
                batch_id = create_trendyol_product_with_ai(product)
                
                if batch_id:
                    self.stdout.write(self.style.SUCCESS(
                        f'Successfully sent product to Trendyol with batch ID: {batch_id}'
                    ))
                    success_count += 1
                else:
                    self.stdout.write(self.style.ERROR(
                        f'Failed to create product. Status: {product.batch_status}, '
                        f'Message: {product.status_message}'
                    ))
                    error_count += 1
                
                # Add delay between requests to avoid rate limiting
                time.sleep(delay)
                
                # Process in batches with status reports
                current_batch += 1
                if current_batch >= batch_size:
                    self.stdout.write(self.style.SUCCESS(
                        f'Processed {i+1}/{total_products} products. '
                        f'Success: {success_count}, Errors: {error_count}'
                    ))
                    current_batch = 0
                
            except Exception as e:
                logger.exception(f"Error processing product {product.id}: {str(e)}")
                self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
                error_count += 1
        
        # Final status report
        self.stdout.write(self.style.SUCCESS(
            f'AI-powered Trendyol synchronization completed. '
            f'Processed {total_products} products. '
            f'Success: {success_count}, Errors: {error_count}'
        ))