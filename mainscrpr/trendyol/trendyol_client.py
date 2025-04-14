"""
Trendyol API client for the LCWaikiki integration.
This module handles all Trendyol API interactions.
"""
import logging
import time
import json
import base64
from typing import Dict, List, Any, Optional, Union
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from .api_integration import APIConfig, TrendyolAPI, TrendyolProductManager, ProductData
from .helpers import convert_lcwaikiki_to_trendyol_product, prepare_attributes_for_category
from .models import (
    TrendyolAPIConfig, 
    TrendyolProduct, 
    TrendyolBrand,
    TrendyolCategory,
    TrendyolBatchResult
)

logger = logging.getLogger(__name__)

class TrendyolClient:
    """
    Main client for interacting with Trendyol API
    """
    
    def __init__(self, config_id=None):
        """
        Initialize the Trendyol client
        
        Args:
            config_id: Optional config ID to use a specific configuration
        """
        self.api_config = None
        self.api_client = None
        self.product_manager = None
        
        self._initialize_api(config_id)
    
    def _initialize_api(self, config_id=None):
        """
        Initialize API client with configuration from database
        
        Args:
            config_id: Optional config ID to use
        """
        try:
            # Get API configuration from database
            if config_id:
                config = TrendyolAPIConfig.objects.get(id=config_id, is_active=True)
            else:
                config = TrendyolAPIConfig.objects.filter(is_active=True).first()
            
            if not config:
                logger.error("No active Trendyol API configuration found")
                return False
            
            # Create authentication token (Base64 encoded)
            auth_token = base64.b64encode(
                f"{config.api_key}:{config.api_secret}".encode()
            ).decode()
            
            # Initialize API client
            api_config = APIConfig(
                api_key=auth_token,
                seller_id=str(config.supplier_id),
                base_url=config.base_url
            )
            
            self.api_config = config
            self.api_client = TrendyolAPI(api_config)
            self.product_manager = TrendyolProductManager(self.api_client)
            
            logger.info(f"Initialized Trendyol API client with config ID {config.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Trendyol API: {str(e)}")
            return False
    
    def fetch_and_store_brands(self):
        """
        Fetch and store all brands from Trendyol
        
        Returns:
            int: Number of brands stored
        """
        if not self.api_client:
            logger.error("API client not initialized")
            return 0
        
        try:
            brands = self.product_manager.fetch_brands()
            
            if not brands:
                logger.warning("No brands returned from API")
                return 0
            
            count = 0
            for brand in brands:
                TrendyolBrand.objects.update_or_create(
                    brand_id=brand['id'],
                    defaults={
                        'name': brand['name'],
                        'is_active': True
                    }
                )
                count += 1
            
            logger.info(f"Successfully stored {count} brands")
            return count
            
        except Exception as e:
            logger.error(f"Error fetching and storing brands: {str(e)}")
            return 0
    
    def fetch_and_store_categories(self):
        """
        Fetch and store all categories from Trendyol
        
        Returns:
            int: Number of categories stored
        """
        if not self.api_client:
            logger.error("API client not initialized")
            return 0
        
        try:
            categories = self.product_manager.fetch_categories()
            
            if not categories:
                logger.warning("No categories returned from API")
                return 0
            
            count = self._store_categories_recursive(categories)
            logger.info(f"Successfully stored {count} categories")
            return count
            
        except Exception as e:
            logger.error(f"Error fetching and storing categories: {str(e)}")
            return 0
    
    def _store_categories_recursive(self, categories, parent_id=None):
        """
        Recursively store categories and their subcategories
        
        Args:
            categories: List of category dictionaries
            parent_id: Parent category ID
            
        Returns:
            int: Number of categories stored
        """
        count = 0
        
        for category in categories:
            try:
                obj, created = TrendyolCategory.objects.update_or_create(
                    category_id=category['id'],
                    defaults={
                        'name': category['name'],
                        'parent_id': parent_id,
                        'is_active': True
                    }
                )
                
                count += 1
                
                # Process subcategories if any
                if 'subCategories' in category and category['subCategories']:
                    count += self._store_categories_recursive(
                        category['subCategories'], 
                        parent_id=category['id']
                    )
                    
            except Exception as e:
                logger.error(f"Error storing category {category.get('name')}: {str(e)}")
        
        return count
    
    def get_brand_id(self, brand_name):
        """
        Get Trendyol brand ID for the given brand name
        
        Args:
            brand_name: Brand name to look for
            
        Returns:
            int: Brand ID or None if not found
        """
        if not brand_name:
            return None
        
        try:
            # Try to find brand in local database
            brand = TrendyolBrand.objects.filter(
                name__iexact=brand_name,
                is_active=True
            ).first()
            
            if brand:
                logger.info(f"Found brand in database: {brand.name} (ID: {brand.brand_id})")
                return brand.brand_id
            
            # Try to find similar brand
            brand = TrendyolBrand.objects.filter(
                name__icontains=brand_name,
                is_active=True
            ).first()
            
            if brand:
                logger.info(f"Found similar brand: {brand.name} (ID: {brand.brand_id})")
                return brand.brand_id
            
            # Try to fetch from API
            if self.api_client:
                try:
                    brands = self.product_manager.fetch_brands(brand_name)
                    
                    if brands and len(brands) > 0:
                        brand_id = brands[0]['id']
                        
                        # Store for future use
                        TrendyolBrand.objects.create(
                            brand_id=brand_id,
                            name=brands[0]['name'],
                            is_active=True
                        )
                        
                        logger.info(f"Found brand via API: {brands[0]['name']} (ID: {brand_id})")
                        return brand_id
                except Exception as e:
                    logger.error(f"API brand lookup failed: {str(e)}")
            
            # Use default LC Waikiki brand ID (7651) if not found
            logger.warning(f"Brand '{brand_name}' not found, using default LC Waikiki brand")
            return 7651
            
        except Exception as e:
            logger.error(f"Error finding brand ID: {str(e)}")
            return None
    
    def convert_lcwaikiki_product(self, lcw_product, trendyol_product=None):
        """
        Convert LCWaikiki product to Trendyol product format
        
        Args:
            lcw_product: LCWaikiki product model instance
            trendyol_product: Existing TrendyolProduct instance if updating
            
        Returns:
            TrendyolProduct: Created or updated Trendyol product
        """
        try:
            # Get brand ID (default to LC Waikiki if not found)
            brand_id = self.get_brand_id("LC Waikiki")
            if not brand_id:
                brand_id = 7651  # Default LC Waikiki brand ID
            
            # Find category
            category_id = None
            
            # Use existing category if available
            if trendyol_product and trendyol_product.category_id:
                category_id = trendyol_product.category_id
            else:
                # Try to find a matching category based on product's category name
                category_name = lcw_product.category if hasattr(lcw_product, 'category') else ""
                
                if category_name:
                    # Find matching category in database
                    category = TrendyolCategory.objects.filter(
                        name__icontains=category_name,
                        is_active=True
                    ).first()
                    
                    if category:
                        category_id = category.category_id
                        logger.info(f"Found matching category: {category.name} (ID: {category_id})")
                
                # If still not found, use a default category
                if not category_id:
                    default_category = TrendyolCategory.objects.filter(
                        name__icontains="Giyim",
                        is_active=True
                    ).first()
                    
                    if default_category:
                        category_id = default_category.category_id
                        logger.warning(f"Using default category: {default_category.name}")
                    else:
                        # Arbitrary default category ID for clothing
                        category_id = 1733  # Example placeholder
                        logger.warning("Using hardcoded default category ID: 1733")
            
            # Create ProductData object with appropriate data
            return convert_lcwaikiki_to_trendyol_product(
                lcw_product, 
                brand_id, 
                category_id,
                trendyol_product
            )
            
        except Exception as e:
            logger.error(f"Error converting LCWaikiki product: {str(e)}")
            return None
    
    def prepare_product_data(self, product, trendyol_product_data):
        """
        Prepare product data for Trendyol API submission
        
        Args:
            product: TrendyolProduct model instance
            trendyol_product_data: ProductData instance
            
        Returns:
            ProductData: Updated product data with attributes
        """
        try:
            # Prepare attributes from category
            if self.api_client and trendyol_product_data.category_id:
                # Get product color if available
                product_info = {
                    'color': product.lcwaikiki_product.color if hasattr(product.lcwaikiki_product, 'color') else None
                }
                
                # Get attributes for this category
                attributes = prepare_attributes_for_category(
                    self.api_client,
                    trendyol_product_data.category_id,
                    product_info
                )
                
                if attributes:
                    trendyol_product_data.attributes = attributes
                    logger.info(f"Added {len(attributes)} attributes to product")
            
            return trendyol_product_data
            
        except Exception as e:
            logger.error(f"Error preparing product data: {str(e)}")
            return trendyol_product_data
    
    def create_or_update_product(self, product):
        """
        Create or update a product on Trendyol
        
        Args:
            product: TrendyolProduct model instance
            
        Returns:
            bool: Success status
        """
        if not self.api_client or not self.product_manager:
            logger.error("API client not initialized")
            return False
        
        try:
            # Convert product to Trendyol format
            trendyol_data = self.convert_lcwaikiki_product(
                product.lcwaikiki_product, 
                product
            )
            
            if not trendyol_data:
                logger.error(f"Failed to convert product {product.id}")
                product.status_message = "Failed to convert product"
                product.batch_status = "failed"
                product.save()
                return False
            
            # Prepare product data (attributes, etc.)
            trendyol_data = self.prepare_product_data(product, trendyol_data)
            
            # Submit to Trendyol API
            batch_id = self.product_manager.create_product(trendyol_data)
            
            if batch_id:
                # Update product with batch information
                with transaction.atomic():
                    product.batch_id = batch_id
                    product.batch_status = "pending"
                    product.status_message = "Submitted to Trendyol"
                    product.save()
                    
                    # Create batch result entry
                    TrendyolBatchResult.objects.create(
                        batch_id=batch_id,
                        status="PENDING",
                        message="Product submission initiated",
                        product=product
                    )
                
                logger.info(f"Successfully submitted product {product.id} with batch ID {batch_id}")
                return True
            else:
                product.status_message = "Failed to submit product (no batch ID)"
                product.batch_status = "failed"
                product.save()
                return False
                
        except Exception as e:
            logger.error(f"Error creating/updating product {product.id}: {str(e)}")
            product.status_message = f"Error: {str(e)}"
            product.batch_status = "failed"
            product.save()
            return False
    
    def check_batch_status(self, batch_id):
        """
        Check status of a batch operation
        
        Args:
            batch_id: Batch ID to check
            
        Returns:
            dict: Batch status information
        """
        if not self.api_client or not self.product_manager:
            logger.error("API client not initialized")
            return None
        
        try:
            batch_status = self.product_manager.check_batch_status(batch_id)
            
            logger.info(f"Batch {batch_id} status: {json.dumps(batch_status)}")
            
            # Store batch result
            try:
                batch_result = TrendyolBatchResult.objects.filter(batch_id=batch_id).first()
                
                if batch_result:
                    batch_result.status = batch_status.get('status', 'UNKNOWN')
                    batch_result.message = batch_status.get('message', '')
                    batch_result.response_data = batch_status
                    batch_result.save()
                
                # Update associated products
                products = TrendyolProduct.objects.filter(batch_id=batch_id)
                
                if products.exists():
                    status = batch_status.get('status', '')
                    
                    if status == 'COMPLETED':
                        products.update(
                            batch_status='completed',
                            status_message='Successfully submitted to Trendyol'
                        )
                    elif status in ['FAILED', 'REJECTED']:
                        products.update(
                            batch_status='failed',
                            status_message=batch_status.get('message', 'Submission failed')
                        )
            except Exception as e:
                logger.error(f"Error updating batch result: {str(e)}")
            
            return batch_status
            
        except Exception as e:
            logger.error(f"Error checking batch status: {str(e)}")
            return None