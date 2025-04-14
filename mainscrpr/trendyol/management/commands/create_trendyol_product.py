"""
Django management command to manually create a Trendyol product from LCWaikiki product.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from lcwaikiki.models import Product as LCWaikikiProduct
from trendyol.trendyol_client import TrendyolClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Create a Trendyol product from an existing LCWaikiki product'
    
    def add_arguments(self, parser):
        parser.add_argument('product_id', type=int, help='LCWaikiki product ID')
        parser.add_argument('--brand-id', type=int, default=None, 
                            help='Override brand ID (default: auto-detect)')
        parser.add_argument('--category-id', type=int, default=None,
                            help='Override category ID (default: auto-detect)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Do not actually submit to Trendyol')
    
    def handle(self, *args, **options):
        product_id = options['product_id']
        brand_id = options['brand_id']
        category_id = options['category_id']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.NOTICE(f"Starting product creation at {timezone.now()}"))
        
        try:
            # Get LCWaikiki product
            lcw_product = LCWaikikiProduct.objects.get(id=product_id)
            self.stdout.write(self.style.SUCCESS(f"Found LCWaikiki product: {lcw_product.title}"))
            
            # Initialize Trendyol client
            client = TrendyolClient()
            
            if not client.api_client:
                self.stdout.write(self.style.ERROR("Failed to initialize Trendyol client"))
                return
            
            # Create or get existing Trendyol product
            from trendyol.models import TrendyolProduct
            trendyol_product = TrendyolProduct.objects.filter(lcwaikiki_product=lcw_product).first()
            
            if trendyol_product:
                self.stdout.write(self.style.NOTICE(
                    f"Found existing Trendyol product: {trendyol_product.id} (Status: {trendyol_product.batch_status})"
                ))
            
            # Override brand ID if specified
            if brand_id:
                self.stdout.write(self.style.WARNING(f"Overriding brand ID to: {brand_id}"))
                if trendyol_product:
                    trendyol_product.brand_id = brand_id
                    trendyol_product.save()
            
            # Override category ID if specified
            if category_id:
                self.stdout.write(self.style.WARNING(f"Overriding category ID to: {category_id}"))
                if trendyol_product:
                    trendyol_product.category_id = category_id
                    trendyol_product.pim_category_id = category_id
                    trendyol_product.save()
            
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN - No actual API submission will be made"))
                
                # Convert to Trendyol format
                trendyol_data = client.convert_lcwaikiki_product(lcw_product, trendyol_product)
                
                if trendyol_data:
                    self.stdout.write(self.style.SUCCESS("Product conversion successful"))
                    self.stdout.write(self.style.SUCCESS(f"Title: {trendyol_data.title}"))
                    self.stdout.write(self.style.SUCCESS(f"Barcode: {trendyol_data.barcode}"))
                    self.stdout.write(self.style.SUCCESS(f"Brand ID: {trendyol_data.brand_id}"))
                    self.stdout.write(self.style.SUCCESS(f"Category ID: {trendyol_data.category_id}"))
                    self.stdout.write(self.style.SUCCESS(f"Quantity: {trendyol_data.quantity}"))
                    self.stdout.write(self.style.SUCCESS(f"Price: {trendyol_data.price}"))
                else:
                    self.stdout.write(self.style.ERROR("Failed to convert product to Trendyol format"))
            else:
                # Create or update product on Trendyol
                if not trendyol_product:
                    # Create new Trendyol product in database first
                    from django.db import transaction
                    with transaction.atomic():
                        trendyol_product = TrendyolProduct.objects.create(
                            title=lcw_product.title or "LC Waikiki Product",
                            description=lcw_product.description or lcw_product.title or "LC Waikiki Product Description",
                            barcode=lcw_product.barcode or f"LCW-{lcw_product.id}",
                            product_main_id=lcw_product.product_code or f"LCW-{lcw_product.id}",
                            stock_code=lcw_product.product_code or f"LCW-{lcw_product.id}",
                            brand_name="LCW",
                            brand_id=brand_id or 7651,  # Use provided brand ID or default
                            category_name=lcw_product.category or "Clothing",
                            category_id=category_id,  # Use provided category ID
                            pim_category_id=category_id,  # Use same category ID
                            image_url=lcw_product.image_url if hasattr(lcw_product, 'image_url') else "",
                            lcwaikiki_product=lcw_product,
                            batch_status='new',
                            status_message="Created manually via command",
                            currency_type="TRY",
                            vat_rate=18
                        )
                
                result = client.create_or_update_product(trendyol_product)
                
                if result:
                    self.stdout.write(self.style.SUCCESS(f"Successfully submitted product to Trendyol"))
                    self.stdout.write(self.style.SUCCESS(f"Batch ID: {trendyol_product.batch_id}"))
                    self.stdout.write(self.style.SUCCESS(f"Batch status: {trendyol_product.batch_status}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Failed to submit product to Trendyol"))
                    self.stdout.write(self.style.ERROR(f"Status message: {trendyol_product.status_message}"))
            
        except LCWaikikiProduct.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"LCWaikiki product with ID {product_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating product: {str(e)}"))