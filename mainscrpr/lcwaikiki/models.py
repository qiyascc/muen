from django.db import models
from django.core.exceptions import ValidationError
import json
from django.utils import timezone


class Config(models.Model):
    """
    Config model to store configuration data for the application.
    This consolidated model now stores both brand data and various configuration settings.
    
    The brands field can store a list of brand identifiers in JSON format
    or a more complex JSON structure with additional configuration settings.
    
    Example structure:
    {
        "brands": ["lcw-classic", "lcw-abc"],
        "price_config": {
            "threshold": 500,
            "below_multiplier": 1.1,
            "above_multiplier": 1.2
        },
        "city_config": {
            "default_city_id": "865",
            "active_cities": ["865", "34", "6", "35", "1"],
            "use_stores": true
        },
        "stock_config": {
            "min_stock_level": 1,
            "check_store_stock": true,
            "max_concurrent_requests": 5,
            "batch_size": 100
        },
        "scraper_config": {
            "max_retries": 3,
            "retry_delay": 5,
            "timeout": 30,
            "max_proxy_attempts": 3
        }
    }
    """
    CITY_CHOICES = [
        ('34', 'Istanbul'),
        ('6', 'Ankara'),
        ('35', 'Izmir'),
        ('1', 'Adana'),
        ('865', 'Default City'),
    ]
    
    name = models.CharField(max_length=100, unique=True, help_text="Configuration name")
    brands = models.JSONField(
        help_text="Brand and configuration data in JSON format"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this config is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def default_city_id(self):
        """Get the default city ID from the configuration"""
        try:
            return self.brands.get('city_config', {}).get('default_city_id', '865')
        except (AttributeError, KeyError):
            return '865'  # Default fallback
    
    @property
    def active_cities(self):
        """Get the list of active cities from the configuration"""
        try:
            return self.brands.get('city_config', {}).get('active_cities', ['865'])
        except (AttributeError, KeyError):
            return ['865']  # Default fallback
    
    @property
    def use_stores(self):
        """Check if store stock checking is enabled"""
        try:
            return self.brands.get('city_config', {}).get('use_stores', True)
        except (AttributeError, KeyError):
            return True  # Default fallback
    
    @property
    def max_concurrent_requests(self):
        """Get the maximum number of concurrent requests"""
        try:
            return self.brands.get('stock_config', {}).get('max_concurrent_requests', 5)
        except (AttributeError, KeyError):
            return 5  # Default fallback
    
    @property
    def batch_size(self):
        """Get the batch size for processing URLs"""
        try:
            return self.brands.get('stock_config', {}).get('batch_size', 100)
        except (AttributeError, KeyError):
            return 100  # Default fallback

    def __str__(self):
        return self.name

    def clean(self):
        """
        Validate the brands field structure.
        """
        # Handle both legacy list format and new object format
        if isinstance(self.brands, list):
            # Convert legacy format to new format
            self.brands = {
                "brands": self.brands
            }
        
        if not isinstance(self.brands, dict):
            raise ValidationError({'brands': 'Configuration must be a JSON object'})
        
        # Validate brands if present
        if "brands" in self.brands:
            if not isinstance(self.brands["brands"], list):
                raise ValidationError({'brands': 'Brands must be a list'})
            
            for brand in self.brands["brands"]:
                if not isinstance(brand, str):
                    raise ValidationError({'brands': 'All brands must be strings'})
        
        # Validate price config if present
        if "price_config" in self.brands:
            if not isinstance(self.brands["price_config"], dict):
                raise ValidationError({'brands': 'Price config must be a dictionary'})
            
            if "threshold" in self.brands["price_config"] and not isinstance(self.brands["price_config"]["threshold"], (int, float)):
                raise ValidationError({'brands': 'Price threshold must be a number'})
                
            if "below_multiplier" in self.brands["price_config"] and not isinstance(self.brands["price_config"]["below_multiplier"], (int, float)):
                raise ValidationError({'brands': 'Below threshold multiplier must be a number'})
                
            if "above_multiplier" in self.brands["price_config"] and not isinstance(self.brands["price_config"]["above_multiplier"], (int, float)):
                raise ValidationError({'brands': 'Above threshold multiplier must be a number'})
        
        # Validate city config if present
        if "city_config" in self.brands:
            if not isinstance(self.brands["city_config"], dict):
                raise ValidationError({'brands': 'City config must be a dictionary'})
            
            if "active_cities" in self.brands["city_config"]:
                if not isinstance(self.brands["city_config"]["active_cities"], list):
                    raise ValidationError({'brands': 'Active cities must be a list'})
                
                for city in self.brands["city_config"]["active_cities"]:
                    if not any(city == choice[0] for choice in self.CITY_CHOICES):
                        raise ValidationError({'brands': f'Invalid city ID: {city}'})

    def save(self, *args, **kwargs):
        """
        Override save to validate data before saving.
        If is_active is True, make sure other configs are set to inactive.
        """
        self.clean()
        if self.is_active:
            Config.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Configuration"
        verbose_name_plural = "Configurations"


class ProductAvailableUrl(models.Model):
    """
    Model to store available product URLs.
    """
    page_id = models.CharField(max_length=255, help_text="Page identifier")
    product_id_in_page = models.CharField(max_length=255, help_text="Product identifier within the page")
    url = models.URLField(max_length=1000, help_text="URL to the product")
    last_checking = models.DateTimeField(default=timezone.now, help_text="Date of last check")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.page_id} - {self.product_id_in_page}"

    class Meta:
        verbose_name = "Available Product URL"
        verbose_name_plural = "Available Product URLs"
        indexes = [
            models.Index(fields=['page_id']),
            models.Index(fields=['product_id_in_page']),
            models.Index(fields=['last_checking']),
            models.Index(fields=['url']),
        ]


class ProductDeletedUrl(models.Model):
    """
    Model to store deleted product URLs.
    """
    url = models.URLField(max_length=1000, help_text="URL to the deleted product")
    last_checking = models.DateTimeField(default=timezone.now, help_text="Date of last check")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.url

    class Meta:
        verbose_name = "Deleted Product URL"
        verbose_name_plural = "Deleted Product URLs"
        indexes = [
            models.Index(fields=['last_checking']),
            models.Index(fields=['url']),
        ]


class ProductNewUrl(models.Model):
    """
    Model to store new product URLs.
    """
    url = models.URLField(max_length=1000, help_text="URL to the new product")
    last_checking = models.DateTimeField(default=timezone.now, help_text="Date of last check")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.url

    class Meta:
        verbose_name = "New Product URL"
        verbose_name_plural = "New Product URLs"
        indexes = [
            models.Index(fields=['last_checking']),
            models.Index(fields=['url']),
        ]
