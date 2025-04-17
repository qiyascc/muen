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
    
    actions = ['check_batch_status']
    
    def check_batch_status(self, request, queryset):
        from .services import check_product_batch_status
        updated = 0
        for product in queryset:
            if product.batch_id and product.batch_status != 'completed':
                check_product_batch_status(product)
                updated += 1
        
        self.message_user(request, f"{updated} ürünün batch durumu güncellendi.")
    check_batch_status.short_description = "Seçili ürünlerin batch durumlarını kontrol et"