from django.contrib import admin
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.html import format_html
from django.forms.widgets import Textarea
from unfold.admin import ModelAdmin
import json
from datetime import timedelta
from django.urls import reverse

from .models import (
    TrendyolAPIConfig,
    TrendyolBrand,
    TrendyolCategory,
    TrendyolProduct,
    TrendyolBatchRequest,
)

# Register your models here.

class JSONFieldTextarea(Textarea):
    """Textarea widget for JSONField with pretty formatting"""
    def format_value(self, value):
        if value is None:
            return ""
        try:
            if isinstance(value, str):
                value = json.loads(value)
            return json.dumps(value, indent=2, cls=DjangoJSONEncoder, ensure_ascii=False)
        except Exception:
            return value


@admin.register(TrendyolAPIConfig)
class TrendyolAPIConfigAdmin(ModelAdmin):
    list_display = ('name', 'seller_id', 'is_active', 'updated_at')
    search_fields = ('name', 'seller_id')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Configuration', {
            'fields': ('name', 'seller_id', 'is_active')
        }),
        ('API Credentials', {
            'fields': ('api_key', 'api_secret'),
            'classes': ('collapse',),
        }),
        ('Advanced Settings', {
            'fields': ('base_url', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(TrendyolBrand)
class TrendyolBrandAdmin(ModelAdmin):
    list_display = ('name', 'brand_id', 'is_active')
    search_fields = ('name', 'brand_id')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Brand Information', {
            'fields': ('name', 'brand_id', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    actions = ['refresh_brands']
    
    def refresh_brands(self, request, queryset):
        from trendyol.trendyol_api_client import get_api_client
        
        api = get_api_client()
        if not api:
            self.message_user(request, "Failed to initialize API client. Check API configuration.", level='error')
            return
            
        try:
            # Fetch brands from Trendyol API
            brands_data = api.get("product/brands")
            
            if not isinstance(brands_data, list):
                self.message_user(request, f"Unexpected API response format: {type(brands_data)}", level='error')
                return
                
            count_new = 0
            count_updated = 0
            
            for brand in brands_data:
                brand_id = brand.get('id')
                brand_name = brand.get('name')
                
                if not brand_id or not brand_name:
                    continue
                    
                obj, created = TrendyolBrand.objects.update_or_create(
                    brand_id=brand_id,
                    defaults={
                        'name': brand_name,
                        'is_active': True
                    }
                )
                
                if created:
                    count_new += 1
                else:
                    count_updated += 1
                    
            self.message_user(
                request, 
                f"Successfully refreshed brands: {count_new} new brands, {count_updated} updated brands"
            )
            
        except Exception as e:
            self.message_user(request, f"Error refreshing brands: {str(e)}", level='error')
    refresh_brands.short_description = "Refresh brands from Trendyol API"


@admin.register(TrendyolCategory)
class TrendyolCategoryAdmin(ModelAdmin):
    list_display = ('name', 'category_id', 'parent_id', 'is_active')
    search_fields = ('name', 'category_id', 'parent_id')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Category Information', {
            'fields': ('name', 'category_id', 'parent_id', 'path', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    actions = ['refresh_categories']
    
    def refresh_categories(self, request, queryset):
        from trendyol.trendyol_api_client import get_api_client
        
        api = get_api_client()
        if not api:
            self.message_user(request, "Failed to initialize API client. Check API configuration.", level='error')
            return
            
        try:
            # Fetch categories from Trendyol API
            categories_data = api.get("product/product-categories")
            categories = categories_data.get('categories', [])
            
            if not categories:
                self.message_user(request, "No categories returned from API", level='error')
                return
                
            count_new = 0
            count_updated = 0
            
            # Process all categories recursively
            self._process_categories(categories, None, '', count_new, count_updated)
                    
            self.message_user(
                request, 
                f"Successfully refreshed categories: {count_new} new categories, {count_updated} updated categories"
            )
            
        except Exception as e:
            self.message_user(request, f"Error refreshing categories: {str(e)}", level='error')
    
    def _process_categories(self, categories, parent_id, parent_path, count_new, count_updated):
        """Process categories recursively"""
        for category in categories:
            category_id = category.get('id')
            category_name = category.get('name')
            
            if not category_id or not category_name:
                continue
                
            # Construct category path
            path = f"{parent_path} > {category_name}" if parent_path else category_name
            
            obj, created = TrendyolCategory.objects.update_or_create(
                category_id=category_id,
                defaults={
                    'name': category_name,
                    'parent_id': parent_id,
                    'path': path,
                    'is_active': True
                }
            )
            
            if created:
                count_new += 1
            else:
                count_updated += 1
                
            # Process subcategories if any
            subcategories = category.get('subCategories', [])
            if subcategories:
                self._process_categories(subcategories, category_id, path, count_new, count_updated)
    
    refresh_categories.short_description = "Refresh categories from Trendyol API"


@admin.register(TrendyolBatchRequest)
class TrendyolBatchRequestAdmin(ModelAdmin):
    list_display = ('batch_id', 'status', 'operation_type', 'items_count', 'success_count', 'fail_count', 'created_at', 'check_status_button')
    list_filter = ('status', 'operation_type', 'created_at')
    search_fields = ('batch_id', 'status_message')
    readonly_fields = ('batch_id', 'created_at', 'updated_at', 'last_checked_at', 'formatted_response_data')
    fieldsets = (
        ('Batch Information', {
            'fields': ('batch_id', 'status', 'operation_type', 'status_message')
        }),
        ('Counts', {
            'fields': ('items_count', 'success_count', 'fail_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_checked_at'),
        }),
        ('Response Data', {
            'fields': ('formatted_response_data',),
            'classes': ('collapse',),
        }),
    )
    actions = ['check_batch_status']
    
    def formatted_response_data(self, obj):
        """Display formatted JSON response data"""
        if not obj.response_data:
            return '-'
        try:
            data = json.loads(obj.response_data)
            return format_html('<pre>{}</pre>', json.dumps(data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            return format_html('<pre>{}</pre>', obj.response_data)
    formatted_response_data.short_description = 'Response Data'
    
    def check_status_button(self, obj):
        """Add a button to check batch status"""
        url = reverse('admin:check_batch_status', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Check Status</a>',
            url
        )
    check_status_button.short_description = 'Actions'
    
    def check_batch_status(self, request, queryset):
        from trendyol.trendyol_api_client import get_product_manager
        from django.utils import timezone
        
        product_manager = get_product_manager()
        if not product_manager:
            self.message_user(request, "Failed to initialize API client. Check API configuration.", level='error')
            return
            
        success_count = 0
        fail_count = 0
        
        for batch_request in queryset:
            try:
                # Check batch status
                status_data = product_manager.check_batch_status(batch_request.batch_id)
                
                # Update batch request
                batch_request.status = status_data.get('status', 'unknown').lower()
                batch_request.status_message = status_data.get('message', '')
                batch_request.last_checked_at = timezone.now()
                batch_request.success_count = status_data.get('successCount', 0)
                batch_request.fail_count = status_data.get('failCount', 0)
                batch_request.items_count = status_data.get('itemCount', 0)
                batch_request.response_data = json.dumps(status_data)
                batch_request.save()
                
                # Update associated products
                self._update_products_from_batch(batch_request, status_data)
                
                success_count += 1
            except Exception as e:
                fail_count += 1
                self.message_user(
                    request, 
                    f"Error checking batch {batch_request.batch_id}: {str(e)}", 
                    level='error'
                )
                
        if success_count > 0:
            self.message_user(
                request, 
                f"Successfully checked {success_count} batch requests."
            )
    check_batch_status.short_description = "Check batch status from Trendyol API"
    
    def _update_products_from_batch(self, batch_request, status_data):
        """Update products associated with this batch"""
        from django.utils import timezone
        from .models import TrendyolProduct
        
        # Find products with this batch ID
        products = TrendyolProduct.objects.filter(batch_id=batch_request.batch_id)
        
        if not products:
            return
            
        batch_status = status_data.get('status', '').lower()
        
        # Get results
        results = status_data.get('results', [])
        
        for product in products:
            if batch_status == 'completed':
                product.batch_status = 'completed'
                product.status_message = 'Product synchronized successfully'
                
                # Try to get product ID from results
                for result in results:
                    if result.get('status') == 'SUCCESS' and result.get('productId'):
                        product.trendyol_id = str(result.get('productId'))
                        break
                        
            elif batch_status == 'failed':
                product.batch_status = 'failed'
                product.status_message = status_data.get('message', 'Unknown error')
                
                # Try to get error message from results
                for result in results:
                    if result.get('status') == 'FAILED':
                        error_message = result.get('failureReasons', [])
                        if error_message:
                            product.status_message = ', '.join([r.get('message', '') for r in error_message])
                        break
            else:
                product.batch_status = 'processing'
                product.status_message = f"Status: {batch_status.capitalize()} - {status_data.get('message', '')}"
                
            product.save()


@admin.register(TrendyolProduct)
class TrendyolProductAdmin(ModelAdmin):
    list_display = ('title', 'barcode', 'category_name', 'price', 'quantity', 'batch_status', 'created_at', 'actions_buttons')
    list_filter = ('batch_status', 'created_at', 'updated_at')
    search_fields = ('title', 'barcode', 'product_main_id', 'stock_code')
    readonly_fields = ('created_at', 'updated_at', 'last_synced_at', 'formatted_attributes')
    formfield_overrides = {
        models.JSONField: {'widget': JSONFieldTextarea},
    }
    
    fieldsets = (
        ('Product Information', {
            'fields': ('title', 'description', 'barcode', 'product_main_id', 'stock_code')
        }),
        ('Status', {
            'fields': ('batch_status', 'status_message', 'trendyol_id', 'batch_id', 'last_synced_at')
        }),
        ('Categorization', {
            'fields': ('brand_id', 'brand_name', 'category_id', 'category_name', 'pim_category_id')
        }),
        ('Pricing and Stock', {
            'fields': ('price', 'sale_price', 'quantity', 'vat_rate', 'currency_type', 'dimensional_weight', 'cargo_company_id')
        }),
        ('Images', {
            'fields': ('image_url', 'preview_image', 'additional_images')
        }),
        ('Attributes', {
            'fields': ('formatted_attributes',),
            'classes': ('collapse',),
        }),
        ('Relations', {
            'fields': ('lcwaikiki_product', 'batch_request'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = [
        'sync_products_to_trendyol', 
        'check_product_status',
        'update_product_prices',
        'update_product_stock'
    ]
    
    def get_readonly_fields(self, request, obj=None):
        """Make more fields readonly if product is already submitted to Trendyol"""
        readonly_fields = list(self.readonly_fields)
        if obj and obj.batch_status in ['completed']:
            readonly_fields.extend([
                'barcode', 'product_main_id', 'stock_code',
                'brand_id', 'category_id', 'pim_category_id'
            ])
        return readonly_fields
    
    def preview_image(self, obj):
        """Display image preview"""
        if obj.image_url:
            return format_html('<img src="{}" style="max-width: 200px; max-height: 200px;" />', obj.image_url)
        return '-'
    preview_image.short_description = 'Image Preview'
    
    def formatted_attributes(self, obj):
        """Display formatted attributes"""
        if not obj.attributes:
            return '-'
        try:
            return format_html('<pre>{}</pre>', json.dumps(obj.attributes, indent=2, ensure_ascii=False))
        except Exception:
            return format_html('<pre>{}</pre>', str(obj.attributes))
    formatted_attributes.short_description = 'Attributes'
    
    def actions_buttons(self, obj):
        """Show action buttons"""
        buttons = []
        
        # Button to sync to Trendyol
        if obj.batch_status in ['pending', 'failed']:
            url = reverse('admin:sync_product_to_trendyol', args=[obj.pk])
            buttons.append(f'<a class="button" href="{url}">Sync to Trendyol</a>')
        
        # Button to check status
        if obj.batch_id and obj.batch_status == 'processing':
            url = reverse('admin:check_product_status', args=[obj.pk])
            buttons.append(f'<a class="button" href="{url}">Check Status</a>')
        
        # Buttons for completed products
        if obj.batch_status == 'completed' and obj.trendyol_id:
            # Update price button
            url = reverse('admin:update_product_price', args=[obj.pk])
            buttons.append(f'<a class="button" href="{url}">Update Price</a>')
            
            # Update stock button
            url = reverse('admin:update_product_stock', args=[obj.pk])
            buttons.append(f'<a class="button" href="{url}">Update Stock</a>')
        
        return format_html(' '.join(buttons))
    actions_buttons.short_description = 'Actions'
    
    def sync_products_to_trendyol(self, request, queryset):
        """Sync selected products to Trendyol"""
        success_count = 0
        fail_count = 0
        
        for product in queryset:
            try:
                if product.sync_to_trendyol():
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                self.message_user(
                    request, 
                    f"Error syncing product {product.barcode}: {str(e)}", 
                    level='error'
                )
                
        if success_count > 0:
            self.message_user(
                request, 
                f"Successfully submitted {success_count} products to Trendyol."
            )
        if fail_count > 0:
            self.message_user(
                request,
                f"Failed to submit {fail_count} products. Check individual products for error details.",
                level='warning'
            )
    sync_products_to_trendyol.short_description = "Sync selected products to Trendyol"
    
    def check_product_status(self, request, queryset):
        """Check the status of selected products"""
        success_count = 0
        fail_count = 0
        
        for product in queryset:
            try:
                if product.check_batch_status():
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                self.message_user(
                    request, 
                    f"Error checking status for product {product.barcode}: {str(e)}", 
                    level='error'
                )
                
        if success_count > 0:
            self.message_user(
                request, 
                f"Successfully checked status for {success_count} products."
            )
        if fail_count > 0:
            self.message_user(
                request,
                f"Failed to check status for {fail_count} products.",
                level='warning'
            )
    check_product_status.short_description = "Check product status in Trendyol"
    
    def update_product_prices(self, request, queryset):
        """Update prices for selected products"""
        success_count = 0
        fail_count = 0
        
        for product in queryset:
            try:
                if product.update_price():
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                self.message_user(
                    request, 
                    f"Error updating price for product {product.barcode}: {str(e)}", 
                    level='error'
                )
                
        if success_count > 0:
            self.message_user(
                request, 
                f"Successfully submitted price updates for {success_count} products."
            )
        if fail_count > 0:
            self.message_user(
                request,
                f"Failed to update prices for {fail_count} products.",
                level='warning'
            )
    update_product_prices.short_description = "Update prices in Trendyol"
    
    def update_product_stock(self, request, queryset):
        """Update stock for selected products"""
        success_count = 0
        fail_count = 0
        
        for product in queryset:
            try:
                if product.update_stock():
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                self.message_user(
                    request, 
                    f"Error updating stock for product {product.barcode}: {str(e)}", 
                    level='error'
                )
                
        if success_count > 0:
            self.message_user(
                request, 
                f"Successfully submitted stock updates for {success_count} products."
            )
        if fail_count > 0:
            self.message_user(
                request,
                f"Failed to update stock for {fail_count} products.",
                level='warning'
            )
    update_product_stock.short_description = "Update stock in Trendyol"