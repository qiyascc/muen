# Trendyol API Integration Notes

## API Status Summary

### Working Endpoints
- `integration/product/sellers/{supplier_id}/products` - Successfully retrieving product data
- `integration/inventory/sellers/{supplier_id}/products/price-and-inventory` - Successfully updating price and inventory data
- `integration/product/sellers/{supplier_id}/products/batch-requests/{batch_id}` - Successfully checking batch status

### Unavailable Endpoints (556 Server Error)
- `product/brands` - Using fallback database data
- `product/product-categories` - Using fallback database data
- `product/product-categories/{id}/attributes` - Using fallback mechanisms

## Authentication
- Basic authentication with API key and API secret
- Authorization header format: `Basic {base64_encoded(api_key:api_secret)}`

## Key API Details
- Base URL: `https://apigw.trendyol.com` (not `api.trendyol.com/sapigw`)
- Critical headers:
  - User-Agent: `{seller_id} - SelfIntegration`
  - Content-Type: `application/json`

## Implemented Solutions

### URL Formatting
- Removed leading slashes from all endpoints
- Ensured clean joining of base URL and endpoint paths
- Fixed inconsistent naming of `base_url` vs `api_url`

### Fallback Mechanisms
- Created database caching for brands and categories
- Added default data for essential entities (brands, categories)
- Implemented LC WAIKIKI fallback (brand ID 7651)

### Batch Processing
- Improved batch request handling
- Fixed UUID handling in batch request endpoint
- Added better logging for batch status updates

### Error Handling
- Enhanced error logging and handling
- Added graceful fallbacks for unavailable endpoints
- Removed unnecessary error messages for expected 556 errors

## Usage Tips

1. Always use the `get_api_client()` function to get a properly configured client
2. When working with products:
   - Ensure required attributes are included (especially color with attributeId 348)
   - Always provide proper brand ID (use 7651 for LC WAIKIKI if nothing else available)
   - Validate required fields before submission

3. For categories:
   - Use the `find_category_id` method in `TrendyolCategoryFinder` class
   - Fallback to default categories when needed

4. When running the API, first ensure you have data in the database:
   ```
   python update_api_handling.py
   ```

## Troubleshooting

1. If a product submission fails, check:
   - Required attributes (especially color)
   - Brand ID (must be valid)
   - Category ID (must be valid)
   - Required fields (barcode, title, productMainId, etc.)

2. If endpoints return 556 errors:
   - This is expected for some endpoints
   - The system will use fallback database data
   - Ensure the database has been populated with `update_api_handling.py`