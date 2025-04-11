# Trendyol API Integration Tests

This directory contains comprehensive tests for the Trendyol API integration. The tests are designed to verify that all aspects of the Trendyol API integration are working correctly.

## Test Modules

1. **test_api_connection.py**: Tests for API connectivity, authentication, and basic API operations.
2. **test_product_operations.py**: Tests for product creation, updating, and price/inventory management.
3. **test_category_and_attributes.py**: Tests for category mapping, finding, and attribute handling.

## Running Tests

### Using Management Commands

The easiest way to run the tests is using the provided management commands:

```bash
# Run verification tests
python manage.py test_trendyol_api

# Run full test suite
python manage.py run_trendyol_tests

# Run tests with verbose output
python manage.py run_trendyol_tests --verbose

# Include product sync tests (caution: may create real products in Trendyol)
python manage.py run_trendyol_tests --include-product-sync

# Run specific test module
python manage.py run_trendyol_tests --test-module test_api_connection

# Run specific test case
python manage.py run_trendyol_tests --test-module test_api_connection --test-case TrendyolAPIConnectionTest

# Run specific test method
python manage.py run_trendyol_tests --test-module test_api_connection --test-case TrendyolAPIConnectionTest --test-method test_brands_api_connection

# Output results in JSON format
python manage.py run_trendyol_tests --json
```

### Using the Verification Script

You can also run the verification script directly:

```bash
# Run the verification script
python run_trendyol_verification.py

# Run with verbose output
python run_trendyol_verification.py --verbose

# Include product operations tests
python run_trendyol_verification.py --include-product-ops
```

## Test Categories

### API Connection Tests

These tests verify that the API client can connect to Trendyol's API and perform basic operations:

- Test API configuration
- Test API client initialization
- Test User-Agent header
- Test connection to Brands API
- Test connection to Categories API
- Test connection to Products API

### Product Operations Tests

These tests verify that product operations work correctly:

- Test product data preparation
- Test price and inventory update format
- Test product validation
- Test product model functionality

### Category and Attributes Tests

These tests verify that category mapping and attribute handling work correctly:

- Test category finder initialization
- Test fetching categories
- Test category tree transformation
- Test getting category attributes
- Test finding category IDs
- Test similarity calculation between strings

## Adding New Tests

To add new tests, follow these steps:

1. Create a new test file in this directory with a name starting with `test_`.
2. Import the necessary modules and classes.
3. Create a test class that inherits from `django.test.TestCase`.
4. Add test methods that start with `test_`.
5. Run the tests to verify that they work correctly.

Example:

```python
import django
from django.test import TestCase
from trendyol.api_client import get_api_client

class MyNewTests(TestCase):
    def setUp(self):
        # Set up test environment
        self.api_client = get_api_client()

    def test_some_feature(self):
        # Test some feature
        result = self.api_client.some_method()
        self.assertTrue(result)
```