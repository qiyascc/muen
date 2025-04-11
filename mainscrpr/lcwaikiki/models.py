from django.db import models
from django.core.exceptions import ValidationError
import json
from django.utils import timezone


class Config(models.Model):
    """
    Config model to store configuration data for the application.
    The brands field stores a list of brand identifiers in JSON format.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Configuration name")
    brands = models.JSONField(
        help_text="List of brands in JSON format, e.g. ['lcw-classic', 'lcw-abc']"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def clean(self):
        """
        Validate that the brands field contains a list of strings.
        """
        if not isinstance(self.brands, list):
            raise ValidationError({'brands': 'Brands must be a list'})
        
        for brand in self.brands:
            if not isinstance(brand, str):
                raise ValidationError({'brands': 'All brands must be strings'})

    def save(self, *args, **kwargs):
        """
        Override save to validate data before saving.
        """
        self.clean()
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
