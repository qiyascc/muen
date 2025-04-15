"""
Submit a product to Trendyol without attributes, then analyze batch errors and resubmit with required attributes.

This command implements a "try first, then fix" approach to product submission:
1. First submits a product without any attributes
2. Checks the batch status and extracts required attributes from error messages
3. Automatically adds the required attributes with sensible values
4. Resubmits the product with the minimal set of required attributes

Usage:
    python manage.py submit_without_attributes --product_id=<id> [--check_only]
"""

import time
import logging
from django.core.management.base import BaseCommand
from trendyol.models import TrendyolProduct
from trendyol.api_client_new import get_product_manager, ProductData

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Submit a product to Trendyol without attributes, then fix based on error messages'
    
    def add_arguments(self, parser):
        parser.add_argument('--product_id', type=int, required=True, help='TrendyolProduct ID to submit')
        parser.add_argument('--check_only', action='store_true', help='Only check batch status, don\'t submit')
        parser.add_argument('--batch_id', type=str, help='Check specific batch ID instead of submitting new product')
        parser.add_argument('--wait', type=int, default=10, help='Seconds to wait for batch processing (default: 10)')
        
    def handle(self, *args, **options):
        product_id = options['product_id']
        check_only = options['check_only']
        batch_id = options.get('batch_id')
        wait_time = options['wait']
        
        try:
            # Get product from database
            product = TrendyolProduct.objects.get(id=product_id)
            product_manager = get_product_manager()
            
            if check_only and batch_id:
                # Only check batch status
                self.stdout.write(f"Checking batch status for batch ID: {batch_id}")
                batch_status = product_manager.check_batch_status(batch_id)
                self.stdout.write(f"Batch status: {batch_status.get('status')}")
                
                # Check individual item status and error messages
                items = batch_status.get('items', [])
                for i, item in enumerate(items):
                    self.stdout.write(f"Item {i+1}:")
                    self.stdout.write(f"  Status: {item.get('status')}")
                    
                    if 'failureReasons' in item and item['failureReasons']:
                        self.stdout.write("  Failure reasons:")
                        for reason in item['failureReasons']:
                            self.stdout.write(f"    - {reason}")
                
                return
                
            if batch_id:
                # Use existing batch ID for processing
                self.stdout.write(f"Processing existing batch ID: {batch_id}")
                
                # Create product data object for resubmission
                product_data = ProductData(
                    barcode=product.barcode,
                    title=product.title,
                    product_main_id=product.product_main_id,
                    brand_name=product.brand_name,
                    category_name=product.category_name,
                    quantity=product.quantity,
                    stock_code=product.stock_code,
                    price=float(product.price),
                    sale_price=float(product.price),  # Use same price if no sale price defined
                    description=product.description,
                    image_url=product.image_url
                )
                
                # Process batch errors and resubmit with required attributes
                result = product_manager.process_batch_errors(batch_id, product_data)
                self.stdout.write(f"Processing result: {result}")
                
                if result['success']:
                    product.batch_id = result['batch_id']
                    product.batch_status = 'processing'
                    product.status_message = result['message']
                    product.save()
                    self.stdout.write(self.style.SUCCESS(f"Product resubmitted with batch ID: {result['batch_id']}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Failed to process batch: {result['message']}"))
                
                return
            
            if check_only:
                self.stdout.write(self.style.ERROR("--check_only requires --batch_id"))
                return
                
            # Submit product without attributes first
            self.stdout.write(f"Submitting product without attributes: {product.title}")
            
            # Create product data
            product_data = ProductData(
                barcode=product.barcode,
                title=product.title,
                product_main_id=product.product_main_id,
                brand_name=product.brand_name,
                category_name=product.category_name,
                quantity=product.quantity,
                stock_code=product.stock_code,
                price=float(product.price),
                sale_price=float(product.price),  # Use same price if no sale price defined
                description=product.description,
                image_url=product.image_url
            )
            
            # Submit without attributes (empty list)
            batch_id = product_manager.create_product_without_attributes(product_data)
            self.stdout.write(f"Product submitted with batch ID: {batch_id}")
            
            # Update product in database
            product.batch_id = batch_id
            product.batch_status = 'processing'
            product.status_message = 'Submitted without attributes'
            product.save()
            
            # Wait for batch processing
            self.stdout.write(f"Waiting {wait_time} seconds for batch processing...")
            time.sleep(wait_time)
            
            # Process batch errors and resubmit with required attributes
            result = product_manager.process_batch_errors(batch_id, product_data)
            self.stdout.write(f"Processing result: {result}")
            
            if result['success']:
                product.batch_id = result['batch_id']
                product.batch_status = 'processing'
                product.status_message = result['message']
                product.save()
                self.stdout.write(self.style.SUCCESS(f"Product resubmitted with batch ID: {result['batch_id']}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to process batch: {result['message']}"))
                
        except TrendyolProduct.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Product with ID {product_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing product: {str(e)}"))