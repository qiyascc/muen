from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
import json
import time
from django.utils.html import format_html
from django.contrib import messages
from django.http import HttpResponseRedirect
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from .models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl
from .product_models import Product, ProductSize, City, Store, SizeStoreStock
from trendyol_app.services import create_trendyol_product
from .sopyo_api import send_product_to_sopyo

# Product Models Admin Configuration


class ProductSizeInline(TabularInline):
  """
    Inline admin for ProductSize model.
    """
  model = ProductSize
  extra = 0
  fields = ('size_name', 'size_id', 'size_general_stock',
            'product_option_size_reference')


@admin.register(Product)
class ProductAdmin(ModelAdmin):
  """
    Admin configuration for the Product model.
    """
  model = Product
  list_display = ('title', 'product_code', 'color', 'price', 'in_stock',
                  'status', 'trendyol_batch_id', 'timestamp')
  list_filter = ('in_stock', 'status', 'timestamp')
  search_fields = ('title', 'product_code', 'url')
  readonly_fields = ('timestamp', )
  list_per_page = 20
  inlines = [ProductSizeInline]
  actions = ['send_to_trendyol', 'send_to_sopyo']

  # Unfold specific configurations
  fieldsets = (
      ("Product Information", {
          "fields": ("title", "product_code", "category", "color")
      }),
      ("Details", {
          "fields":
          ("description", "price", "discount_ratio", "in_stock", "status")
      }),
      ("URL and Images", {
          "fields": ("url", "images")
      }),
      ("Metadata", {
          "fields": ("timestamp", )
      }),
  )

  date_hierarchy = 'timestamp'
  empty_value_display = 'N/A'

  def trendyol_batch_id(self, obj):
    """
        Display Trendyol batch ID if product has been sent to Trendyol.
        """
    try:
      trendyol_product = obj.trendyol_products.first()
      if trendyol_product and trendyol_product.batch_id:
        status_color = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red'
        }.get(trendyol_product.batch_status, 'gray')

        return format_html('<span style="color: {};">{} ({})</span>',
                           status_color, trendyol_product.batch_id,
                           trendyol_product.batch_status)
      return 'Not sent'
    except Exception:
      return 'Error'

  trendyol_batch_id.short_description = 'Trendyol Batch'

  def send_to_trendyol(self, request, queryset):
    """
        Action to send selected products to Trendyol.
        This implementation uses batch processing for better performance and
        to avoid overwhelming the Trendyol API with too many requests at once.
        """
    if not queryset.exists():
      self.message_user(request,
                        "No products selected to send to Trendyol",
                        level=messages.ERROR)
      return

    # Filter out products that are not in stock
    valid_products = []
    skipped_products = []

    for product in queryset:
      if not product.in_stock:
        skipped_products.append(product)
      else:
        valid_products.append(product)

    # Show warnings for skipped products
    for product in skipped_products:
      self.message_user(
          request,
          f"Product '{product.title}' is not in stock and was skipped",
          level=messages.WARNING)

    if not valid_products:
      self.message_user(request,
                        "No in-stock products to send to Trendyol",
                        level=messages.WARNING)
      return

    # Define processing function
    def process_product(product, variant_data=None):
      """
      Process a product for Trendyol submission
      
      Args:
          product: The LCWaikiki Product to process
          variant_data: Optional dict with variant info, e.g. {'size': 'M', 'stock': 10}
      """
      try:
        # Gerekli modül ve işlevleri import et
        from trendyol_app.services import create_trendyol_product, TrendyolAPI, TrendyolCategoryFinder
        from trendyol_app.models import TrendyolAPIConfig, TrendyolProduct
        import logging
        import json

        logger = logging.getLogger('lcwaikiki.admin')
        
        # Varyant bilgisini kaydet
        variant_desc = ""
        if variant_data:
            variant_size = variant_data.get('size')
            variant_stock = variant_data.get('stock')
            variant_desc = f" (Size: {variant_size})"
            logger.info(f"Processing variant for product {product.id}: Size={variant_size}, Stock={variant_stock}")
            self.message_user(
                request,
                f"Processing size variant '{variant_size}' with stock {variant_stock} for product '{product.title}'",
                level=messages.INFO)
        
        # LCWaikiki ürününü Trendyol ürününe dönüştür
        try:
            # Varolan Trendyol ürününü kontrol et
            trendyol_product = TrendyolProduct.objects.filter(lcwaikiki_product=product).first()
            
            # Eğer yoksa yeni oluştur
            if not trendyol_product:
                trendyol_product = TrendyolProduct()
                trendyol_product.lcwaikiki_product = product
            
            # Ürün bilgilerini doldur
            trendyol_product.barcode = product.product_code
            trendyol_product.product_main_id = product.product_code
            trendyol_product.title = product.title
            trendyol_product.description = product.description or product.title
            trendyol_product.brand_name = "LC Waikiki"
            trendyol_product.brand_id = 102  # LC Waikiki brand ID
            trendyol_product.category_name = product.category
            
            # Stok bilgisini ayarla
            if variant_data:
                trendyol_product.quantity = variant_data.get('stock')
                trendyol_product.stock_code = f"{product.product_code}-{variant_data.get('size')}"
            else:
                trendyol_product.quantity = product.get_total_stock()
                trendyol_product.stock_code = product.product_code
            
            # Fiyat bilgilerini ayarla
            trendyol_product.price = product.price
            trendyol_product.sale_price = product.get_discounted_price()
            
            # Varsayılan vergi oranı
            trendyol_product.vat_rate = 18
            
            # Resim URL'sini ayarla
            product_images = product.get_images()
            if product_images and len(product_images) > 0:
                trendyol_product.image_url = product_images[0]
            
            # Para birimi
            trendyol_product.currency_type = "TRY"
            
            # Ürünü kaydet
            trendyol_product.save()
            
            logger.info(f"Converted LCWaikiki product {product.id} to TrendyolProduct with ID {trendyol_product.id}")
        except Exception as e:
            self.message_user(
                request,
                f"Failed to convert '{product.title}{variant_desc}' to Trendyol format: {str(e)}",
                level=messages.ERROR)
            logger.error(f"Error converting product {product.id}: {str(e)}")
            return None

        # API config al
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            self.message_user(
                request,
                f"No active Trendyol API configuration found. Cannot send '{product.title}{variant_desc}'",
                level=messages.ERROR)
            return None
        
        # Ürünü Trendyol'a gönder
        try:
            # create_trendyol_product fonksiyonunu çağır
            batch_id = create_trendyol_product(trendyol_product)
            
            if batch_id:
                # Başarılı gönderim
                self.message_user(
                    request,
                    f"Product '{product.title}{variant_desc}' sent to Trendyol with batch ID: {batch_id}",
                    level=messages.SUCCESS)
                return batch_id
            else:
                # Gönderim başarısız
                self.message_user(
                    request,
                    f"Failed to send '{product.title}{variant_desc}' to Trendyol. No batch ID returned.",
                    level=messages.ERROR)
                return None
        except Exception as e:
            # Hata durumunda
            self.message_user(
                request,
                f"Failed to send '{product.title}{variant_desc}' to Trendyol: {str(e)}",
                level=messages.ERROR)
            logger.error(f"Error sending product {trendyol_product.id} to Trendyol: {str(e)}")
            return None
      except Exception as e:
        variant_desc = f" (Size: {variant_data.get('size')})" if variant_data else ""
        self.message_user(
            request,
            f"Error sending '{product.title}{variant_desc}' to Trendyol: {str(e)}",
            level=messages.ERROR)
        return None

    # Process products in batches
    batch_size = min(
        10, len(valid_products))  # Use smaller batch size for admin actions
    self.message_user(
        request,
        f"Processing {len(valid_products)} products in batches of {batch_size}... This may take a while.",
        level=messages.INFO)

    # Manually batch process the products
    success_count = 0
    error_count = 0
    batch_ids = []
    
    # Process in batches
    for i in range(0, len(valid_products), batch_size):
        batch = valid_products[i:i+batch_size]
        
        for product in batch:
            try:
                # Check if this product has size variants
                sizes = product.sizes.filter(size_general_stock__gt=0)
                
                # If product has sizes with stock > 0, process each size as a variant
                if sizes.exists():
                    self.message_user(
                        request, 
                        f"Product '{product.title}' has {sizes.count()} size variants, processing each separately",
                        level=messages.INFO
                    )
                    
                    # Process each size as a separate Trendyol product
                    for size in sizes:
                        variant_data = {
                            'size': size.size_name,
                            'stock': size.size_general_stock
                        }
                        
                        batch_id = process_product(product, variant_data)
                        if batch_id:
                            success_count += 1
                            batch_ids.append(batch_id)
                        else:
                            error_count += 1
                        
                        # Small delay to avoid overwhelming the API
                        time.sleep(0.5)
                else:
                    # Process as a single product without variants
                    batch_id = process_product(product)
                    if batch_id:
                        success_count += 1
                        batch_ids.append(batch_id)
                    else:
                        error_count += 1
                    
                    # Small delay to avoid overwhelming the API
                    time.sleep(0.5)
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Error processing product {product.title}: {str(e)}",
                    level=messages.ERROR
                )

    # Show summary message
    if success_count > 0:
      self.message_user(
          request,
          f"Successfully sent {success_count} products to Trendyol with batch IDs: {', '.join(batch_ids[:5])}{'...' if len(batch_ids) > 5 else ''}",
          level=messages.SUCCESS)

    if error_count > 0:
      self.message_user(
          request,
          f"{error_count} products failed to send. Check the messages above for details.",
          level=messages.WARNING if success_count > 0 else messages.ERROR)

  send_to_trendyol.short_description = "Send selected products to Trendyol"
  
  def send_to_sopyo(self, request, queryset):
    """
    Action to send selected products to Sopyo platform.
    This implementation selects products and sends them to Sopyo in batches.
    """
    if not queryset.exists():
      self.message_user(request,
                        "No products selected to send to Sopyo",
                        level=messages.ERROR)
      return

    # Filter out products that are not in stock
    valid_products = []
    skipped_products = []

    for product in queryset:
      if not product.in_stock:
        skipped_products.append(product)
      else:
        valid_products.append(product)

    # Show warnings for skipped products
    for product in skipped_products:
      self.message_user(
          request,
          f"Product '{product.title}' is not in stock and was skipped",
          level=messages.WARNING)

    if not valid_products:
      self.message_user(request,
                        "No in-stock products to send to Sopyo",
                        level=messages.WARNING)
      return

    # Process products in batches
    batch_size = min(5, len(valid_products))  # Kullanıcı arayüzü için daha küçük batch boyutu
    self.message_user(
        request,
        f"Processing {len(valid_products)} products in batches of {batch_size}... This may take a while.",
        level=messages.INFO)

    # Ürünlerin ID'lerini topla
    product_ids = [product.id for product in valid_products]
    
    try:
      # API'ye bağlan ve ürünleri gönder
      from .sopyo_api import send_multiple_products_to_sopyo
      result = send_multiple_products_to_sopyo(product_ids, limit=min(10, len(product_ids)))
      
      if result.get("status", False):
        results = result.get('results', {})
        self.message_user(
            request,
            f"Sopyo API'ye gönderim tamamlandı: {results.get('success', 0)}/{results.get('total', 0)} ürün başarıyla gönderildi.",
            level=messages.SUCCESS)
            
        # Başarısız ürünleri göster
        if results.get('failed', 0) > 0:
          for item in results.get('details', []):
            if not item.get('result', {}).get('status', False):
              self.message_user(
                  request,
                  f"Ürün ID: {item.get('product_id')}, Başlık: {item.get('title')}, Hata: {item.get('result', {}).get('message', 'Bilinmeyen hata')}",
                  level=messages.WARNING)
      else:
        self.message_user(
            request,
            f"Sopyo API hatası: {result.get('message', 'Bilinmeyen hata')}",
            level=messages.ERROR)
    
    except Exception as e:
      self.message_user(
          request,
          f"Sopyo API entegrasyonu hatası: {str(e)}",
          level=messages.ERROR)
      
  send_to_sopyo.short_description = "Send selected products to Sopyo"


@admin.register(City)
class CityAdmin(ModelAdmin):
  """
    Admin configuration for the City model.
    """
  model = City
  list_display = ('city_id', 'name')
  search_fields = ('city_id', 'name')
  list_per_page = 20

  # Unfold specific configurations
  fieldsets = (("City Information", {"fields": ("city_id", "name")}), )


class SizeStoreStockInline(TabularInline):
  """
    Inline admin for SizeStoreStock model.
    """
  model = SizeStoreStock
  extra = 0
  fields = ('product_size', 'stock')


@admin.register(Store)
class StoreAdmin(ModelAdmin):
  """
    Admin configuration for the Store model.
    """
  model = Store
  list_display = ('store_name', 'city', 'store_county', 'store_phone')
  list_filter = ('city', )
  search_fields = ('store_name', 'store_code', 'address')
  list_per_page = 20
  inlines = [SizeStoreStockInline]

  # Unfold specific configurations
  fieldsets = (
      ("Store Information", {
          "fields": ("store_code", "store_name", "city")
      }),
      ("Contact Information", {
          "fields": ("store_county", "store_phone", "address")
      }),
      ("Location", {
          "fields": ("latitude", "longitude")
      }),
  )


@admin.register(Config)
class ConfigAdmin(ModelAdmin):
  """
    Admin configuration for the Config model.
    """
  model = Config
  list_display = ('name', 'display_brands', 'created_at', 'updated_at')
  search_fields = ('name', )
  readonly_fields = ('created_at', 'updated_at')
  list_per_page = 20

  # Unfold specific configurations
  fieldsets = (
      ("General Information", {
          "fields": ("name", )
      }),
      ("Brand Settings", {
          "fields": ("brands", )
      }),
      ("Metadata", {
          "fields": ("created_at", "updated_at")
      }),
  )

  date_hierarchy = 'created_at'
  empty_value_display = 'N/A'

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
    form.base_fields[
        'brands'].help_text = 'Enter brands as a list of strings, e.g. ["lcw-classic", "lcw-abc"]'
    return form


@admin.register(ProductAvailableUrl)
class ProductAvailableUrlAdmin(ModelAdmin):
  """
    Admin configuration for the ProductAvailableUrl model.
    """
  model = ProductAvailableUrl
  list_display = ('page_id', 'product_id_in_page', 'display_url',
                  'last_checking', 'created_at')
  list_filter = ('last_checking', 'created_at')
  search_fields = ('page_id', 'product_id_in_page', 'url')
  readonly_fields = ('created_at', 'updated_at')
  list_per_page = 20

  # Unfold specific configurations
  fieldsets = (
      ("Product Information", {
          "fields": ("page_id", "product_id_in_page")
      }),
      ("URL Details", {
          "fields": ("url", "last_checking")
      }),
      ("Metadata", {
          "fields": ("created_at", "updated_at")
      }),
  )

  date_hierarchy = 'last_checking'
  empty_value_display = 'N/A'

  def display_url(self, obj):
    """
        Display URL as a clickable link.
        """
    return format_html('<a href="{}" target="_blank">{}</a>', obj.url,
                       obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)

  display_url.short_description = 'URL'


@admin.register(ProductDeletedUrl)
class ProductDeletedUrlAdmin(ModelAdmin):
  """
    Admin configuration for the ProductDeletedUrl model.
    """
  model = ProductDeletedUrl
  list_display = ('display_url', 'last_checking', 'created_at')
  list_filter = ('last_checking', 'created_at')
  search_fields = ('url', )
  readonly_fields = ('created_at', 'updated_at')
  list_per_page = 20

  # Unfold specific configurations
  fieldsets = (
      ("URL Details", {
          "fields": ("url", "last_checking")
      }),
      ("Metadata", {
          "fields": ("created_at", "updated_at")
      }),
  )

  date_hierarchy = 'last_checking'
  empty_value_display = 'N/A'

  def display_url(self, obj):
    """
        Display URL as a clickable link.
        """
    return format_html('<a href="{}" target="_blank">{}</a>', obj.url,
                       obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)

  display_url.short_description = 'URL'


@admin.register(ProductNewUrl)
class ProductNewUrlAdmin(ModelAdmin):
  """
    Admin configuration for the ProductNewUrl model.
    """
  model = ProductNewUrl
  list_display = ('display_url', 'last_checking', 'created_at')
  list_filter = ('last_checking', 'created_at')
  search_fields = ('url', )
  readonly_fields = ('created_at', 'updated_at')
  list_per_page = 20

  # Unfold specific configurations
  fieldsets = (
      ("URL Details", {
          "fields": ("url", "last_checking")
      }),
      ("Metadata", {
          "fields": ("created_at", "updated_at")
      }),
  )

  date_hierarchy = 'last_checking'
  empty_value_display = 'N/A'

  def display_url(self, obj):
    """
        Display URL as a clickable link.
        """
    return format_html('<a href="{}" target="_blank">{}</a>', obj.url,
                       obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)

  display_url.short_description = 'URL'
