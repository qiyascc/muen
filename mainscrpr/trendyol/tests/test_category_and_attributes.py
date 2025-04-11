"""
Tests for Trendyol category mapping and attribute handling functionality.
"""
import os
import django
import unittest
from django.test import TestCase
from django.conf import settings
import json

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.models import TrendyolProduct, TrendyolCategory, TrendyolBrand
from trendyol.api_client import (
    get_api_client, TrendyolCategoryFinder, 
    get_required_attributes_for_category, find_best_category_match
)

class TrendyolCategoryAndAttributesTest(TestCase):
    """Test Trendyol category mapping and attribute handling"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Initialize API client
        cls.api_client = get_api_client()
        if not cls.api_client:
            raise ValueError("Failed to initialize API client. Check API configuration settings.")
        
        # Initialize category finder
        cls.category_finder = TrendyolCategoryFinder(cls.api_client)
        
        # Make sure we have some categories to work with
        cls._ensure_categories_exist()
        
        # Get a sample product to test with
        cls.product = TrendyolProduct.objects.first()
        if not cls.product:
            # If no product exists, create a test product
            cls.product = cls._create_test_product()
    
    @classmethod
    def _ensure_categories_exist(cls):
        """Ensure there are categories in the database for testing"""
        if TrendyolCategory.objects.count() == 0:
            # Fetch categories from API
            from trendyol.api_client import fetch_categories
            categories = fetch_categories()
            if not categories:
                raise ValueError("Failed to fetch categories from Trendyol API.")
    
    @classmethod
    def _create_test_product(cls):
        """Create a test product for testing purposes"""
        # Find a valid brand
        brand = TrendyolBrand.objects.filter(is_active=True).first()
        if not brand:
            # Fetch brands if none exists
            from trendyol.api_client import fetch_brands
            fetch_brands()
            brand = TrendyolBrand.objects.filter(is_active=True).first()
            if not brand:
                raise ValueError("No brands available for testing.")
        
        # Find a valid category
        category = TrendyolCategory.objects.filter(is_active=True).first()
        if not category:
            raise ValueError("No categories available for testing.")
        
        # Create test product
        product = TrendyolProduct.objects.create(
            title="Category Test T-Shirt",
            description="This is a test product for category mapping.",
            barcode="CATTEST12345",
            product_main_id="CATTEST-MAIN-12345",
            stock_code="CATTEST-STOCK-12345",
            brand_name=brand.name,
            brand_id=brand.brand_id,
            category_name="T-shirt",  # Use a name that should match a valid category
            price=99.99,
            quantity=10,
            vat_rate=18,
            currency_type="TRY"
        )
        return product
    
    def test_category_finder_initialization(self):
        """Test category finder initialization"""
        self.assertIsNotNone(self.category_finder)
        self.assertIsNotNone(self.category_finder.api_client)
    
    def test_fetch_all_categories(self):
        """Test fetching all categories"""
        categories = self.category_finder._fetch_all_categories()
        self.assertTrue(len(categories) > 0)
    
    def test_transform_db_categories(self):
        """Test transforming database categories to a tree structure"""
        # Get categories from DB
        db_categories = list(TrendyolCategory.objects.filter(is_active=True).values('category_id', 'name', 'parent_id'))
        
        # Transform to tree structure
        tree = self.category_finder._transform_db_categories(db_categories)
        
        # Verify that it's a non-empty list
        self.assertTrue(len(tree) > 0)
        
        # Verify that top-level categories have subCategories list
        self.assertIn('subCategories', tree[0])
    
    def test_get_category_attributes(self):
        """Test getting category attributes"""
        # Get a valid category ID from the database
        category = TrendyolCategory.objects.filter(is_active=True).first()
        self.assertIsNotNone(category)
        
        # Get attributes for this category
        attributes = self.category_finder.get_category_attributes(category.category_id)
        
        # We can't guarantee that any category has attributes, but the function should not error
        # and should return a list (possibly empty)
        self.assertIsInstance(attributes, list)
    
    def test_find_category_id_by_name(self):
        """Test finding category ID by name"""
        # Choose a common category name that should exist
        category_name = "T-shirt"
        
        # Create a product with this category name
        test_product = TrendyolProduct.objects.create(
            title="Test T-Shirt",
            description="Test product for category finding.",
            barcode="FINDCAT12345",
            category_name=category_name,
            price=99.99,
            quantity=10
        )
        
        try:
            # Try to find the category ID
            category_id = self.category_finder.find_category_id(test_product)
            
            # We can't guarantee the exact category ID, but it should return something
            # if categories are properly set up in the database
            if TrendyolCategory.objects.filter(name__icontains=category_name).exists():
                self.assertIsNotNone(category_id)
        finally:
            # Clean up
            test_product.delete()
    
    def test_find_category_with_keywords(self):
        """Test finding category with keywords in title/description"""
        # Test products with different keywords
        test_cases = [
            {"title": "Men's Blue T-Shirt", "expected_keywords": ["men", "t-shirt"]},
            {"title": "Women's Summer Dress", "expected_keywords": ["women", "dress"]},
            {"title": "Kids Jeans Pants", "expected_keywords": ["çocuk", "jeans", "pants"]}
        ]
        
        for test_case in test_cases:
            # Create a test product
            test_product = TrendyolProduct.objects.create(
                title=test_case["title"],
                description=f"Test product for {test_case['title']}",
                barcode=f"KEYWORD{test_case['title'].replace(' ', '')[0:8]}",
                price=99.99,
                quantity=10
            )
            
            try:
                # Try to find the category ID
                category_id = self.category_finder.find_category_id(test_product)
                
                # We're just testing that it returns something without error
                # The actual category ID will depend on the database state
            finally:
                # Clean up
                test_product.delete()
    
    def test_get_required_attributes(self):
        """Test getting required attributes for a category"""
        # Get a valid category ID from the database
        category = TrendyolCategory.objects.filter(is_active=True).first()
        self.assertIsNotNone(category)
        
        # Get required attributes for this category
        required_attrs = self.category_finder.get_required_attributes(category.category_id)
        
        # Required attributes should be a list (possibly empty)
        self.assertIsInstance(required_attrs, list)
    
    def test_helper_functions(self):
        """Test helper functions for category and attribute handling"""
        # Test find_best_category_match
        if self.product:
            category_id = find_best_category_match(self.product)
            
            # If the product has a category name, we should find a match
            if self.product.category_name:
                self.assertIsNotNone(category_id)
        
        # Test get_required_attributes_for_category
        # Use a category that definitely exists in the system
        category = TrendyolCategory.objects.filter(is_active=True).first()
        if category:
            attributes = get_required_attributes_for_category(category.category_id)
            
            # Should return a list (possibly empty)
            self.assertIsInstance(attributes, list)
    
    def test_calculate_similarity(self):
        """Test calculating similarity between strings"""
        test_cases = [
            {"str1": "t-shirt", "str2": "t-shirt", "expected": 1.0},
            {"str1": "t-shirt", "str2": "tshirt", "expected_min": 0.7},
            {"str1": "women's dress", "str2": "womens dress", "expected_min": 0.8},
            {"str1": "completely different", "str2": "not related at all", "expected_max": 0.3}
        ]
        
        for test_case in test_cases:
            similarity = self.category_finder._calculate_similarity(test_case["str1"], test_case["str2"])
            
            if "expected" in test_case:
                self.assertAlmostEqual(similarity, test_case["expected"], places=1)
            elif "expected_min" in test_case:
                self.assertGreaterEqual(similarity, test_case["expected_min"])
            elif "expected_max" in test_case:
                self.assertLessEqual(similarity, test_case["expected_max"])
    
    @classmethod
    def tearDownClass(cls):
        # Clean up any created test products
        if hasattr(cls, 'product') and cls.product and cls.product.id and cls.product.barcode.startswith('CATTEST'):
            cls.product.delete()
        super().tearDownClass()