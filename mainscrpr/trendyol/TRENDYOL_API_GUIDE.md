# Trendyol API Integration Guide

This guide provides comprehensive information about the Trendyol API integration in this application, including configuration, troubleshooting, and usage examples.

## Configuration

### API Configuration in Admin

1. Go to the admin interface (/admin/)
2. Navigate to "Trendyol API Configurations" under the "Trendyol" section
3. Create a new configuration or edit an existing one with the following details:
   - **Name**: A descriptive name for the configuration
   - **Seller ID**: Your Trendyol seller ID (found in your Trendyol seller panel)
   - **API Key**: Your Trendyol API key
   - **API Secret**: Your Trendyol API secret
   - **Base URL**: The Trendyol API base URL (default: `https://api.trendyol.com/sapigw`)
   - **User-Agent**: Format: `{SellerID} - SelfIntegration` (e.g., `123456 - SelfIntegration`)
   - **Supplier ID**: Usually the same as Seller ID
   - **Is Active**: Check this box to make this configuration active

**Note**: Only one configuration can be active at a time. If you create multiple configurations, make sure only one has "Is Active" checked.

## API Client Usage

### Basic Usage

The `get_api_client()` function returns a configured Trendyol API client that you can use to interact with the Trendyol API:

```python
from trendyol.api_client import get_api_client

# Get the API client
client = get_api_client()

# Use the client to interact with the API
brands = client.brands.get_brands()
categories = client.categories.get_categories()
products = client.products.get_products()
```

### Product Operations

#### Creating a Product

```python
from trendyol.api_client import create_trendyol_product
from trendyol.models import TrendyolProduct

# Create a TrendyolProduct instance with required fields
product = TrendyolProduct.objects.create(
    title="Product Title",
    description="Product Description",
    barcode="UNIQUE_BARCODE",
    product_main_id="UNIQUE_MAIN_ID",
    stock_code="UNIQUE_STOCK_CODE",
    brand_name="Brand Name",
    brand_id=123,  # Must match a valid Trendyol brand ID
    category_name="Category Name",
    category_id=456,  # Must match a valid Trendyol category ID
    price=99.99,
    quantity=10,
    vat_rate=18,
    currency_type="TRY",
    image_url="https://example.com/image.jpg"
)

# Create the product on Trendyol
batch_id = create_trendyol_product(product)
```

#### Updating Price and Inventory

```python
from trendyol.api_client import update_price_and_inventory
from trendyol.models import TrendyolProduct

# Get an existing product
product = TrendyolProduct.objects.get(id=1)

# Update price and quantity
product.price = 129.99
product.quantity = 20
product.save()

# Update on Trendyol
batch_id = update_price_and_inventory(product)
```

#### Syncing a Product to Trendyol

```python
from trendyol.api_client import sync_product_to_trendyol
from trendyol.models import TrendyolProduct

# Get an existing product
product = TrendyolProduct.objects.get(id=1)

# Sync the product (create if not exists, update if exists)
success = sync_product_to_trendyol(product)
```

### Batch Processing Products

```python
from trendyol.api_client import batch_process_products, sync_product_to_trendyol
from trendyol.models import TrendyolProduct

# Get a set of products to sync
products = TrendyolProduct.objects.filter(batch_status='pending')

# Process them in batches
success_count, error_count, batch_ids = batch_process_products(
    products=products,
    process_func=sync_product_to_trendyol,
    batch_size=10,  # Process 10 products at a time
    delay=0.5  # Wait 0.5 seconds between each product
)
```

## Finding and Mapping Categories

### Finding a Category for a Product

```python
from trendyol.api_client import TrendyolCategoryFinder
from trendyol.models import TrendyolProduct

# Get a product
product = TrendyolProduct.objects.get(id=1)

# Initialize the category finder
finder = TrendyolCategoryFinder()

# Find the most appropriate category ID
category_id = finder.find_category_id(product)

# Update the product with the found category
if category_id:
    product.category_id = category_id
    product.save()
```

### Getting Required Attributes for a Category

```python
from trendyol.api_client import get_required_attributes_for_category

# Get the required attributes for a category
attributes = get_required_attributes_for_category(category_id=456)

# Use these attributes when creating a product
product.attributes = {
    "color": "Red",
    "size": "M",
    # Add other required attributes based on the category
}
product.save()
```

## Testing API Integration

### Using the Test Command

```bash
# Run all tests
python manage.py run_trendyol_tests

# Run with verbose output
python manage.py run_trendyol_tests --verbose

# Run a specific test module
python manage.py run_trendyol_tests --test-module test_api_connection

# Run a specific test case
python manage.py run_trendyol_tests --test-module test_api_connection --test-case TrendyolAPIConnectionTest

# Run a specific test method
python manage.py run_trendyol_tests --test-module test_api_connection --test-case TrendyolAPIConnectionTest --test-method test_brands_api_connection

# Include product sync tests (caution: may create actual products in Trendyol)
python manage.py run_trendyol_tests --include-product-sync

# Output results in JSON format
python manage.py run_trendyol_tests --json
```

### Checking API Connection

```bash
# Run the connection test command
python manage.py test_trendyol_api
```

## Troubleshooting

### API Connection Issues

1. **Check your API credentials**: Verify that the API key, API secret, and seller ID are correct
2. **Check your User-Agent header**: It should be in the format `{SellerID} - SelfIntegration`
3. **Check the API base URL**: It should be `https://api.trendyol.com/sapigw`
4. **Check the API logs**: Look for detailed error messages in the logs

### Product Creation Issues

1. **Missing required fields**: Ensure all required fields are present (barcode, title, productMainId, brandId, categoryId, listPrice, salePrice, vatRate, stockCode)
2. **Invalid brandId**: The brand ID must match a valid Trendyol brand ID
3. **Invalid categoryId**: The category ID must match a valid Trendyol category ID
4. **Duplicate barcode**: Each product must have a unique barcode
5. **Invalid attributes**: Check that the attributes match the category's required attributes

### Price and Inventory Update Issues

1. **Invalid barcode**: Make sure the barcode matches an existing product in Trendyol
2. **Price format**: Ensure prices are positive numbers
3. **Quantity format**: Ensure quantities are non-negative integers

## API Endpoints Reference

### Brands API

- `GET /brands` - Get all brands
- `GET /brands/by-name` - Get brand by name

### Categories API

- `GET /product-categories` - Get all categories
- `GET /product-categories/{categoryId}/attributes` - Get attributes for a specific category

### Products API

- `POST /suppliers/{supplierId}/products` - Create products
- `PUT /suppliers/{supplierId}/products` - Update existing products
- `DELETE /suppliers/{supplierId}/products` - Delete products
- `GET /suppliers/{supplierId}/products/batch-requests/{batchId}` - Get batch request status
- `GET /suppliers/{supplierId}/products` - Get products

### Inventory API

- `POST /suppliers/{supplierId}/products/price-and-inventory` - Update price and inventory for products