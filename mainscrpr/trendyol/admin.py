from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.html import format_html
from django.forms.widgets import PasswordInput
from unfold.admin import ModelAdmin, TabularInline

from .models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct
from .openai_processor import create_trendyol_product_with_ai, prepare_product_with_ai

# Import improved modules (with fallback to originals if import fails)
try:
    from .category_finder_improved import TrendyolCategoryFinderImproved
    from .openai_processor_improved import ProductAttributeProcessor
    IMPROVED_MODULES_AVAILABLE = True
except ImportError:
    IMPROVED_MODULES_AVAILABLE = False
    from .category_finder import TrendyolCategoryFinder


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
    
    actions = ['sync_with_trendyol', 'sync_with_trendyol_ai', 'sync_with_improved_ai', 'check_sync_status', 'retry_failed_products', 'refresh_product_data']
    
    def sync_with_trendyol(self, request, queryset):
        """
        Synchronize selected products with Trendyol.
        """
        from . import api_client
        
        count = 0
        for product in queryset:
            try:
                batch_id = api_client.create_trendyol_product(product)
                if batch_id:
                    count += 1
            except Exception as e:
                self.message_user(request, f"Error syncing product {product.title}: {str(e)}", level='error')
        
        if count:
            self.message_user(request, f"Successfully initiated sync for {count} products. Check status in a few minutes.")
    sync_with_trendyol.short_description = "Sync selected products with Trendyol"
    
    def sync_with_trendyol_ai(self, request, queryset):
        """
        Synchronize selected products with Trendyol using OpenAI for optimizing attributes.
        """
        count = 0
        for product in queryset:
            try:
                batch_id = create_trendyol_product_with_ai(product)
                if batch_id:
                    count += 1
            except Exception as e:
                self.message_user(request, f"Error syncing product with AI {product.title}: {str(e)}", level='error')
        
        if count:
            self.message_user(request, f"Successfully initiated AI-powered sync for {count} products. OpenAI was used to optimize product details and attributes. Check status in a few minutes.")
        else:
            self.message_user(request, "No products were sent to Trendyol. Please check error messages.", level='warning')
    sync_with_trendyol_ai.short_description = "Sync with Trendyol (AI-powered)"
    
    def sync_with_improved_ai(self, request, queryset):
        """
        Synchronize products with Trendyol using improved category finder and OpenAI processor.
        This method doesn't require mandatory fields and works without storing categories locally.
        """
        from . import api_client
        count = 0
        
        if not IMPROVED_MODULES_AVAILABLE:
            self.message_user(request, 
                "Improved AI modules are not available. Using standard AI processing instead.", 
                level='warning')
            return self.sync_with_trendyol_ai(request, queryset)
            
        # Initialize the improved category finder and processor
        try:
            api = api_client.get_api_client()
            category_finder = TrendyolCategoryFinderImproved(api)
            processor = ProductAttributeProcessor(category_finder)
            
            for product in queryset:
                try:
                    # Get LCWaikiki product if linked
                    lcw_product = product.lcwaikiki_product
                    
                    if lcw_product:
                        # Process with AI - no mandatory fields required
                        enhanced_data = processor.optimize_product_data(lcw_product)
                        
                        # Update product with enhanced data
                        if 'title' in enhanced_data:
                            product.title = enhanced_data['title']
                        
                        if 'description' in enhanced_data:
                            product.description = enhanced_data['description']
                        
                        if 'categoryId' in enhanced_data:
                            product.category_id = enhanced_data['categoryId']
                        
                        if 'attributes' in enhanced_data:
                            product.attributes = enhanced_data['attributes']
                        
                        product.batch_status = 'pending'
                        product.status_message = 'Prepared with improved AI processing'
                        product.save()
                        
                        # Send to Trendyol
                        batch_id = api_client.create_trendyol_product(product)
                        if batch_id:
                            count += 1
                    else:
                        self.message_user(
                            request, 
                            f"Product '{product.title}' is not linked to an LCWaikiki product", 
                            level='warning'
                        )
                        
                except Exception as e:
                    self.message_user(
                        request, 
                        f"Error processing product '{product.title}' with improved AI: {str(e)}", 
                        level='error'
                    )
            
            if count:
                self.message_user(
                    request, 
                    f"Successfully processed {count} products with improved AI. " +
                    "This method doesn't require mandatory fields and works without local category storage."
                )
            else:
                self.message_user(
                    request, 
                    "No products were sent to Trendyol. Please check error messages.", 
                    level='warning'
                )
                
        except Exception as e:
            self.message_user(
                request, 
                f"Error initializing improved AI processing: {str(e)}", 
                level='error'
            )
    sync_with_improved_ai.short_description = "Sync with Trendyol (Improved AI - No mandatory fields)"
    
    def check_sync_status(self, request, queryset):
        """
        Check synchronization status for selected products.
        """
        from . import api_client
        
        count = 0
        for product in queryset:
            if product.batch_id:
                try:
                    api_client.check_product_batch_status(product)
                    count += 1
                except Exception as e:
                    self.message_user(request, f"Error checking status for {product.title}: {str(e)}", level='error')
        
        if count:
            self.message_user(request, f"Successfully checked status for {count} products.")
        else:
            self.message_user(request, "No products with batch IDs were found.", level='warning')
    check_sync_status.short_description = "Check sync status for selected products"
    
    def retry_failed_products(self, request, queryset):
        """
        Retry failed products with improved attribute handling.
        Specifically removes the problematic 'color' field and uses proper attribute IDs.
        """
        from . import api_client
        import json
        import re
        
        fixed_count = 0
        success_count = 0
        already_pending_count = 0
        
        # Color ID mapping to use numeric IDs instead of string values
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
                # Skip products that are already in pending or processing status
                if product.batch_status in ['pending', 'processing']:
                    already_pending_count += 1
                    continue
                    
                # Clear existing attributes to let the API provide the correct ones
                product.attributes = []
                fixed_count += 1
                
                # Set to pending status with a placeholder message
                product.batch_status = 'pending'
                product.status_message = 'Pending retry after fix'
                product.save()
                
                # Step 2: Just use the regular prepare_product_data - no need for customization
                # as we've already cleared attributes and removed the gender field
                
                # Call the standard API client which now works correctly without color field
                try:
                    batch_id = api_client.create_trendyol_product(product)
                    if batch_id:
                        success_count += 1
                except Exception as e:
                    self.message_user(request, f"API error for {product.title}: {str(e)}", level='error')
            except Exception as e:
                self.message_user(request, f"Error retrying product {product.title}: {str(e)}", level='error')
        
        # Report results
        message_parts = []
        if fixed_count:
            message_parts.append(f"Fixed attributes for {fixed_count} products")
        if success_count:
            message_parts.append(f"Successfully submitted {success_count} products to Trendyol")
        if already_pending_count:
            message_parts.append(f"Skipped {already_pending_count} products already in pending/processing state")
            
        if message_parts:
            self.message_user(request, ". ".join(message_parts) + ".")
        else:
            self.message_user(request, "No products were eligible for retry.", level='warning')
    
    retry_failed_products.short_description = "Retry failed products (fix attributes & color)"
    
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