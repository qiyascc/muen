from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.utils.html import format_html
from django.contrib import messages
from django.http import HttpResponseRedirect
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from .models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl
from .product_models import Product, ProductSize, City, Store, SizeStoreStock
from trendyol import api_client
from trendyol.api_helpers import submit_product_to_trendyol, prepare_product_for_submission
from trendyol.fetch_api_data import fetch_all_categories, fetch_all_brands

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
  actions = ['send_to_trendyol']

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
    def process_product(product):
      try:
        # Import at this level to avoid circular imports
        from trendyol.trendyol_api_client import send_lcwaikiki_to_trendyol
        
        # Send to Trendyol using the new function
        success, message, batch_id = send_lcwaikiki_to_trendyol(product)
        
        if success and batch_id:
          self.message_user(
              request,
              f"Product '{product.title}' sent to Trendyol with batch ID: {batch_id}",
              level=messages.SUCCESS)
          return batch_id
        else:
          error_message = f"Failed to send '{product.title}' to Trendyol"
          if message:
            error_message += f": {message}"
          self.message_user(request, error_message, level=messages.ERROR)
          return None
      except Exception as e:
        self.message_user(
            request,
            f"Error sending '{product.title}' to Trendyol: {str(e)}",
            level=messages.ERROR)
        return None

    # Process products in batches
    batch_size = min(
        10, len(valid_products))  # Use smaller batch size for admin actions
    self.message_user(
        request,
        f"Processing {len(valid_products)} products in batches of {batch_size}... This may take a while.",
        level=messages.INFO)

    # Perform batch processing
    success_count, error_count, batch_ids = api_client.batch_process_products(
        valid_products,
        process_product,
        batch_size=batch_size,
        delay=0.5  # Half-second delay between products
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
