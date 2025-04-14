# Trendyol Integration

This module provides integration with the Trendyol Marketplace API, allowing products from LCWaikiki to be automatically synchronized with Trendyol.

## Architecture

The integration consists of several components:

1. `api_integration.py` - Low-level API client for making requests to Trendyol
2. `helpers.py` - Helper functions for data conversion and transformation
3. `trendyol_client.py` - Higher-level client for Trendyol operations
4. `sync_manager.py` - Manager for synchronizing products between LCWaikiki and Trendyol
5. Management commands for various operations

## Management Commands

The following management commands are available:

### Fetch data from Trendyol

```bash
python manage.py fetch_trendyol_data --data-type brands
python manage.py fetch_trendyol_data --data-type categories
python manage.py fetch_trendyol_data --data-type all
```

### Synchronize products from LCWaikiki to Trendyol

```bash
python manage.py sync_from_lcwaikiki --max-items 100 --batch-size 10
```

### Check batch status

```bash
python manage.py check_batch_status
python manage.py check_batch_status --batch-id <BATCH-ID>
```

### Create a Trendyol product from an LCWaikiki product

```bash
python manage.py create_trendyol_product <PRODUCT-ID>
```

## Configuration

The integration uses the `TrendyolAPIConfig` model to store API credentials. Make sure you have a valid configuration set up before using the integration.

Required credentials:
- `supplier_id` - Your Trendyol seller ID
- `api_key` - Your Trendyol API key
- `api_secret` - Your Trendyol API secret
- `base_url` - The Trendyol API base URL (defaults to `https://apigw.trendyol.com/integration/`)

## Product Synchronization Process

1. LCWaikiki products are fetched from the database
2. For each product, a corresponding Trendyol product is created or updated
3. The product is converted to Trendyol format with appropriate attributes
4. The product is submitted to Trendyol using the API
5. Batch status is checked to verify successful submission

## Error Handling

The integration includes robust error handling and logging. All API operations are logged to `trendyol_integration.log` and also to the standard output. Failed product submissions are marked as failed in the database with an appropriate error message.

## API Limitations

Note that the Trendyol API has the following limitations:
- Maximum 1000 items per update
- Maximum 20,000 items maximum stock
- Maximum 50 requests per 10 seconds