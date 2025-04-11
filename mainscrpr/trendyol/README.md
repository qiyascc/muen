# Trendyol API Integration

This module provides a comprehensive integration with the Trendyol API for product management and synchronization.

## Features

- **API Client**: Robust API client with authentication, endpoint management, and error handling
- **Product Management**: Create, update, and delete products on Trendyol 
- **Batch Processing**: Track batch operations with status checking
- **Attribute Handling**: Proper color mapping with numeric IDs and attribute formatting
- **Automatic Retry**: Tools for retrying failed product submissions
- **Admin Integration**: Admin actions for synchronization and management

## Command Line Tools

### Retry Failed Products

You can retry failed product submissions using the command line tool:

```bash
python manage.py retry_failed_trendyol_products --limit 10
```

Options:
- `--all`: Process all products, not just failed ones
- `--limit N`: Limit processing to N products (default: 10)

### Other Commands

- `python manage.py sync_trendyol`: Run Trendyol synchronization
- `python manage.py test_trendyol_api`: Test Trendyol API connection

## Admin Actions

The following admin actions are available in the TrendyolProduct admin interface:

1. **Sync with Trendyol**: Submit selected products to Trendyol
2. **Check Sync Status**: Check synchronization status for products with batch IDs
3. **Retry Failed Products**: Retry failed products with improved attribute handling
4. **Refresh Product Data**: Refresh product data from LCWaikiki source

## API Notes

- The API base URL is `https://apigw.trendyol.com/integration`
- Authentication uses Basic Auth with the Trendyol seller ID, API key, and API secret
- The User-Agent header format should be `{seller_id} - SelfIntegration`
- Color attributes must use numeric IDs (like 348 for color attributeId)
- Do not include a separate "color" field outside the attributes array

## Color ID Mapping

For proper Trendyol integration, use these numeric color IDs:

```
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
```

## Troubleshooting

If products fail to send to Trendyol, check:

1. Attribute format - must use numeric IDs
2. Remove any redundant "color" field outside the attributes array
3. Check image URLs are valid and accessible 
4. Verify that required fields like barcode, title, and price are present
5. Review API response errors in the product's status_message field