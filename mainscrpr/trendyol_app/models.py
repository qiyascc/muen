from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class TrendyolAPIConfig(models.Model):
    seller_id = models.CharField(max_length=100, verbose_name=_("Satıcı ID"))
    supplier_id = models.CharField(max_length=100, verbose_name=_("Tedarikçi ID"), null=True, blank=True)
    api_key = models.CharField(max_length=255, verbose_name=_("API Key"))
    api_secret = models.CharField(max_length=255, verbose_name=_("API Secret"), default="", blank=True)
    base_url = models.CharField(
        max_length=255, 
        default="https://apigw.trendyol.com/integration/",
        verbose_name=_("API Base URL")
    )
    
    # API Endpoints
    products_endpoint = models.CharField(
        max_length=255,
        default="product/sellers/{sellerId}/products",
        verbose_name=_("Ürünler Endpoint")
    )
    product_detail_endpoint = models.CharField(
        max_length=255,
        default="product/sellers/{sellerId}/products",
        verbose_name=_("Ürün Detay Endpoint")
    )
    brands_endpoint = models.CharField(
        max_length=255,
        default="brands",
        verbose_name=_("Markalar Endpoint")
    )
    categories_endpoint = models.CharField(
        max_length=255,
        default="product-categories",
        verbose_name=_("Kategoriler Endpoint")
    )
    category_attributes_endpoint = models.CharField(
        max_length=255,
        default="product-categories/{categoryId}/attributes",
        verbose_name=_("Kategori Özellikleri Endpoint")
    )
    batch_status_endpoint = models.CharField(
        max_length=255,
        default="product/sellers/{sellerId}/products/batch-requests/{batchRequestId}",
        verbose_name=_("Batch Durum Endpoint")
    )
    
    is_active = models.BooleanField(default=True, verbose_name=_("Aktif Mi?"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Trendyol API Konfigürasyonu")
        verbose_name_plural = _("Trendyol API Konfigürasyonları")
    
    def __str__(self):
        return f"Trendyol API Config: {self.seller_id}"
        
    def save(self, *args, **kwargs):
        # Supplier ID otomatik olarak Seller ID'ye eşit olsun
        if not self.supplier_id:
            self.supplier_id = self.seller_id
        super().save(*args, **kwargs)


class TrendyolProduct(models.Model):
    BATCH_STATUS_CHOICES = [
        ('pending', _('Beklemede')),
        ('processing', _('İşleniyor')),
        ('completed', _('Tamamlandı')),
        ('failed', _('Başarısız')),
    ]
    
    barcode = models.CharField(max_length=100, unique=True, verbose_name=_("Barkod"))
    title = models.CharField(max_length=255, verbose_name=_("Başlık"))
    product_main_id = models.CharField(max_length=100, unique=True, verbose_name=_("Ürün Ana ID"))
    brand_name = models.CharField(max_length=255, verbose_name=_("Marka Adı"))
    category_name = models.CharField(max_length=255, verbose_name=_("Kategori Adı"))
    quantity = models.PositiveIntegerField(default=0, verbose_name=_("Stok Miktarı"))
    stock_code = models.CharField(max_length=100, verbose_name=_("Stok Kodu"))
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Liste Fiyatı"))
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Satış Fiyatı"))
    description = models.TextField(verbose_name=_("Açıklama"))
    image_url = models.URLField(verbose_name=_("Resim URL"))
    vat_rate = models.PositiveSmallIntegerField(default=10, verbose_name=_("KDV Oranı"))
    currency_type = models.CharField(max_length=10, default="TRY", verbose_name=_("Para Birimi"))
    
    batch_id = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Batch ID"))
    batch_status = models.CharField(
        max_length=20,
        choices=BATCH_STATUS_CHOICES,
        default='pending',
        verbose_name=_("Batch Durumu")
    )
    status_message = models.TextField(null=True, blank=True, verbose_name=_("Durum Mesajı"))
    last_check_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Son Kontrol Zamanı"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Trendyol Ürünü")
        verbose_name_plural = _("Trendyol Ürünleri")
    
    def __str__(self):
        return f"{self.title} - {self.barcode}"
    
    def set_batch_status(self, status, message=None):
        self.batch_status = status
        if message:
            self.status_message = message
        self.last_check_time = timezone.now()
        self.save(update_fields=['batch_status', 'status_message', 'last_check_time'])
    
    def needs_status_check(self):
        if self.batch_status in ['completed', 'failed']:
            return False
        
        if not self.last_check_time:
            return True
        
        # 2 dakikada bir kontrol et
        return (timezone.now() - self.last_check_time).total_seconds() >= 120