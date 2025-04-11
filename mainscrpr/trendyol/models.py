from django.db import models
from django.utils import timezone
from lcwaikiki.product_models import Product


class TrendyolAPIConfig(models.Model):
    """
    Configuration for the Trendyol API.
    Stores authentication and connection details.
    """
    name = models.CharField(max_length=100, help_text="Name for this configuration")
    seller_id = models.CharField(max_length=100, help_text="Trendyol Seller ID")
    api_key = models.CharField(max_length=255, help_text="Trendyol API Key")
    api_secret = models.CharField(max_length=255, help_text="Trendyol API Secret")
    base_url = models.URLField(default="https://apigw.trendyol.com/integration", help_text="Trendyol API base URL")
    is_active = models.BooleanField(default=True, help_text="Whether this configuration is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trendyol API Configuration"
        verbose_name_plural = "Trendyol API Configurations"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.seller_id})"


class TrendyolBrand(models.Model):
    """
    Trendyol Brand model.
    Stores brand information from Trendyol.
    """
    brand_id = models.IntegerField(unique=True, help_text="Trendyol Brand ID")
    name = models.CharField(max_length=255, help_text="Brand Name")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trendyol Brand"
        verbose_name_plural = "Trendyol Brands"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.brand_id})"


class TrendyolCategory(models.Model):
    """
    Trendyol Category model.
    Stores category information from Trendyol.
    """
    category_id = models.IntegerField(unique=True, help_text="Trendyol Category ID")
    name = models.CharField(max_length=255, help_text="Category Name")
    parent_id = models.IntegerField(null=True, blank=True, help_text="Parent Category ID")
    path = models.CharField(max_length=500, blank=True, help_text="Full category path")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trendyol Category"
        verbose_name_plural = "Trendyol Categories"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.category_id})"


class TrendyolProduct(models.Model):
    """
    Trendyol Product model.
    Stores product information for Trendyol integration.
    """
    BATCH_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    CURRENCY_CHOICES = [
        ('TRY', 'Turkish Lira'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
    ]
    
    # Product information
    title = models.CharField(max_length=255)
    description = models.TextField()
    barcode = models.CharField(max_length=100, unique=True)
    product_main_id = models.CharField(max_length=100, blank=True, help_text="Main product ID")
    stock_code = models.CharField(max_length=100, blank=True, help_text="Stock code")
    
    # Brand and category
    brand_name = models.CharField(max_length=100)
    brand_id = models.IntegerField(null=True, blank=True)
    category_name = models.CharField(max_length=255, blank=True)
    category_id = models.IntegerField(null=True, blank=True)
    pim_category_id = models.IntegerField(null=True, blank=True, help_text="Product Information Management Category ID (optional)")
    
    # Price and stock
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=0)
    vat_rate = models.IntegerField(default=18, help_text="VAT rate percentage")
    currency_type = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='TRY')
    
    # Images
    image_url = models.URLField(blank=True)
    additional_images = models.JSONField(default=list, blank=True)
    
    # LCWaikiki relation
    lcwaikiki_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='trendyol_products'
    )
    
    # Trendyol information
    trendyol_id = models.CharField(max_length=50, blank=True, help_text="Trendyol product ID")
    trendyol_url = models.URLField(blank=True, help_text="URL to the product on Trendyol")
    attributes = models.JSONField(default=dict, blank=True, help_text="Product attributes for Trendyol")
    
    # Synchronization
    batch_id = models.CharField(max_length=100, blank=True, help_text="Batch ID for synchronization")
    batch_status = models.CharField(
        max_length=20, choices=BATCH_STATUS_CHOICES, default='pending', help_text="Status of the synchronization"
    )
    status_message = models.TextField(blank=True, help_text="Status or error message")
    last_check_time = models.DateTimeField(null=True, blank=True, help_text="Last status check time")
    last_sync_time = models.DateTimeField(null=True, blank=True, help_text="Last successful sync time")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Trendyol Product"
        verbose_name_plural = "Trendyol Products"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['barcode']),
            models.Index(fields=['product_main_id']),
            models.Index(fields=['batch_status']),
            models.Index(fields=['last_sync_time']),
        ]
    
    def __str__(self):
        return f"{self.title} (Barcode: {self.barcode})"
    
    def save(self, *args, **kwargs):
        # Update last_check_time when batch_status changes
        if self.pk:
            old_obj = TrendyolProduct.objects.get(pk=self.pk)
            if old_obj.batch_status != self.batch_status:
                self.last_check_time = timezone.now()
                
            # Update last_sync_time when batch_status changes to completed
            if old_obj.batch_status != 'completed' and self.batch_status == 'completed':
                self.last_sync_time = timezone.now()
        
        super().save(*args, **kwargs)