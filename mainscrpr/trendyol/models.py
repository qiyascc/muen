from django.db import models
from django.utils import timezone
from loguru import logger


class TrendyolConfig(models.Model):
    """
    Configuration model for Trendyol API settings.
    This model stores the API key, secret, and supplier ID required for Trendyol integration.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Configuration name")
    api_key = models.CharField(max_length=200, help_text="Trendyol API key")
    api_secret = models.CharField(max_length=200, help_text="Trendyol API secret")
    supplier_id = models.CharField(max_length=100, help_text="Trendyol supplier ID")
    is_test = models.BooleanField(default=False, help_text="Use test environment")
    is_active = models.BooleanField(default=True, help_text="Whether this config is active")
    sync_frequency = models.PositiveIntegerField(
        default=12, 
        help_text="How often to sync with Trendyol (in hours)"
    )
    last_sync = models.DateTimeField(null=True, blank=True, help_text="Last successful sync time")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({'Test' if self.is_test else 'Production'})"

    def save(self, *args, **kwargs):
        """If this config is active, deactivate all others"""
        if self.is_active:
            TrendyolConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Trendyol Configuration"
        verbose_name_plural = "Trendyol Configurations"


class TrendyolProduct(models.Model):
    """
    Model to store Trendyol product data.
    This model maps to products in the Trendyol platform.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending Approval'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]

    trendyol_id = models.CharField(max_length=100, unique=True, help_text="Trendyol product ID")
    barcode = models.CharField(max_length=100, db_index=True, help_text="Product barcode")
    title = models.CharField(max_length=255, help_text="Product title")
    category_id = models.CharField(max_length=100, help_text="Trendyol category ID")
    category_name = models.CharField(max_length=255, help_text="Category name")
    brand_id = models.CharField(max_length=100, help_text="Trendyol brand ID")
    brand_name = models.CharField(max_length=255, help_text="Brand name")
    description = models.TextField(blank=True, null=True, help_text="Product description")
    list_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="List price")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Sale price")
    stock = models.PositiveIntegerField(default=0, help_text="Available stock")
    images = models.JSONField(default=list, help_text="Product images")
    approved = models.BooleanField(default=False, help_text="Whether product is approved")
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Product status"
    )
    last_sync = models.DateTimeField(default=timezone.now, help_text="Last sync time")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    raw_data = models.JSONField(default=dict, help_text="Raw data from Trendyol API")

    def __str__(self):
        return f"{self.title} ({self.barcode})"

    class Meta:
        verbose_name = "Trendyol Product"
        verbose_name_plural = "Trendyol Products"
        indexes = [
            models.Index(fields=['last_sync']),
            models.Index(fields=['barcode']),
            models.Index(fields=['status']),
        ]


class TrendyolSyncLog(models.Model):
    """
    Model to log Trendyol synchronization activities.
    This helps with debugging and monitoring the integration.
    """
    OPERATION_CHOICES = [
        ('fetch', 'Fetch Products'),
        ('update', 'Update Products'),
        ('price_stock', 'Update Price and Stock'),
        ('create', 'Create Products'),
    ]

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
    ]

    operation = models.CharField(
        max_length=20, 
        choices=OPERATION_CHOICES,
        help_text="Type of synchronization operation"
    )
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES,
        help_text="Status of the operation"
    )
    products_affected = models.PositiveIntegerField(
        default=0,
        help_text="Number of products affected"
    )
    message = models.TextField(help_text="Log message")
    request_data = models.JSONField(
        default=dict, 
        blank=True, 
        null=True,
        help_text="Data sent to Trendyol API"
    )
    response_data = models.JSONField(
        default=dict, 
        blank=True, 
        null=True,
        help_text="Data received from Trendyol API"
    )
    batch_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Trendyol batch request ID"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.operation} - {self.status} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"

    class Meta:
        verbose_name = "Trendyol Sync Log"
        verbose_name_plural = "Trendyol Sync Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['operation']),
            models.Index(fields=['status']),
        ]