from django.db import models
from django.utils import timezone
from datetime import timedelta
import json


class TrendyolAPIConfig(models.Model):
    """
    Configuration for Trendyol API access.
    """
    name = models.CharField(max_length=100, help_text="Configuration name")
    seller_id = models.CharField(max_length=50, help_text="Trendyol seller ID")
    api_key = models.CharField(max_length=255, help_text="API key for authentication")
    api_secret = models.CharField(max_length=255, help_text="API secret for authentication")
    base_url = models.URLField(
        default="https://api.trendyol.com/sapigw/",
        help_text="Base URL for the Trendyol API"
    )
    is_active = models.BooleanField(default=False, help_text="Whether this config is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.seller_id})"
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure only one config is active at a time.
        """
        if self.is_active:
            # Set all other configs to inactive
            TrendyolAPIConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Trendyol API Configuration"
        verbose_name_plural = "Trendyol API Configurations"


class TrendyolBrand(models.Model):
    """
    Model to store Trendyol brand information.
    """
    brand_id = models.IntegerField(primary_key=True, help_text="Trendyol brand ID")
    name = models.CharField(max_length=255, help_text="Brand name")
    is_active = models.BooleanField(default=True, help_text="Whether this brand is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Trendyol Brand"
        verbose_name_plural = "Trendyol Brands"


class TrendyolCategory(models.Model):
    """
    Model to store Trendyol category information.
    """
    category_id = models.IntegerField(primary_key=True, help_text="Trendyol category ID")
    name = models.CharField(max_length=255, help_text="Category name")
    parent_id = models.IntegerField(null=True, blank=True, help_text="Parent category ID")
    path = models.TextField(blank=True, help_text="Full category path")
    is_active = models.BooleanField(default=True, help_text="Whether this category is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Trendyol Category"
        verbose_name_plural = "Trendyol Categories"


class TrendyolProduct(models.Model):
    """
    Model to store Trendyol product information.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Basic information
    title = models.CharField(max_length=255, help_text="Product title")
    description = models.TextField(blank=True, help_text="Product description")
    barcode = models.CharField(max_length=100, help_text="Product barcode", unique=True)
    product_main_id = models.CharField(max_length=100, help_text="Unique ID for product variations")
    stock_code = models.CharField(max_length=100, help_text="Stock code", blank=True)
    brand_name = models.CharField(max_length=255, help_text="Brand name")
    category_name = models.CharField(max_length=255, help_text="Category name")
    
    # Price and stock information
    quantity = models.PositiveIntegerField(default=0, help_text="Available quantity")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price")
    vat_rate = models.PositiveIntegerField(default=18, help_text="VAT rate percentage")
    currency_type = models.CharField(max_length=3, default="TRY", help_text="Currency type")
    
    # Images
    image_url = models.URLField(help_text="Main product image URL")
    additional_images = models.JSONField(default=list, help_text="Additional product images")
    
    # Original LCWaikiki product link
    lcwaikiki_product = models.ForeignKey(
        'lcwaikiki.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trendyol_products',
        help_text="Related LCWaikiki product"
    )
    
    # Trendyol information
    trendyol_id = models.CharField(max_length=100, blank=True, null=True, help_text="Trendyol product ID")
    trendyol_url = models.URLField(blank=True, null=True, help_text="Trendyol product URL")
    category_id = models.IntegerField(null=True, blank=True, help_text="Trendyol category ID")
    brand_id = models.IntegerField(null=True, blank=True, help_text="Trendyol brand ID")
    attributes = models.JSONField(default=dict, help_text="Product attributes")
    
    # Synchronization information
    batch_id = models.CharField(max_length=100, blank=True, null=True, help_text="Batch ID for tracking requests")
    batch_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', help_text="Status of the last batch operation")
    status_message = models.TextField(blank=True, help_text="Status message or error details")
    last_check_time = models.DateTimeField(default=timezone.now, help_text="Time of last status check")
    last_sync_time = models.DateTimeField(null=True, blank=True, help_text="Time of last successful sync")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    def set_batch_status(self, status, message=""):
        """
        Update batch status and message.
        """
        self.batch_status = status
        self.status_message = message
        self.last_check_time = timezone.now()
        if status == 'completed':
            self.last_sync_time = timezone.now()
        self.save(update_fields=['batch_status', 'status_message', 'last_check_time', 'last_sync_time'])
    
    def needs_status_check(self):
        """
        Determine if this product needs a status check.
        """
        if not self.batch_id or self.batch_status not in ['pending', 'processing']:
            return False
        
        # Only check every 5 minutes
        return timezone.now() > self.last_check_time + timedelta(minutes=5)
    
    def to_trendyol_payload(self):
        """
        Convert this product to a Trendyol API payload.
        """
        return {
            "barcode": self.barcode,
            "title": self.title,
            "productMainId": self.product_main_id,
            "brandId": self.brand_id,
            "categoryId": self.category_id,
            "quantity": self.quantity,
            "stockCode": self.stock_code,
            "description": self.description,
            "currencyType": self.currency_type,
            "listPrice": float(self.price) + 10,  # Add a margin for list price
            "salePrice": float(self.price),
            "vatRate": self.vat_rate,
            "images": self._format_images(),
            "attributes": self.attributes
        }
    
    def _format_images(self):
        """
        Format images for Trendyol API.
        """
        images = [{"url": self.image_url}]
        for img_url in self.additional_images:
            images.append({"url": img_url})
        return images
    
    def from_lcwaikiki_product(self, lcw_product):
        """
        Populate this product from an LCWaikiki product.
        """
        from uuid import uuid4
        
        self.title = lcw_product.title or ""
        self.description = lcw_product.description or ""
        self.lcwaikiki_product = lcw_product
        self.price = lcw_product.price or 0
        self.quantity = 10 if lcw_product.in_stock else 0
        
        # Generate a random barcode if needed
        if not self.barcode:
            self.barcode = f"LCW{uuid4().hex[:12].upper()}"
        
        if not self.product_main_id:
            self.product_main_id = f"LCW{lcw_product.product_code}"
        
        if not self.stock_code:
            self.stock_code = lcw_product.product_code or f"LCW{uuid4().hex[:8].upper()}"
        
        # Set brand and category
        self.brand_name = "LCW"
        self.category_name = lcw_product.category or "Clothing"
        
        # Set main image
        if lcw_product.images:
            self.image_url = lcw_product.images[0]
            self.additional_images = lcw_product.images[1:5]  # Limit to first 5 images
        
        return self
    
    class Meta:
        verbose_name = "Trendyol Product"
        verbose_name_plural = "Trendyol Products"
        indexes = [
            models.Index(fields=['batch_status']),
            models.Index(fields=['barcode']),
            models.Index(fields=['last_check_time']),
        ]