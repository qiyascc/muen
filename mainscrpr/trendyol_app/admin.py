from django.contrib import admin
from django.utils.html import format_html
from .models import TrendyolAPIConfig, TrendyolProduct

@admin.register(TrendyolAPIConfig)
class TrendyolAPIConfigAdmin(admin.ModelAdmin):
    list_display = ('seller_id', 'is_active', 'created_at', 'updated_at')
    search_fields = ('seller_id',)
    list_filter = ('is_active',)


@admin.register(TrendyolProduct)
class TrendyolProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'barcode', 'brand_name', 'category_name', 
                    'quantity', 'price', 'sale_price', 'batch_id', 
                    'batch_status', 'last_check_time')
    list_filter = ('batch_status', 'brand_name')
    search_fields = ('title', 'barcode', 'product_main_id', 'batch_id')
    readonly_fields = ('batch_id', 'batch_status', 'status_message', 'last_check_time', 'display_image')
    fieldsets = (
        (None, {
            'fields': ('barcode', 'title', 'product_main_id', 'brand_name', 'category_name')
        }),
        ('Stok ve Fiyat Bilgileri', {
            'fields': ('quantity', 'stock_code', 'price', 'sale_price', 'vat_rate', 'currency_type')
        }),
        ('Ürün Detayları', {
            'fields': ('description', 'image_url', 'display_image',)
        }),
        ('Trendyol Entegrasyon Durumu', {
            'fields': ('batch_id', 'batch_status', 'status_message', 'last_check_time'),
            'classes': ('collapse',)
        }),
    )
    
    def display_image(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" height="150" />', obj.image_url)
        return "Resim yok"
    display_image.short_description = "Ürün Resmi"
    
    actions = ['check_batch_status', 'send_to_trendyol']
    
    def check_batch_status(self, request, queryset):
        from .services import check_product_batch_status
        updated = 0
        for product in queryset:
            if product.batch_id and product.batch_status != 'completed':
                check_product_batch_status(product)
                updated += 1
        
        self.message_user(request, f"{updated} ürünün batch durumu güncellendi.")
    check_batch_status.short_description = "Seçili ürünlerin batch durumlarını kontrol et"
    
    def send_to_trendyol(self, request, queryset):
        """Seçili ürünleri Trendyol'a gönderir"""
        from .services import TrendyolAPI, TrendyolCategoryFinder, TrendyolProductManager, create_trendyol_product
        from .models import TrendyolAPIConfig
        import json
        
        success_count = 0
        error_count = 0
        
        # API yapılandırmasını al
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            self.message_user(request, "Aktif Trendyol API yapılandırması bulunamadı", level='error')
            return
            
        # API istemcisini oluştur
        api_client = TrendyolAPI(config)
        category_finder = TrendyolCategoryFinder(api_client)
        
        for product in queryset:
            try:
                # Kategori ID'sini GPT-4o ile bul
                if not product.category_id:
                    category_id = category_finder.find_matching_category(product.title, product.description)
                    product.category_id = category_id
                    product.save(update_fields=['category_id'])
                
                # Ürünü Trendyol'a gönder
                batch_id = create_trendyol_product(product)
                
                if batch_id:
                    success_count += 1
                    self.message_user(
                        request, 
                        f"'{product.title}' başarıyla gönderildi. Batch ID: {batch_id}", 
                        level='success'
                    )
                else:
                    error_count += 1
                    self.message_user(
                        request,
                        f"'{product.title}' gönderilemedi. Bir hata oluştu.",
                        level='error'
                    )
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"'{product.title}' gönderilemedi: {str(e)}",
                    level='error'
                )
        
        if success_count > 0:
            self.message_user(
                request,
                f"{success_count} ürün başarıyla Trendyol'a gönderildi. Durumlarını birkaç dakika içinde kontrol edin.",
                level='success'
            )
        
        if error_count > 0:
            self.message_user(
                request,
                f"{error_count} ürün gönderilemedi.",
                level='warning'
            )
    
    send_to_trendyol.short_description = "Seçili ürünleri Trendyol'a gönder"