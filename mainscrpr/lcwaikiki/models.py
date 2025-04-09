from django.db import models
from django.core.exceptions import ValidationError
import json


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
