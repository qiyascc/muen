"""
Management command to create a product in Trendyol using OpenAI
to optimize product data and attributes.

This command takes a TrendyolProduct ID and uses OpenAI to generate optimized
product data with appropriate attributes for Trendyol.

Usage:
    python manage.py create_product_with_ai <product_id>
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from trendyol.models import TrendyolProduct
from trendyol.openai_processor import create_trendyol_product_with_ai

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create a product in Trendyol using OpenAI to optimize product data'

    def add_arguments(self, parser):
        parser.add_argument('product_id', type=int, help='TrendyolProduct ID to process')

    def handle(self, *args, **options):
        product_id = options['product_id']

        try:
            product = TrendyolProduct.objects.get(id=product_id)
        except TrendyolProduct.DoesNotExist:
            raise CommandError(f'TrendyolProduct with ID {product_id} does not exist')

        try:
            self.stdout.write(self.style.SUCCESS(f'Processing product: {product.title}'))
            
            # Call OpenAI processor
            batch_id = create_trendyol_product_with_ai(product)
            
            if not batch_id:
                self.stdout.write(self.style.ERROR(
                    f'Failed to create product. Check status message: {product.status_message}'
                ))
                return
            
            self.stdout.write(self.style.SUCCESS(
                f'Product successfully sent to Trendyol with batch ID: {batch_id}'
            ))
            
        except Exception as e:
            logger.exception(f"Error in create_product_with_ai command: {str(e)}")
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))