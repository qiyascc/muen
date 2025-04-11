# Trendyol API Endpoint Updates

This document outlines the changes made to the Trendyol API endpoints to align with the latest Trendyol API documentation.

## Base URL Change

The base URL has been updated from `apigw.trendyol.com/integration` to `api.trendyol.com/sapigw`:

- **Old Base URL**: `https://apigw.trendyol.com/integration`
- **New Base URL**: `https://api.trendyol.com/sapigw` 

## Product API Endpoints

The product-related endpoints have been modified to include the proper path structure:

- **Old Path Pattern**: `/product/suppliers/{supplierId}/...`
- **New Path Pattern**: `/integration/product/sellers/{supplierId}/...`

### Specific Product Endpoint Changes:

1. **Create Products**:
   - Old: `/product/suppliers/{supplierId}/products`
   - New: `/integration/product/sellers/{supplierId}/products`

2. **Update Products**:
   - Old: `/product/suppliers/{supplierId}/products`
   - New: `/integration/product/sellers/{supplierId}/products`

3. **Delete Products**:
   - Old: `/product/suppliers/{supplierId}/products`
   - New: `/integration/product/sellers/{supplierId}/products`

4. **Get Products**:
   - Old: `/product/suppliers/{supplierId}/products`
   - New: `/integration/product/sellers/{supplierId}/products`

5. **Get Batch Request Status**:
   - Old: `/product/suppliers/{supplierId}/products/batch-requests/{batchRequestId}`
   - New: `/integration/product/sellers/{supplierId}/products/batch-requests/{batchRequestId}`

## Inventory API Endpoints

The inventory-related endpoints have been updated to include the correct path structure:

- **Old Path Pattern**: `/inventory/suppliers/{supplierId}/...`
- **New Path Pattern**: `/integration/inventory/sellers/{supplierId}/...`

### Specific Inventory Endpoint Changes:

1. **Update Price and Inventory**:
   - Old: `/inventory/suppliers/{supplierId}/price-and-inventory`
   - New: `/integration/inventory/sellers/{supplierId}/products/price-and-inventory`

## Brands API Endpoints

The brands endpoints have been updated to follow the current API structure:

1. **Get Brands**:
   - Old: `/brands`
   - New: `/brands/suppliers`

2. **Get Brand by Name**:
   - Old: `/brands/by-name`
   - New: `/brands/suppliers/by-name`

## Categories API Endpoints 

The categories endpoints remain the same as they were already correct:

1. **Get Categories**:
   - Path: `/product-categories`

2. **Get Category Attributes**:
   - Path: `/product-categories/{categoryId}/attributes`

## Refactoring for Maintainability

All API client classes have been enhanced with helper methods to standardize endpoint generation:

- `_get_products_endpoint()`
- `_get_batch_request_endpoint(batch_id)`
- `_get_price_inventory_endpoint()`
- `_get_brands_endpoint()`
- `_get_categories_endpoint()`
- `_get_category_attributes_endpoint(category_id)`

These helper methods make it easier to maintain the endpoint paths and provide a single place to update endpoint patterns if needed in the future.

## Verification

A comprehensive verification system has been added to test all API endpoints and ensure they match the expected patterns. The verification checks:

1. Product API endpoints
2. Inventory API endpoints
3. Brands API endpoints
4. Categories API endpoints

This verification helps confirm that all endpoints are correctly configured and aligned with Trendyol's API documentation.