import re
import json
from django.core.management.base import BaseCommand
from django.utils import timezone

from trendyol.models import TrendyolProduct
from trendyol.api_client import get_api_client, prepare_product_data


class Command(BaseCommand):
    help = 'Test Trendyol product attribute formatting including color detection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--id',
            type=int,
            help='Test a specific product by ID',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Maximum number of products to test (default: 5)',
        )

    def handle(self, *args, **options):
        product_id = options.get('id')
        limit = options.get('limit', 5)
        
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
        
        # Get products to test
        if product_id:
            products = TrendyolProduct.objects.filter(id=product_id)
            self.stdout.write(f"Testing product with ID {product_id}")
        else:
            products = TrendyolProduct.objects.all().order_by('-updated_at')[:limit]
            self.stdout.write(f"Testing up to {limit} most recently updated products")
            
        if not products:
            self.stdout.write(self.style.WARNING("No products found to test"))
            return
            
        self.stdout.write(f"Found {len(products)} products to test")
        
        # Get API client for testing
        api_client = get_api_client()
        if not api_client:
            self.stdout.write(self.style.ERROR("Failed to get API client, check configuration"))
            return
            
        self.stdout.write(self.style.SUCCESS(f"Successfully connected to API: {api_client.base_url}"))
        
        # Test each product
        for product in products:
            self.stdout.write("\n" + "="*80)
            self.stdout.write(f"Testing product {product.id}: {product.title}")
            
            # Test 1: Color detection
            self.stdout.write("\nColor Detection Test:")
            color = None
            if product.title:
                color_match = re.search(r'(Beyaz|Siyah|Mavi|Kirmizi|Pembe|Yeşil|Sarı|Mor|Gri|Kahverengi|Ekru|Bej|Lacivert|Turuncu|Krem)', 
                                       product.title, re.IGNORECASE)
                if color_match:
                    color = color_match.group(1)
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Detected color: {color} (ID: {color_id_map.get(color, 'Unknown')})"))
                else:
                    self.stdout.write(self.style.WARNING(f"  ✗ No color detected in title: {product.title}"))
            else:
                self.stdout.write(self.style.WARNING("  ✗ Product has no title"))
            
            # Test 2: Current attributes
            self.stdout.write("\nCurrent Attributes Test:")
            if product.attributes:
                self.stdout.write(f"  Current attributes: {json.dumps(product.attributes, indent=2)}")
                
                # First check if attributes is a dictionary (old format) or list (new format)
                if isinstance(product.attributes, dict):
                    self.stdout.write(self.style.WARNING("  ✗ Attributes are in dictionary format, should be list of objects with attributeId/attributeValueId"))
                    has_numeric_attrs = False
                elif isinstance(product.attributes, list):
                    # Check for proper attribute format
                    has_numeric_attrs = all(
                        isinstance(attr.get('attributeId'), int) and 
                        isinstance(attr.get('attributeValueId'), int)
                        for attr in product.attributes if 'attributeId' in attr and 'attributeValueId' in attr
                    )
                    
                    if has_numeric_attrs:
                        self.stdout.write(self.style.SUCCESS("  ✓ Attributes use proper numeric IDs"))
                    else:
                        self.stdout.write(self.style.ERROR("  ✗ Attributes do not use proper numeric IDs"))
                else:
                    self.stdout.write(self.style.ERROR("  ✗ Attributes are in an unknown format"))
                    has_numeric_attrs = False
            else:
                self.stdout.write(self.style.WARNING("  ✗ No attributes defined"))
            
            # Test 3: API data generation
            self.stdout.write("\nAPI Payload Test:")
            # Define product data preparation function without the 'color' field
            def prepare_product_data_fixed(product_obj):
                try:
                    # Get standard product data
                    data = prepare_product_data(product_obj)
                    
                    # Remove problematic 'color' field if it exists
                    if 'color' in data:
                        self.stdout.write(self.style.WARNING(f"  ✗ Found problematic 'color' field: {data['color']} (will be removed)"))
                        del data['color']
                    else:
                        self.stdout.write(self.style.SUCCESS("  ✓ No problematic 'color' field found"))
                    
                    # Check for required fields
                    required_fields = ['barcode', 'title', 'productMainId', 'brandId', 'categoryId']
                    missing_fields = [field for field in required_fields if field not in data or not data[field]]
                    
                    if missing_fields:
                        self.stdout.write(self.style.ERROR(f"  ✗ Missing required fields: {', '.join(missing_fields)}"))
                    else:
                        self.stdout.write(self.style.SUCCESS("  ✓ All required fields present"))
                    
                    # Check image URLs
                    if 'images' in data and data['images']:
                        image_count = len(data['images'])
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Found {image_count} images"))
                    else:
                        self.stdout.write(self.style.ERROR("  ✗ No images found"))
                    
                    return data
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ✗ Error preparing data: {str(e)}"))
                    return None
            
            # Prepare data using our fixed function
            api_data = prepare_product_data_fixed(product)
            if api_data:
                # Show final attribute format
                if 'attributes' in api_data and api_data['attributes']:
                    self.stdout.write(f"  Final attributes: {json.dumps(api_data['attributes'], indent=2)}")
                else:
                    self.stdout.write(self.style.WARNING("  ✗ No attributes in final payload"))
            
            # Test 4: Suggested improvements
            self.stdout.write("\nSuggested Improvements:")
            
            # If we detected a color but it's not in attributes, suggest adding it
            if color and color in color_id_map:
                color_id = color_id_map[color]
                
                # Check if this color is already in attributes
                has_color_attr = False
                if product.attributes:
                    # Handle different attribute formats
                    if isinstance(product.attributes, dict) and 'color' in product.attributes:
                        has_color_attr = True
                    elif isinstance(product.attributes, list):
                        for attr in product.attributes:
                            if isinstance(attr, dict) and attr.get('attributeId') == 348:  # 348 is the attributeId for color
                                has_color_attr = True
                                break
                
                if not has_color_attr:
                    self.stdout.write(self.style.WARNING(
                        f"  → Add color attribute: {{'attributeId': 348, 'attributeValueId': {color_id}}}"
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS("  ✓ Product already has color attribute"))
            
            # If the attribute format is not numeric, suggest fixing
            if product.attributes and not has_numeric_attrs:
                self.stdout.write(self.style.WARNING(
                    "  → Fix attribute format to use numeric IDs for both 'attributeId' and 'attributeValueId'"
                ))
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("Attribute testing complete"))