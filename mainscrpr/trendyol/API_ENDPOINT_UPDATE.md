# Trendyol API Endpoint Update Documentation

## Overview
This document outlines updates made to the Trendyol API integration endpoints to align with the latest API documentation.

## Changes Made

### Base URL Update
- Updated from: `https://apigw.trendyol.com/integration`
- To: `https://api.trendyol.com/sapigw`

### Endpoints Updated

#### Product Operations
1. **Create Products**
   - Old: `/sellers/{sellerId}/products`
   - New: `/integration/product/sellers/{sellerId}/products`
   - Method: POST

2. **Update Products**
   - Old: `/sellers/{sellerId}/products`
   - New: `/integration/product/sellers/{sellerId}/products`
   - Method: PUT

3. **Delete Products**
   - Old: `/sellers/{sellerId}/products`
   - New: `/integration/product/sellers/{sellerId}/products`
   - Method: DELETE

4. **Get Batch Request Status**
   - Old: `/sellers/{sellerId}/products/batch-requests/{batchId}`
   - New: `/integration/product/sellers/{sellerId}/products/batch-requests/{batchId}`
   - Method: GET

5. **Get Products**
   - Old: `/sellers/{sellerId}/products`
   - New: `/integration/product/sellers/{sellerId}/products`
   - Method: GET
   - Params: barcode, approved, page, size

#### Inventory Operations
1. **Update Price and Inventory**
   - Old: `/sellers/{sellerId}/products/price-and-inventory`
   - New: `/integration/inventory/sellers/{sellerId}/products/price-and-inventory`
   - Method: POST

## Authentication
- Added required User-Agent header: `{sellerId} - SelfIntegration`
- Basic authentication remains unchanged (uses API key and secret)

## Testing and Verification
The API update includes comprehensive testing to ensure all endpoints are functioning correctly with the new URL structure. The following tests were performed:

1. API connection and authentication verification
2. Product operations (create, update, delete, get)
3. Batch request status checks
4. Price and inventory updates

## Migration Impact
- No database schema changes were required
- Existing product data remains compatible with the new API structure
- API configuration was updated in the database

## Troubleshooting
If you encounter API errors after this update, check the following:

1. Verify the API configuration in the admin panel has the correct base URL
2. Check that the User-Agent header is correctly set
3. Review the logs for any detailed error messages from the API
4. Ensure supplier ID/seller ID is correctly configured