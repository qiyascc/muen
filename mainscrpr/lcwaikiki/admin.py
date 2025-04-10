from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.utils.html import format_html
from .models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl

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


@admin.register(ProductAvailableUrl)
class ProductAvailableUrlAdmin(admin.ModelAdmin):
    """
    Admin configuration for the ProductAvailableUrl model.
    """
    list_display = ('page_id', 'product_id_in_page', 'display_url', 'last_checking', 'created_at')
    list_filter = ('last_checking', 'created_at')
    search_fields = ('page_id', 'product_id_in_page', 'url')
    readonly_fields = ('created_at', 'updated_at')
    
    def display_url(self, obj):
        """
        Display URL as a clickable link.
        """
        return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)
    
    display_url.short_description = 'URL'


@admin.register(ProductDeletedUrl)
class ProductDeletedUrlAdmin(admin.ModelAdmin):
    """
    Admin configuration for the ProductDeletedUrl model.
    """
    list_display = ('display_url', 'last_checking', 'created_at')
    list_filter = ('last_checking', 'created_at')
    search_fields = ('url',)
    readonly_fields = ('created_at', 'updated_at')
    
    def display_url(self, obj):
        """
        Display URL as a clickable link.
        """
        return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)
    
    display_url.short_description = 'URL'


@admin.register(ProductNewUrl)
class ProductNewUrlAdmin(admin.ModelAdmin):
    """
    Admin configuration for the ProductNewUrl model.
    """
    list_display = ('display_url', 'last_checking', 'created_at')
    list_filter = ('last_checking', 'created_at')
    search_fields = ('url',)
    readonly_fields = ('created_at', 'updated_at')
    
    def display_url(self, obj):
        """
        Display URL as a clickable link.
        """
        return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)
    
    display_url.short_description = 'URL'
