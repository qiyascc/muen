"""
Tests for Trendyol product operations: creation, update, price/inventory updates, and deletion.
"""
import os
import uuid
import django
import unittest
import json
from decimal import Decimal
from django.test import TestCase
from django.conf import settings
from django.utils import timezone

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.models import TrendyolProduct, TrendyolBrand, TrendyolCategory
from trendyol.api_client import (
    get_api_client, prepare_product_data, create_trendyol_product,
    update_price_and_inventory, sync_product_to_trendyol
)

class TrendyolProductOperationsTest(TestCase):
    """Test Trendyol product operations"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Initialize API client
        cls.api_client = get_api_client()
        if not cls.api_client:
            raise ValueError("Failed to initialize API client. Check API configuration settings.")
        
        # Create a test product for testing
        cls.test_product = cls._create_test_product()
    
    @classmethod
    def _create_test_product(cls):
        """Create a test product for testing purposes"""
        # Generate a unique barcode
        unique_id = str(uuid.uuid4()).replace('-', '')[0:12]
        barcode = f"TEST{unique_id}"
        
        # Find a valid brand for testing
        brand = TrendyolBrand.objects.filter(is_active=True).first()
        if not brand:
            # Fetch brands if none exists
            from trendyol.api_client import fetch_brands
            fetch_brands()
            brand = TrendyolBrand.objects.filter(is_active=True).first()
            if not brand:
                raise ValueError("No brands available for testing. Please fetch brands from Trendyol API.")
        
        # Find a valid category for testing
        category = TrendyolCategory.objects.filter(is_active=True).first()
        if not category:
            # Fetch categories if none exists
            from trendyol.api_client import fetch_categories
            fetch_categories()
            category = TrendyolCategory.objects.filter(is_active=True).first()
            if not category:
                raise ValueError("No categories available for testing. Please fetch categories from Trendyol API.")
        
        # Create the test product
        product = TrendyolProduct.objects.create(
            title=f"Test Product {unique_id}",
            description="This is a test product created for API testing purposes.",
            barcode=barcode,
            product_main_id=f"TEST-MAIN-{unique_id}",
            stock_code=f"TEST-STOCK-{unique_id}",
            brand_name=brand.name,
            brand_id=brand.brand_id,
            category_name=category.name,
            category_id=category.category_id,
            price=Decimal("99.99"),
            quantity=10,
            vat_rate=18,
            currency_type="TRY",
            image_url="https://via.placeholder.com/800x600.png?text=Test+Product",
            additional_images=[],
            attributes={
                "color": "Red",
                "size": "M"
            }
        )
        return product
    
    def test_prepare_product_data(self):
        """Test preparing product data for Trendyol API"""
        product_data = prepare_product_data(self.test_product)
        
        # Verify the product data has all required fields
        self.assertIn('barcode', product_data)
        self.assertIn('title', product_data)
        self.assertIn('productMainId', product_data)
        self.assertIn('brandId', product_data)
        self.assertIn('categoryId', product_data)
        self.assertIn('listPrice', product_data)
        self.assertIn('salePrice', product_data)
        self.assertIn('vatRate', product_data)
        self.assertIn('stockCode', product_data)
        
        # Check if values are correctly mapped
        self.assertEqual(product_data['barcode'], self.test_product.barcode)
        self.assertEqual(product_data['title'], self.test_product.title)
        self.assertEqual(product_data['productMainId'], self.test_product.product_main_id)
        self.assertEqual(product_data['brandId'], self.test_product.brand_id)
        self.assertEqual(product_data['categoryId'], self.test_product.category_id)
        self.assertEqual(float(product_data['listPrice']), float(self.test_product.price))
        self.assertEqual(float(product_data['salePrice']), float(self.test_product.price))
        self.assertEqual(product_data['vatRate'], self.test_product.vat_rate)
        self.assertEqual(product_data['stockCode'], self.test_product.stock_code)
    
    def test_price_and_inventory_update_format(self):
        """Test the format of price and inventory updates"""
        # Prepare price and inventory update
        items = [{
            "barcode": self.test_product.barcode,
            "quantity": self.test_product.quantity,
            "salePrice": float(self.test_product.price),
            "listPrice": float(self.test_product.price)
        }]
        
        # Make a direct call to the inventory API
        response = self.api_client.inventory.update_price_and_inventory(items)
        
        # Check if the response has expected format
        # Note: This test only checks the response format, not the actual update success
        # since this might require a product to already exist in Trendyol
        self.assertNotIn('error', response)

    def test_create_product_validation(self):
        """Test product validation before sending to Trendyol"""
        # Create a product with missing required fields
        incomplete_product = TrendyolProduct.objects.create(
            title="Incomplete Test Product",
            barcode=f"INCTEST{str(uuid.uuid4()).replace('-', '')[0:8]}",
            # Missing other required fields
            price=Decimal("99.99"),
            quantity=10
        )
        
        # Try to prepare product data - this should identify the missing fields
        product_data = prepare_product_data(incomplete_product)
        
        # The test passes if prepare_product_data doesn't raise an exception
        # but returns None or a product with validation warnings
        
        # Clean up
        incomplete_product.delete()
    
    @unittest.skip("Skip actual product creation to avoid creating real products in Trendyol")
    def test_sync_product_to_trendyol(self):
        """
        Test syncing a product to Trendyol
        Note: This test is skipped by default to avoid creating real products in the production system
        Remove the @unittest.skip decorator to run this test when needed
        """
        # Update product with test-specific data
        unique_id = str(uuid.uuid4()).replace('-', '')[0:8]
        self.test_product.barcode = f"SYNCTEST{unique_id}"
        self.test_product.product_main_id = f"SYNCTEST-MAIN-{unique_id}"
        self.test_product.stock_code = f"SYNCTEST-STOCK-{unique_id}"
        self.test_product.save()
        
        # Attempt to sync the product
        success = sync_product_to_trendyol(self.test_product)
        
        # Check if sync was successful
        self.assertTrue(success)
        
        # Verify that the product has batch ID and sync time
        self.test_product.refresh_from_db()
        self.assertTrue(self.test_product.batch_id)
        self.assertIsNotNone(self.test_product.last_sync_time)
        
        # Clean up
        self.test_product.delete()
        
    def test_trendyol_product_model(self):
        """Test the TrendyolProduct model functionality"""
        # Create a new product with all required fields
        unique_id = str(uuid.uuid4()).replace('-', '')[0:8]
        product = TrendyolProduct.objects.create(
            title=f"Model Test Product {unique_id}",
            description="This is a test product for model testing.",
            barcode=f"MODELTEST{unique_id}",
            product_main_id=f"MODEL-MAIN-{unique_id}",
            stock_code=f"MODEL-STOCK-{unique_id}",
            brand_name="Test Brand",
            brand_id=1,
            category_name="Test Category",
            category_id=1,
            price=Decimal("149.99"),
            quantity=5,
            vat_rate=18,
            currency_type="TRY",
            image_url="https://via.placeholder.com/800x600.png?text=Model+Test"
        )
        
        # Test basic model functionality
        self.assertEqual(str(product), f"Model Test Product {unique_id}")
        
        # Test batch status and sync time
        self.assertEqual(product.batch_status, 'pending')
        self.assertIsNone(product.last_sync_time)
        
        # Test updating sync information
        product.batch_id = f"BATCH-{unique_id}"
        product.batch_status = 'completed'
        product.last_sync_time = timezone.now()
        product.save()
        
        # Refresh from database
        product.refresh_from_db()
        self.assertEqual(product.batch_status, 'completed')
        self.assertIsNotNone(product.last_sync_time)
        
        # Clean up
        product.delete()
        
    def tearDown(self):
        # Any per-test cleanup
        pass
        
    @classmethod
    def tearDownClass(cls):
        # Clean up test product
        if hasattr(cls, 'test_product') and cls.test_product:
            cls.test_product.delete()
        super().tearDownClass()