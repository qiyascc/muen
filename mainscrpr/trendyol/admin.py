from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.html import format_html, mark_safe
from django.forms.widgets import PasswordInput, Textarea
from unfold.admin import ModelAdmin, TabularInline

from .models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct


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
    readonly_fields = ('created_at', 'updated_at', 'last_check_time', 'last_sync_time', 
                      'display_trendyol_link', 'display_batch_id', 'formatted_description', 'preview_image', 'formatted_attributes')
    
    fieldsets = (
        ("Product Information", {"fields": ("title", "description", "formatted_description", "barcode", "product_main_id", "stock_code")}),
        ("Brand and Category", {"fields": ("brand_name", "category_name", "brand_id", "category_id")}),
        ("Price and Stock", {"fields": ("price", "quantity", "vat_rate", "currency_type")}),
        ("Images", {"fields": ("image_url", "preview_image", "additional_images")}),
        ("LCWaikiki Relation", {"fields": ("lcwaikiki_product",)}),
        ("Trendyol Information", {"fields": ("trendyol_id", "trendyol_url", "display_trendyol_link", "attributes", "formatted_attributes")}),
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
    
    actions = ['sync_with_trendyol', 'check_sync_status', 'retry_failed_products', 'refresh_product_data']
    
    def sync_with_trendyol(self, request, queryset):
        """
        Synchronize selected products with Trendyol.
        
        If product already exists on Trendyol (has a barcode), this will only update price and inventory.
        Otherwise, it will create a new product on Trendyol.
        """
        from . import api_client
        import logging
        
        logger = logging.getLogger('trendyol.admin')
        
        new_count = 0
        update_count = 0
        error_count = 0
        
        for product in queryset:
            try:
                logger.info(f"Processing product '{product.title}', barcode: {product.barcode}")
                
                # Check if product already exists on Trendyol
                if product.trendyol_id or product.batch_status == 'completed':
                    # Product exists - update price and inventory only
                    logger.info(f"Product '{product.title}' already exists on Trendyol, updating price and inventory")
                    batch_id = api_client.update_price_and_inventory(product)
                    if batch_id:
                        update_count += 1
                        self.message_user(
                            request, 
                            f"Updated price and inventory for '{product.title}' with batch ID: {batch_id}",
                            level='success'
                        )
                else:
                    # New product - create on Trendyol
                    logger.info(f"Product '{product.title}' is new, creating on Trendyol")
                    batch_id = api_client.create_trendyol_product(product)
                    if batch_id:
                        new_count += 1
                        self.message_user(
                            request, 
                            f"Created new product '{product.title}' with batch ID: {batch_id}",
                            level='success'
                        )
            except Exception as e:
                logger.error(f"Error syncing product {product.title}: {str(e)}")
                self.message_user(
                    request, 
                    f"Error syncing product '{product.title}': {str(e)}", 
                    level='error'
                )
                error_count += 1
        
        if new_count > 0 or update_count > 0:
            summary = []
            if new_count > 0:
                summary.append(f"created {new_count} new products")
            if update_count > 0:
                summary.append(f"updated {update_count} existing products")
                
            self.message_user(
                request, 
                f"Successfully {' and '.join(summary)} on Trendyol. Check status in a few minutes.",
                level='success'
            )
        elif error_count == 0:
            self.message_user(request, "No products were processed.", level='warning')
    
    sync_with_trendyol.short_description = "Sync selected products with Trendyol"
    
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
    
    def formatted_description(self, obj):
        """
        Display formatted HTML description with proper styling and cleaned content.
        """
        if not obj.description:
            return "No description available"
            
        # Clean the description by removing "Satıcı" paragraphs if present
        description = obj.description
        if description and "<p><b>Satıcı:</b>" in description:
            import re
            satici_pattern = r'<p><b>Satıcı:</b>.*?</p>'
            description = re.sub(satici_pattern, '', description)
        
        # Add CSS styling to ensure proper formatting in the admin panel
        styled_html = f"""
        <div style="max-width: 800px; max-height: 400px; overflow: auto; padding: 10px; 
                    border: 1px solid #eee; border-radius: 5px; background-color: #fafafa;">
            {description}
        </div>
        """
        return mark_safe(styled_html)
    formatted_description.short_description = "Formatted Description"
    
    def preview_image(self, obj):
        """
        Display a thumbnail of the product image with a link to the full-size image.
        Also shows additional images if available.
        """
        if not obj.image_url:
            return "No image available"
        
        html = [f"""
        <div style="margin-bottom: 10px;">
            <strong>Main Image:</strong><br>
            <a href="{obj.image_url}" target="_blank">
                <img src="{obj.image_url}" style="max-width: 200px; max-height: 200px; 
                border: 1px solid #ddd; border-radius: 4px; padding: 5px;" />
            </a>
        </div>
        """]
        
        # Check for additional images
        if obj.additional_images:
            additional_urls = []
            
            # Parse additional images from JSON or list
            if isinstance(obj.additional_images, list):
                additional_urls = obj.additional_images
            elif isinstance(obj.additional_images, str):
                try:
                    import json
                    additional_urls = json.loads(obj.additional_images)
                except json.JSONDecodeError:
                    pass
                    
            # Display additional images
            if additional_urls:
                html.append("<div><strong>Additional Images:</strong><br>")
                html.append('<div style="display: flex; flex-wrap: wrap; gap: 10px;">')
                
                for i, img_url in enumerate(additional_urls[:5]):  # Limit to first 5 additional images
                    if img_url:
                        html.append(f"""
                        <a href="{img_url}" target="_blank" title="Additional Image {i+1}">
                            <img src="{img_url}" style="width: 100px; height: 100px; object-fit: cover; 
                            border: 1px solid #ddd; border-radius: 4px; padding: 3px;" />
                        </a>
                        """)
                
                if len(additional_urls) > 5:
                    html.append(f"<div>+{len(additional_urls) - 5} more images</div>")
                    
                html.append('</div></div>')
        
        return mark_safe(''.join(html))
    preview_image.short_description = "Image Preview"
    
    def formatted_attributes(self, obj):
        """
        Display product attributes in a formatted way with proper styling.
        """
        if not obj.attributes:
            return "No attributes available"
            
        # Parse attributes from JSON or list
        attributes = []
        if isinstance(obj.attributes, list):
            attributes = obj.attributes
        elif isinstance(obj.attributes, str):
            try:
                import json
                attributes = json.loads(obj.attributes)
            except json.JSONDecodeError:
                return "Invalid attribute format"
                
        if not attributes:
            return "No attributes available"
            
        # Build HTML for attributes table
        html = ['<div style="max-width: 800px; max-height: 400px; overflow: auto;">']
        html.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">')
        html.append('<thead style="background-color: #f5f5f5;">')
        html.append('<tr>')
        html.append('<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Attribute ID</th>')
        html.append('<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Attribute Name</th>')
        html.append('<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Value ID</th>')
        html.append('<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Value</th>')
        html.append('</tr>')
        html.append('</thead>')
        html.append('<tbody>')
        
        # Add rows for each attribute
        for attr in attributes:
            try:
                attr_id = attr.get('attributeId', '')
                attr_name = attr.get('attributeName', '')
                value_id = attr.get('attributeValueId', '')
                value = attr.get('attributeValue', '')
                
                html.append('<tr>')
                html.append(f'<td style="padding: 8px; border: 1px solid #ddd;">{attr_id}</td>')
                html.append(f'<td style="padding: 8px; border: 1px solid #ddd;">{attr_name}</td>')
                html.append(f'<td style="padding: 8px; border: 1px solid #ddd;">{value_id}</td>')
                html.append(f'<td style="padding: 8px; border: 1px solid #ddd;">{value}</td>')
                html.append('</tr>')
            except Exception as e:
                html.append(f'<tr><td colspan="4" style="padding: 8px; border: 1px solid #ddd; color: red;">Error parsing attribute: {str(e)}</td></tr>')
                
        html.append('</tbody>')
        html.append('</table>')
        html.append('</div>')
        
        return mark_safe(''.join(html))
    formatted_attributes.short_description = "Formatted Attributes"