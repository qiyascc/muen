import os
import django
import json
import uuid
from loguru import logger
from decimal import Decimal

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Now import the models and functions
from trendyol.models import TrendyolProduct, TrendyolAPIConfig, TrendyolCategory, TrendyolBrand
from trendyol.api_client import (
    create_trendyol_product, get_api_client, prepare_product_data, 
    fetch_categories, fetch_brands, TrendyolCategoryFinder
)

# Check if we have active API config
api_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
if not api_config:
    print("No active Trendyol API configuration found!")
    exit(1)
    
print(f"Using API config: {api_config.name} (ID: {api_config.id})")

# Let's first check if we have categories and brands in our database
print("\n== Checking Trendyol Categories ==")
categories_count = TrendyolCategory.objects.count()
print(f"Categories in database: {categories_count}")
if categories_count == 0:
    print("Fetching categories from Trendyol API...")
    categories = fetch_categories()
    print(f"Fetched {len(categories)} categories")

print("\n== Checking Trendyol Brands ==")
brands_count = TrendyolBrand.objects.count()
print(f"Brands in database: {brands_count}")
if brands_count == 0:
    print("Fetching brands from Trendyol API...")
    brands = fetch_brands()
    print(f"Fetched {len(brands)} brands")

# Find a valid clothing category for testing
valid_category = TrendyolCategory.objects.filter(name__icontains='tişört').first()
if valid_category:
    print(f"\nFound valid category: {valid_category.name} (ID: {valid_category.category_id})")
else:
    valid_category = TrendyolCategory.objects.filter(name__icontains='bebek').first()
    if valid_category:
        print(f"\nFound valid category: {valid_category.name} (ID: {valid_category.category_id})")

# Find LCW brand
lcw_brand = TrendyolBrand.objects.filter(name__icontains='lcw').first()
if lcw_brand:
    print(f"Found LCW brand: {lcw_brand.name} (ID: {lcw_brand.brand_id})")

# Find failed products
failed_product = TrendyolProduct.objects.filter(batch_status='failed').last()
if not failed_product:
    print("\nNo failed products found!")
    print("Creating a test product to diagnose issues...")
    
    # Create test product with valid data
    test_product = TrendyolProduct(
        title="LCW TEST T-Shirt - API Diagnostic",
        description="Test product for API diagnostics",
        barcode=f"LCWTEST{uuid.uuid4().hex[:8]}",  # Generate unique barcode
        product_main_id=f"TEST{uuid.uuid4().hex[:8]}",  # Generate unique product ID
        stock_code=f"TEST{uuid.uuid4().hex[:6]}",  # Generate unique stock code
        brand_name="LCW",
        brand_id=lcw_brand.brand_id if lcw_brand else None,
        category_name=valid_category.name if valid_category else "T-shirt",
        category_id=valid_category.category_id if valid_category else None,
        price=Decimal('199.99'),
        quantity=10,
        vat_rate=18,
        currency_type="TRY",
        image_url="https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20224/5841125/l_20224-w4bi51z8-ct5_a.jpg",
        additional_images=[],
        attributes={"color": "Blue"}
    )
    test_product.save()
    failed_product = test_product
    print(f"Created test product: {test_product.title} (ID: {test_product.id})")
else:
    print(f"\nTesting with existing product: {failed_product.title} (ID: {failed_product.id})")
    print(f"Current status: {failed_product.batch_status}")
    print(f"Error message: {failed_product.status_message}")

# Update the product with valid data if it has issues
if valid_category and failed_product.category_id != valid_category.category_id:
    print(f"\nUpdating product with valid category ID: {valid_category.category_id}")
    failed_product.category_id = valid_category.category_id
    failed_product.category_name = valid_category.name
    failed_product.save()

if lcw_brand and failed_product.brand_id != lcw_brand.brand_id:
    print(f"Updating product with valid brand ID: {lcw_brand.brand_id}")
    failed_product.brand_id = lcw_brand.brand_id
    failed_product.brand_name = lcw_brand.name
    failed_product.save()

# Make sure barcode is valid
if failed_product.barcode in ["K", ""]:
    new_barcode = f"LCWTEST{uuid.uuid4().hex[:8]}"
    print(f"Updating product with valid barcode: {new_barcode}")
    failed_product.barcode = new_barcode
    failed_product.save()

# Make sure product_main_id is valid
if failed_product.product_main_id in ["K", ""]:
    new_product_main_id = f"TEST{uuid.uuid4().hex[:8]}"
    print(f"Updating product with valid product_main_id: {new_product_main_id}")
    failed_product.product_main_id = new_product_main_id
    failed_product.save()

# Make sure stock_code is valid
if failed_product.stock_code in ["K", ""]:
    new_stock_code = f"TEST{uuid.uuid4().hex[:6]}"
    print(f"Updating product with valid stock_code: {new_stock_code}")
    failed_product.stock_code = new_stock_code
    failed_product.save()

# Initialize API client
client = get_api_client()
if not client:
    print("Could not initialize API client")
    exit(1)

# Fetch attributes for the category
cat_finder = TrendyolCategoryFinder(client)
if valid_category and failed_product.category_id == valid_category.category_id:
    print(f"\nFetching attributes for category {valid_category.name} (ID: {valid_category.category_id})...")
    attributes = cat_finder.get_category_attributes(valid_category.category_id)
    if attributes:
        print(f"Found {len(attributes)} attributes for this category")
        
        # Add required attributes to our product
        print("Adding required attributes to product...")
        required_attributes = []
        
        for attr in attributes:
            attr_name = attr.get('name', '')
            attr_id = attr.get('id')
            attr_required = attr.get('required', False)
            
            if attr_required:
                print(f"Required attribute: {attr_name} (ID: {attr_id})")
                
                # Get attribute values
                values = attr.get('attributeValues', [])
                if values:
                    first_value = values[0]
                    value_id = first_value.get('id')
                    value_name = first_value.get('name', '')
                    
                    print(f"  Using value: {value_name} (ID: {value_id})")
                    
                    # Add to attributes
                    required_attributes.append({
                        "attributeId": attr_id,
                        "attributeValueId": value_id
                    })
        
        # Add color attribute if available
        if 'color' in failed_product.attributes:
            color_value = failed_product.attributes.get('color')
            if color_value:
                required_attributes.append({
                    "attributeId": "color",
                    "attributeValueId": color_value
                })
                print(f"Added color attribute: {color_value}")
        
        # Save attributes to product
        failed_product.attributes = required_attributes
        failed_product.save()
        print(f"Added {len(required_attributes)} attributes to product")

# We already have client initialized above, no need to get it again
if client:
    try:
        # Prepare the product for submission
        product_data = prepare_product_data(failed_product)
        print("\nProduct data for Trendyol API:")
        print(json.dumps(product_data, indent=2, default=str))
        
        # Check required fields
        required_fields = ['barcode', 'title', 'productMainId', 'brandId', 'categoryId',
                           'listPrice', 'salePrice', 'vatRate', 'stockCode',
                           'description', 'currencyType']
        
        print("\nChecking required fields:")
        for field in required_fields:
            if field not in product_data or product_data[field] is None:
                print(f"❌ MISSING: {field}")
            else:
                print(f"✓ PRESENT: {field} = {product_data[field]}")
        
        # Attributes check
        if 'attributes' not in product_data or not product_data['attributes']:
            print("❌ MISSING: attributes")
        else:
            attributes = product_data['attributes']
            print(f"\nAttributes ({len(attributes)}):")
            for attr in attributes:
                if isinstance(attr, dict):
                    print(f"  - {attr.get('attributeId')}: {attr.get('attributeValueId')}")
                else:
                    print(f"  - Invalid attribute: {attr}")
        
        # Images check
        if 'images' not in product_data or not product_data['images']:
            print("❌ MISSING: images")
        else:
            images = product_data['images']
            print(f"\nImages ({len(images)}):")
            for img in images:
                if isinstance(img, dict) and 'url' in img:
                    print(f"  - {img['url']}")
                else:
                    print(f"  - Invalid image: {img}")
        
        # Gender check (important for many categories)
        if 'gender' not in product_data or not product_data['gender']:
            print("❌ MISSING: gender")
        else:
            print(f"✓ PRESENT: gender = {product_data['gender']}")
        
        # Try to create the product
        print("\nAttempting to create product on Trendyol...")
        result = create_trendyol_product(failed_product)
        print(f"Result: {result}")
        
        # Check result
        if result:
            print("✅ SUCCESS: Product was successfully submitted to Trendyol")
        else:
            print("❌ FAILED: Could not create product on Trendyol")
            print(f"Error message: {failed_product.status_message}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
else:
    print("Could not initialize API client")