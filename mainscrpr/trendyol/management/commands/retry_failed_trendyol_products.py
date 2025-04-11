import re
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from trendyol.models import TrendyolProduct
from trendyol.api_client import get_api_client, prepare_product_data


class Command(BaseCommand):
    help = 'Retry failed Trendyol products with improved attribute handling'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Include all products, not just failed ones',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of products to process (default: 10)',
        )

    def handle(self, *args, **options):
        limit = options.get('limit', 10)
        process_all = options.get('all', False)
        
        # Color ID mapping to use numeric IDs instead of string values
        color_id_map = {
            'Beyaz': 1001, 
            'Siyah': 1002, 
            'Mavi': 1003, 
            'Kirmizi': 1004, 
            'Pembe': 1005,
            'Yeşil': 1006,
            'Sarı': 1007,
            'Mor': 1008,
            'Gri': 1009,
            'Kahverengi': 1010,
            'Ekru': 1011,
            'Bej': 1012,
            'Lacivert': 1013,
            'Turuncu': 1014,
            'Krem': 1015
        }
        
        # Get products to retry
        if process_all:
            products = TrendyolProduct.objects.exclude(
                batch_status__in=['pending', 'processing']
            ).order_by('-updated_at')[:limit]
            self.stdout.write(f"Processing up to {limit} products (all statuses except pending/processing)")
        else:
            products = TrendyolProduct.objects.filter(
                batch_status='failed'
            ).order_by('-updated_at')[:limit]
            self.stdout.write(f"Processing up to {limit} failed products")
            
        if not products:
            self.stdout.write(self.style.WARNING("No eligible products found to retry"))
            return
            
        self.stdout.write(f"Found {len(products)} products to process")
            
        fixed_count = 0
        success_count = 0
        
        for product in products:
            with transaction.atomic():
                try:
                    self.stdout.write(f"Processing product {product.id}: {product.title}")
                    
                    # Step 1: Fix product attributes (extract color from title if possible)
                    color = None
                    if product.title:
                        color_match = re.search(r'(Beyaz|Siyah|Mavi|Kirmizi|Pembe|Yeşil|Sarı|Mor|Gri|Kahverengi|Ekru|Bej|Lacivert|Turuncu|Krem)', 
                                                product.title, re.IGNORECASE)
                        if color_match:
                            color = color_match.group(1)
                    
                    # Apply proper numeric color ID attribute
                    if color and color in color_id_map:
                        color_id = color_id_map[color]
                        product.attributes = [{"attributeId": 348, "attributeValueId": color_id}]
                        fixed_count += 1
                    
                    # Set to pending status with a placeholder message
                    product.batch_status = 'pending'
                    product.status_message = 'Pending retry after command-line fix'
                    product.save()
                    
                    # Step 2: Define product data preparation function without the 'color' field
                    def prepare_product_data_fixed(product_obj):
                        try:
                            # Get standard product data
                            data = prepare_product_data(product_obj)
                            
                            # Remove problematic 'color' field if it exists
                            if 'color' in data:
                                self.stdout.write(f"  Removing problematic 'color' field: {data['color']}")
                                del data['color']
                            
                            return data
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  Error preparing data: {str(e)}"))
                            return None
                    
                    # Step 3: Call API client with our modified data
                    client = get_api_client()
                    if not client:
                        self.stdout.write(self.style.ERROR("  Failed to get API client"))
                        continue
                        
                    # Prepare data using our fixed function
                    api_data = prepare_product_data_fixed(product)
                    if not api_data:
                        self.stdout.write(self.style.ERROR("  Failed to prepare product data"))
                        continue
                        
                    # Display attributes for debugging
                    self.stdout.write(f"  Submitting with attributes: {json.dumps(api_data.get('attributes', []))}")
                    
                    # Submit to API
                    response = client.products.create_products([api_data])
                    
                    # Update status based on response
                    if response and isinstance(response, dict) and 'batchId' in response:
                        batch_id = response['batchId']
                        product.batch_id = batch_id
                        product.batch_status = 'processing'
                        product.save()
                        
                        success_count += 1
                        self.stdout.write(self.style.SUCCESS(f"  Successfully submitted with batch ID: {batch_id}"))
                    else:
                        error_msg = "Unknown error (no batch ID in response)"
                        if isinstance(response, dict) and 'errors' in response:
                            error_msg = str(response['errors'])
                        
                        self.stdout.write(self.style.ERROR(f"  API error: {error_msg}"))
                        product.batch_status = 'failed'
                        product.status_message = error_msg[:500]  # Truncate if too long
                        product.save()
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Error processing product {product.id}: {str(e)}"))
        
        # Report results
        if fixed_count or success_count:
            self.stdout.write(self.style.SUCCESS(
                f"Summary: Fixed attributes for {fixed_count} products, "
                f"successfully submitted {success_count} products to Trendyol"
            ))
        else:
            self.stdout.write(self.style.WARNING("No products were successfully processed"))