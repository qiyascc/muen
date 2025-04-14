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
                  'status', 'timestamp')
  list_filter = ('in_stock', 'status', 'timestamp')
  search_fields = ('title', 'product_code', 'url')
  readonly_fields = ('timestamp', )
  list_per_page = 20
  inlines = [ProductSizeInline]
  actions = []

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
