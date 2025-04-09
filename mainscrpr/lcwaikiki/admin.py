from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
import json
from .models import Config

@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Config model.
    """
    list_display = ('name', 'display_brands', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    def display_brands(self, obj):
        """
        Format the brands list for display in the admin list view.
        """
        if isinstance(obj.brands, list):
            return ", ".join(obj.brands)
        return str(obj.brands)
    
    display_brands.short_description = 'Brands'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['brands'].help_text = 'Enter brands as a list of strings, e.g. ["lcw-classic", "lcw-abc"]'
        return form
