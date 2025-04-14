from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.html import format_html
from django.forms.widgets import PasswordInput
from unfold.admin import ModelAdmin, TabularInline

from .models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct
from .fetch_api_data import fetch_all_categories, fetch_all_brands

# Import api_helpers for direct API-based product submission
from .api_helpers import submit_product_to_trendyol, prepare_product_for_submission


@admin.register(TrendyolAPIConfig)
class TrendyolAPIConfigAdmin(ModelAdmin):
    """
    Admin configuration for the TrendyolAPIConfig model.
    """
    model = TrendyolAPIConfig
    list_display = ('name', 'seller_id', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'seller_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ("API Information", {"fields": ("name", "seller_id", "is_active")}),
        ("Authentication", {"fields": ("api_key", "api_secret")}),
        ("Connection", {"fields": ("base_url",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )
    
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in ('api_key', 'api_secret'):
            kwargs['widget'] = PasswordInput
        return super().formfield_for_dbfield(db_field, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """
        Ensure only one configuration is active at a time.
        """
        if obj.is_active:
            TrendyolAPIConfig.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(TrendyolBrand)
class TrendyolBrandAdmin(ModelAdmin):
    """
    Admin configuration for the TrendyolBrand model.
    """
    model = TrendyolBrand
    list_display = ('brand_id', 'name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'brand_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ("Brand Information", {"fields": ("brand_id", "name", "is_active")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(TrendyolCategory)
class TrendyolCategoryAdmin(ModelAdmin):
    """
    Admin configuration for the TrendyolCategory model.
    """
    model = TrendyolCategory
    list_display = ('category_id', 'name', 'parent_id', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'category_id', 'parent_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ("Category Information", {"fields": ("category_id", "name", "parent_id", "path", "is_active")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(TrendyolProduct)
class TrendyolProductAdmin(ModelAdmin):
    """
    Admin configuration for the TrendyolProduct model.
    """
    model = TrendyolProduct
    list_display = ('title', 'barcode', 'brand_name', 'price', 'quantity', 'display_batch_id', 'batch_status', 'last_sync_time')
    list_filter = ('batch_status', 'last_sync_time', 'created_at')
    search_fields = ('title', 'barcode', 'product_main_id', 'stock_code', 'batch_id')
    readonly_fields = ('created_at', 'updated_at', 'last_check_time', 'last_sync_time', 'display_trendyol_link', 'display_batch_id')
    
    fieldsets = (
        ("Product Information", {"fields": ("title", "description", "barcode", "product_main_id", "stock_code")}),
        ("Brand and Category", {"fields": ("brand_name", "category_name", "brand_id", "category_id")}),
        ("Price and Stock", {"fields": ("price", "quantity", "vat_rate", "currency_type")}),
        ("Images", {"fields": ("image_url", "additional_images")}),
        ("LCWaikiki Relation", {"fields": ("lcwaikiki_product",)}),
        ("Trendyol Information", {"fields": ("trendyol_id", "trendyol_url", "display_trendyol_link", "attributes")}),
        ("Synchronization", {"fields": ("display_batch_id", "batch_id", "batch_status", "status_message", "last_check_time", "last_sync_time")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )
    
    date_hierarchy = 'created_at'
    empty_value_display = 'N/A'
    
    def display_trendyol_link(self, obj):
        """
        Display Trendyol URL as a clickable link.
        """
        if obj.trendyol_url:
            return format_html('<a href="{}" target="_blank">Open in Trendyol</a>', obj.trendyol_url)
        return "Not available"
    display_trendyol_link.short_description = "Trendyol Link"
    
    def display_batch_id(self, obj):
        """
        Display batch ID as a clickable link to custom batch status page.
        """
        if obj.batch_id:
            # Create link to our custom batch status page
            from django.urls import reverse
            batch_status_url = reverse('trendyol:batch_status', args=[obj.batch_id])
            return format_html('<a href="{}" target="_blank">{}</a>', batch_status_url, obj.batch_id)
        return "Not available"
    display_batch_id.short_description = "Batch ID"
    
    from .admin_actions import (
        send_to_trendyol,
        check_sync_status,
        retry_failed_products,
        refresh_from_api,
        refresh_product_data
    )
    
    actions = [
        'send_to_trendyol',
        'check_sync_status',
        'retry_failed_products',
        'refresh_from_api',
        'refresh_product_data'
    ]
    
    def send_to_trendyol(self, request, queryset):
        """Trendyol'a ürün gönderme işlemi"""
        from .admin_actions import send_to_trendyol as send_to_trendyol_action
        return send_to_trendyol_action(self, request, queryset)
    
    def check_sync_status(self, request, queryset):
        """Ürün durumunu kontrol etme işlemi"""
        from .admin_actions import check_sync_status as check_sync_status_action
        return check_sync_status_action(self, request, queryset)
    
    def retry_failed_products(self, request, queryset):
        """Başarısız ürünleri yeniden deneme işlemi"""
        from .admin_actions import retry_failed_products as retry_failed_products_action
        return retry_failed_products_action(self, request, queryset)
    
    def refresh_from_api(self, request, queryset):
        """API'den ürün bilgilerini yenileme işlemi"""
        from .admin_actions import refresh_from_api as refresh_from_api_action
        return refresh_from_api_action(self, request, queryset)
    
    def refresh_product_data(self, request, queryset):
        """
        Refresh product data from LCWaikiki source (if available) and update attributes.
        Useful for synchronizing changes in product details with Trendyol.
        """
        import re
        from django.utils import timezone
        from lcwaikiki.product_models import Product as LCWaikikiProduct
        
        updated_count = 0
        not_linked_count = 0
        attribute_fixed_count = 0
        
        # Color ID mapping for Trendyol
        color_id_map = {
            'Beyaz': 1001, 
            'Siyah': 1002, 
            'Mavi': 1003, 
            'Kirmizi': 1004, 
            'Pembe': 1005,
            'Yeşil': 1006,
            'Sarı': 1007,
            'Mor': 1008,
            'Gri': 1009,
            'Kahverengi': 1010,
            'Ekru': 1011,
            'Bej': 1012,
            'Lacivert': 1013,
            'Turuncu': 1014,
            'Krem': 1015,
            'Petrol': 1016   # Petrol rengini ekledik
        }
        
        for product in queryset:
            try:
                # Check if product is linked to LCWaikiki product
                if not product.lcwaikiki_product_id:
                    # Try to find a matching LCWaikiki product by barcode or stock code
                    matching_product = None
                    if product.barcode:
                        matching_product = LCWaikikiProduct.objects.filter(
                            product_code=product.barcode
                        ).first()
                    
                    if not matching_product and product.stock_code:
                        matching_product = LCWaikikiProduct.objects.filter(
                            product_code=product.stock_code
                        ).first()
                    
                    if matching_product:
                        # Link the products
                        product.lcwaikiki_product = matching_product
                        self.message_user(
                            request, 
                            f"Linked product '{product.title}' to LCWaikiki product '{matching_product.title}'", 
                            level='success'
                        )
                    else:
                        not_linked_count += 1
                        continue
                
                # Get linked LCWaikiki product
                lcw_product = product.lcwaikiki_product
                if lcw_product:
                    # Update product data
                    product.title = lcw_product.title or product.title
                    product.description = lcw_product.description or product.description
                    product.price = lcw_product.price or product.price
                    product.image_url = lcw_product.images[0] if lcw_product.images else product.image_url
                    
                        # Atributes are now set by the API automatically
                    # Clear any existing attributes to let the API handle them correctly
                    product.attributes = []
                    attribute_fixed_count += 1
                    
                    # Update timestamp
                    product.updated_at = timezone.now()
                    product.save()
                    updated_count += 1
                
            except Exception as e:
                self.message_user(request, f"Error refreshing product {product.title}: {str(e)}", level='error')
        
        # Report results
        if updated_count:
            self.message_user(
                request, 
                f"Successfully refreshed {updated_count} products. Fixed attributes for {attribute_fixed_count} products."
            )
        if not_linked_count:
            self.message_user(
                request, 
                f"Could not find LCWaikiki data for {not_linked_count} products.", 
                level='warning'
            )
    
    refresh_product_data.short_description = "Refresh product data from LCWaikiki"