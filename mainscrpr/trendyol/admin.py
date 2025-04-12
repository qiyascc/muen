from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.html import format_html
from django.forms.widgets import PasswordInput
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
    
    actions = ['sync_with_trendyol', 'check_sync_status', 'retry_failed_products', 'refresh_product_data']
    
    def sync_with_trendyol(self, request, queryset):
        """
        Synchronize selected products with Trendyol using the updated API client.
        This implementation uses the direct working API endpoints.
        """
        # Using the updated API client
        from .trendyol_api_working import sync_product_to_trendyol, get_api_client_from_config
        from django.utils import timezone
        
        # Verify API client is working
        api_client = get_api_client_from_config()
        if not api_client or not api_client.config:
            self.message_user(request, "API istemcisi başlatılamadı. API yapılandırmasını kontrol edin.", level='error')
            return
            
        self.message_user(request, f"API istemcisi başarıyla başlatıldı: {api_client.config.name} ({api_client.config.seller_id})")
        
        success_count = 0
        error_count = 0
        
        for product in queryset:
            try:
                # Set status to pending
                product.batch_status = 'pending'
                product.status_message = 'İşleme alındı'
                product.save()
                
                self.message_user(request, f"'{product.title}' ürünü Trendyol'a gönderiliyor...")
                
                # Use the sync_product_to_trendyol function which properly handles the product
                result = sync_product_to_trendyol(product)
                
                if result:
                    # Update last sync time
                    product.last_sync_time = timezone.now()
                    product.save()
                    
                    success_count += 1
                    self.message_user(request, f"'{product.title}' ürünü başarıyla senkronize edildi. Batch ID: {product.batch_id}")
                else:
                    error_count += 1
                    self.message_user(request, f"'{product.title}' ürünü senkronize edilemedi. Detaylar: {product.status_message}", level='warning')
            except Exception as e:
                error_count += 1
                self.message_user(request, f"Hata: {product.title} için senkronizasyon hatası: {str(e)}", level='error')
        
        summary = []
        if success_count > 0:
            summary.append(f"{success_count} ürün başarıyla senkronize edildi")
        if error_count > 0:
            summary.append(f"{error_count} ürün senkronize edilemedi")
            
        if summary:
            self.message_user(request, ". ".join(summary) + ".")
    
    sync_with_trendyol.short_description = "Seçili ürünleri Trendyol ile senkronize et"
    
    def check_sync_status(self, request, queryset):
        """
        Check synchronization status for selected products using the updated API client.
        """
        from .trendyol_api_working import check_product_batch_status
        from django.utils import timezone
        
        count = 0
        for product in queryset:
            if product.batch_id:
                try:
                    self.message_user(request, f"'{product.title}' ürününün batch durumu kontrol ediliyor...")
                    result = check_product_batch_status(product)
                    
                    # The status is updated directly in the product by the check_product_batch_status function
                    product.last_check_time = timezone.now()
                    product.save()
                    
                    self.message_user(request, f"'{product.title}' durumu: {product.batch_status.upper()} - {product.status_message}")
                    count += 1
                except Exception as e:
                    self.message_user(request, f"Hata: {product.title} durumu kontrol edilemedi: {str(e)}", level='error')
        
        if count:
            self.message_user(request, f"{count} ürünün durumu başarıyla kontrol edildi.")
        else:
            self.message_user(request, "Batch ID'ye sahip ürün bulunamadı.", level='warning')
    check_sync_status.short_description = "Seçili ürünlerin senkronizasyon durumunu kontrol et"
    
    def retry_failed_products(self, request, queryset):
        """
        Retry failed products with improved attribute handling using the updated API client.
        Specifically uses the TrendyolAPI class which correctly formats attributes.
        """
        from .trendyol_api_working import create_trendyol_product, get_api_client_from_config, TrendyolCategoryFinder
        from django.utils import timezone
        import json
        import re
        
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
            'Petrol': 1016
        }
        
        fixed_count = 0
        success_count = 0
        already_pending_count = 0
        
        # Get API client and category finder
        api_client = get_api_client_from_config()
        if not api_client or not api_client.config:
            self.message_user(request, "API istemcisi başlatılamadı. API yapılandırmasını kontrol edin.", level='error')
            return
            
        self.message_user(request, f"API istemcisi başarıyla başlatıldı: {api_client.config.name} ({api_client.config.seller_id})")
        
        category_finder = TrendyolCategoryFinder(api_client)
        
        for product in queryset:
            try:
                # Skip products that are already in pending or processing status
                if product.batch_status in ['pending', 'processing']:
                    already_pending_count += 1
                    continue
                
                self.message_user(request, f"'{product.title}' ürünü yeniden gönderiliyor...")
                
                # Set to pending status with a placeholder message
                product.batch_status = 'pending'
                product.status_message = 'Yeniden gönderim işlemi başlatıldı'
                product.save()
                
                # Fix color attribute from title if possible
                if not product.attributes or not any(attr.get('attributeId') == 348 for attr in product.attributes):
                    color_match = re.search(r'(Beyaz|Siyah|Mavi|Kirmizi|Pembe|Yeşil|Sarı|Mor|Gri|Kahverengi|Ekru|Bej|Lacivert|Turuncu|Krem|Petrol)', 
                                           product.title, re.IGNORECASE)
                    if color_match:
                        color = color_match.group(1)
                        if color in color_id_map:
                            color_id = color_id_map[color]
                            product.attributes = [{"attributeId": 348, "attributeValueId": color_id}]
                            fixed_count += 1
                            self.message_user(request, f"Renk özelliği eklendi: {color} (ID: {color_id})")
                
                # Find appropriate category if not set
                if not product.category_id:
                    product.category_id = category_finder.find_best_category(product.title, product.description)
                    if product.category_id:
                        fixed_count += 1
                        self.message_user(request, f"Kategori bulundu: ID {product.category_id}")
                
                # Use create_trendyol_product function from trendyol_api_working.py
                batch_id = create_trendyol_product(product)
                if batch_id:
                    product.batch_id = batch_id
                    product.batch_status = 'processing'
                    product.last_sync_time = timezone.now()
                    product.save()
                    success_count += 1
                    self.message_user(request, f"'{product.title}' başarıyla gönderildi. Batch ID: {batch_id}")
                else:
                    self.message_user(request, f"'{product.title}' gönderilemedi.", level='warning')
            except Exception as e:
                self.message_user(request, f"Hata: {product.title} için gönderim hatası: {str(e)}", level='error')
        
        # Report results
        message_parts = []
        if fixed_count:
            message_parts.append(f"{fixed_count} ürünün özellikleri düzeltildi")
        if success_count:
            message_parts.append(f"{success_count} ürün başarıyla Trendyol'a gönderildi")
        if already_pending_count:
            message_parts.append(f"{already_pending_count} ürün zaten işlemde olduğu için atlandı")
            
        if message_parts:
            self.message_user(request, ". ".join(message_parts) + ".")
        else:
            self.message_user(request, "Yeniden gönderilecek uygun ürün bulunamadı.", level='warning')
    
    retry_failed_products.short_description = "Başarısız ürünleri yeniden gönder (öznitelikleri düzelt)"
    
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
            'Petrol': 1016
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
                            f"'{product.title}' ürünü, LC Waikiki ürünü '{matching_product.title}' ile ilişkilendirildi.", 
                            level='success'
                        )
                    else:
                        not_linked_count += 1
                        continue
                
                # Get linked LCWaikiki product
                lcw_product = product.lcwaikiki_product
                if lcw_product:
                    self.message_user(request, f"'{product.title}' ürünü LC Waikiki kaynağından güncelleniyor...")
                    
                    # Update product data
                    product.title = lcw_product.title or product.title
                    product.description = lcw_product.description or product.description
                    product.price = lcw_product.price or product.price
                    product.image_url = lcw_product.images[0] if lcw_product.images else product.image_url
                    
                    # Fix color attribute
                    color = lcw_product.color or None
                    if not color and product.title:
                        color_match = re.search(r'(Beyaz|Siyah|Mavi|Kirmizi|Pembe|Yeşil|Sarı|Mor|Gri|Kahverengi|Ekru|Bej|Lacivert|Turuncu|Krem|Petrol)', 
                                               product.title, re.IGNORECASE)
                        if color_match:
                            color = color_match.group(1)
                    
                    # Apply proper numeric color ID attribute
                    if color and color in color_id_map:
                        color_id = color_id_map[color]
                        product.attributes = [{"attributeId": 348, "attributeValueId": color_id}]
                        attribute_fixed_count += 1
                        self.message_user(request, f"Renk özelliği eklendi: {color} (ID: {color_id})")
                    
                    # Update timestamp
                    product.updated_at = timezone.now()
                    product.save()
                    updated_count += 1
                    self.message_user(request, f"'{product.title}' ürünü başarıyla güncellendi.")
                
            except Exception as e:
                self.message_user(request, f"Hata: {product.title} güncellenirken sorun oluştu: {str(e)}", level='error')
        
        # Report results
        if updated_count:
            self.message_user(
                request, 
                f"{updated_count} ürün başarıyla güncellendi. {attribute_fixed_count} ürünün renk özellikleri düzeltildi."
            )
        if not_linked_count:
            self.message_user(
                request, 
                f"{not_linked_count} ürün için LC Waikiki verisi bulunamadı.", 
                level='warning'
            )
    
    refresh_product_data.short_description = "LC Waikiki'den ürün verilerini güncelle"