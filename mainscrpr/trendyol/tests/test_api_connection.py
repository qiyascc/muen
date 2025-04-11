"""
Comprehensive tests for Trendyol API connection and authentication.
"""
import os
import django
import unittest
from django.test import TestCase
from django.conf import settings

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.models import TrendyolAPIConfig
from trendyol.api_client import TrendyolApi, get_api_client

class TrendyolAPIConnectionTest(TestCase):
    """Test Trendyol API connection and authentication"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Use the existing API configuration from the database
        cls.api_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not cls.api_config:
            raise ValueError("No active Trendyol API configuration found. Please create one in the admin interface.")
        
        # Initialize API client
        cls.api_client = get_api_client()
        if not cls.api_client:
            raise ValueError("Failed to initialize API client. Check API configuration settings.")
    
    def test_api_config_exists(self):
        """Test that API configuration exists and has required fields"""
        self.assertIsNotNone(self.api_config)
        self.assertTrue(self.api_config.seller_id)
        self.assertTrue(self.api_config.api_key)
        self.assertTrue(self.api_config.api_secret)
        self.assertTrue(self.api_config.base_url)
    
    def test_api_client_initialization(self):
        """Test API client initialization"""
        self.assertIsNotNone(self.api_client)
        self.assertEqual(self.api_client.api_url, self.api_config.base_url)
        self.assertEqual(self.api_client.supplier_id, 
                         self.api_config.supplier_id or self.api_config.seller_id)
        
        # Check if the API client has all required API instances
        self.assertIsNotNone(self.api_client.brands)
        self.assertIsNotNone(self.api_client.categories)
        self.assertIsNotNone(self.api_client.products)
        self.assertIsNotNone(self.api_client.inventory)
    
    def test_user_agent_header(self):
        """Test that User-Agent header is set correctly"""
        expected_user_agent = (self.api_config.user_agent or 
                              f"{self.api_config.seller_id} - SelfIntegration")
        self.assertEqual(self.api_client.user_agent, expected_user_agent)
    
    def test_brands_api_connection(self):
        """Test connection to Brands API"""
        response = self.api_client.brands.get_brands(page=0, size=10)
        self.assertIn('brands', response)
        self.assertTrue(len(response['brands']) > 0)
    
    def test_categories_api_connection(self):
        """Test connection to Categories API"""
        response = self.api_client.categories.get_categories()
        self.assertIn('categories', response)
        self.assertTrue(len(response['categories']) > 0)
    
    def test_get_category_attributes(self):
        """Test getting category attributes"""
        # First get a valid category ID from the categories API
        categories_response = self.api_client.categories.get_categories()
        category_id = categories_response['categories'][0]['id']
        
        # Now get attributes for this category
        response = self.api_client.categories.get_category_attributes(category_id)
        self.assertIn('categoryAttributes', response)
    
    def test_products_api_connection(self):
        """Test connection to Products API"""
        # Test listing products
        response = self.api_client.products.get_products(page=0, size=10)
        # The response format may vary depending on whether you have products,
        # but it should be a success response and not an error
        self.assertNotIn('error', response)