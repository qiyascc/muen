from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from .models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl


@admin.register(Config)
class ConfigAdmin(ModelAdmin):
    """
    Admin configuration for the Config model.
    """
    model = Config
    list_display = ('name', 'display_brands', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    
    # Unfold specific configurations
    fieldsets = (
        ("General Information", {"fields": ("name",)}),
        ("Brand Settings", {"fields": ("brands",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
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
        form.base_fields['brands'].help_text = 'Enter brands as a list of strings, e.g. ["lcw-classic", "lcw-abc"]'
        return form


@admin.register(ProductAvailableUrl)
class ProductAvailableUrlAdmin(ModelAdmin):
    """
    Admin configuration for the ProductAvailableUrl model.
    """
    model = ProductAvailableUrl
    list_display = ('page_id', 'product_id_in_page', 'display_url', 'last_checking', 'created_at')
    list_filter = ('last_checking', 'created_at')
    search_fields = ('page_id', 'product_id_in_page', 'url')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    
    # Unfold specific configurations
    fieldsets = (
        ("Product Information", {"fields": ("page_id", "product_id_in_page")}),
        ("URL Details", {"fields": ("url", "last_checking")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )
    
    date_hierarchy = 'last_checking'
    empty_value_display = 'N/A'
    
    def display_url(self, obj):
        """
        Display URL as a clickable link.
        """
        return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)
    
    display_url.short_description = 'URL'


@admin.register(ProductDeletedUrl)
class ProductDeletedUrlAdmin(ModelAdmin):
    """
    Admin configuration for the ProductDeletedUrl model.
    """
    model = ProductDeletedUrl
    list_display = ('display_url', 'last_checking', 'created_at')
    list_filter = ('last_checking', 'created_at')
    search_fields = ('url',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    
    # Unfold specific configurations
    fieldsets = (
        ("URL Details", {"fields": ("url", "last_checking")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )
    
    date_hierarchy = 'last_checking'
    empty_value_display = 'N/A'
    
    def display_url(self, obj):
        """
        Display URL as a clickable link.
        """
        return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)
    
    display_url.short_description = 'URL'


@admin.register(ProductNewUrl)
class ProductNewUrlAdmin(ModelAdmin):
    """
    Admin configuration for the ProductNewUrl model.
    """
    model = ProductNewUrl
    list_display = ('display_url', 'last_checking', 'created_at')
    list_filter = ('last_checking', 'created_at')
    search_fields = ('url',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    
    # Unfold specific configurations
    fieldsets = (
        ("URL Details", {"fields": ("url", "last_checking")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )
    
    date_hierarchy = 'last_checking'
    empty_value_display = 'N/A'
    
    def display_url(self, obj):
        """
        Display URL as a clickable link.
        """
        return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url[:50] + '...' if len(obj.url) > 50 else obj.url)
    
    display_url.short_description = 'URL'





from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect
from django.urls import path
from unfold.admin import ModelAdmin, StackedInline, TabularInline
import requests
import json
from django.contrib import messages

from .models import Product, ProductSize, Store, SizeStoreStock
from config.models import CityConfiguration as City

class ProductSizeInline(TabularInline):
    model = ProductSize
    extra = 0
    fields = ('size_name', 'size_id', 'size_general_stock', 'store_count', 'city_count')
    readonly_fields = ('store_count', 'city_count')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            store_count=Count('store_stocks', distinct=True),
            city_count=Count('store_stocks__store__city', distinct=True)
        )
        return queryset

    def store_count(self, obj):
        return obj.store_count
    store_count.short_description = 'Stores'

    def city_count(self, obj):
        return obj.city_count
    city_count.short_description = 'Cities'

class SizeStoreStockInline(TabularInline):
    model = SizeStoreStock
    extra = 0
    fields = ('store', 'stock')
    autocomplete_fields = ('store',)

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('id', 'title_display', 'category', 'product_code', 'color', 'price', 'discount_ratio', 
                    'in_stock', 'size_count', 'store_count', 'city_count', 'timestamp', 'status')
    list_filter = ('category', 'color', 'in_stock', 'status', 'timestamp',)
    search_fields = ('url', 'title', 'category', 'color', 'product_code')
    inlines = [ProductSizeInline]
    readonly_fields = ('timestamp', 'preview_images', 'store_availability_summary', 'description_display')
    actions = ['refresh_product_data', 'send_to_trendyol']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            size_count=Count('sizes', distinct=True),
            store_count=Count('sizes__store_stocks__store', distinct=True),
            city_count=Count('sizes__store_stocks__store__city', distinct=True)
        )
        return queryset

    def send_to_trendyol(self, request, queryset):
        """Send selected products to Trendyol API"""
        success_count = 0
        error_count = 0

        # Check if we need to batch or send all together
        product_count = queryset.count()

        if product_count <= 2:
            # Process all products in a single API call
            products_data = []

            for product in queryset:
                # Extract product code parts
                product_code = product.product_code.strip() if product.product_code else ""
                barcode = "BRK-" + product_code.split('-', 1)[1] if '-' in product_code else "BRK-" + product_code
                product_main_id = "PMI-" + product_code

                # Get first image URL if available
                image_url = product.images[0] if product.images and len(product.images) > 0 else ""

                # Calculate sale price (if discount_ratio is available)
                price = float(product.price) if product.price else 0.0
                sale_price = price
                if product.discount_ratio and product.discount_ratio > 0:
                    sale_price = round(price * (1 - product.discount_ratio / 100), 2)
                total_quantity = ProductSize.objects.filter(product=product).aggregate(
                    total=Sum('size_general_stock')
                )['total'] or 0

                # Prepare data for Trendyol
                product_data = {
                    "barcode": barcode,
                    "title": product.title or "",
                    "product_main_id": product_main_id,
                    "brand_name": "LC Waikiki",
                    "category_name": product.category or "",
                    "quantity": total_quantity,
                    "stock_code": product_code,
                    "price": str(price),
                    "sale_price": str(sale_price),
                    "description": product.description or "",
                    "image_url": image_url,
                    "vat_rate": 10,
                    "currency_type": "TRY",
                }

                products_data.append(product_data)

            # Create payload with items array
            payload = {
                "items": products_data
            }

            try:
                # Send data to Trendyol API
                response = requests.post(
                    'http://127.0.0.1:8000/api/v1/markets/products/',
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                )

                if response.status_code in [200, 201]:
                    success_count = len(products_data)
                else:
                    error_count = len(products_data)
                    self.message_user(
                        request, 
                        f"Error sending {len(products_data)} products: {response.text}", 
                        level=messages.ERROR
                    )

            except Exception as e:
                error_count = len(products_data)
                self.message_user(
                    request, 
                    f"Error sending products: {str(e)}", 
                    level=messages.ERROR
                )

        else:
            # Process products individually if more than 200
            for product in queryset:
                # Extract product code parts
                product_code = product.product_code.strip() if product.product_code else ""
                barcode = "BRK-" + product_code.split('-', 1)[0] if '-' in product_code else "BRK-" + product_code
                product_main_id = "PMI-" + product_code

                # Get first image URL if available
                image_url = product.images[0] if product.images and len(product.images) > 0 else ""

                # Calculate sale price (if discount_ratio is available)
                price = float(product.price) if product.price else 0.0
                sale_price = price
                if product.discount_ratio and product.discount_ratio > 0:
                    sale_price = round(price * (1 - product.discount_ratio / 100), 2)

                # Prepare data for Trendyol
                trendyol_data = {
                    "barcode": barcode,
                    "title": product.title or "",
                    "product_main_id": product_main_id,
                    "brand_name": "LC Waikiki",
                    "category_name": product.category or "",
                    "quantity": product.sizes.aggregate(total_stock=Sum('size_general_stock'))['total_stock'] or 0,
                    "stock_code": product_code,
                    "price": str(price),
                    "sale_price": str(sale_price),
                    "description": product.description or "",
                    "image_url": image_url,
                    "vat_rate": 10,
                    "currency_type": "TRY",
                }

                try:
                    # Send data to Trendyol API
                    response = requests.post(
                        'http://127.0.0.1:8000/api/v1/markets/products/',
                        json=trendyol_data,
                        headers={'Content-Type': 'application/json'}
                    )

                    if response.status_code in [200, 201]:
                        success_count += 1
                    else:
                        error_count += 1
                        self.message_user(
                            request, 
                            f"Error sending product {product.id}: {response.text}", 
                            level=messages.ERROR
                        )

                except Exception as e:
                    error_count += 1
                    self.message_user(
                        request, 
                        f"Error sending product {product.id}: {str(e)}", 
                        level=messages.ERROR
                    )

        if success_count > 0:
            self.message_user(
                request, 
                f"Successfully sent {success_count} products to Trendyol.", 
                level=messages.SUCCESS
            )

        if error_count > 0:
            self.message_user(
                request, 
                f"Failed to send {error_count} products to Trendyol. Check details above.", 
                level=messages.WARNING
            )

    send_to_trendyol.short_description = "Send selected products to Trendyol"
    def title_display(self, obj):
        if obj.title:
            display_title = obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
            return format_html('<a href="{}" target="_blank">{}</a>', obj.url, display_title)
        return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url)
    title_display.short_description = 'Title'

    def preview_images(self, obj):
        if not obj.images:
            return "No images available"

        html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
        for img_url in obj.images[:5]:  # Limit to first 5 images
            html += f'<a href="{img_url}" target="_blank"><img src="{img_url}" style="max-width: 100px; max-height: 100px;"></a>'

        if len(obj.images) > 5:
            html += f'<p>And {len(obj.images) - 5} more images...</p>'

        html += '</div>'
        return format_html(html)
    preview_images.short_description = 'Product Images'

    def description_display(self, obj):
        if obj.description:
            return format_html(obj.description)
        return "-"

    description_display.short_description = "Description"

    def refresh_product_data(self, request, queryset):
        from .tasks import process_product

        count = 0
        for product in queryset:
            process_product(product.url)
            count += 1

        self.message_user(request, f"Started refreshing data for {count} products.")
    refresh_product_data.short_description = "Refresh product data"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('update-product-data/', self.admin_site.admin_view(self.update_product_data_view), 
                 name='lcwaikiki_product_api_update_product_data'),
        ]
        return custom_urls + urls

    def update_product_data_view(self, request):
        from .views import update_product_data
        return update_product_data(request)



    def size_count(self, obj):
        return obj.size_count
    size_count.short_description = 'Sizes'
    size_count.admin_order_field = 'size_count'

    def store_count(self, obj):
        return obj.store_count
    store_count.short_description = 'Stores'
    store_count.admin_order_field = 'store_count'

    def city_count(self, obj):
        return obj.city_count
    city_count.short_description = 'Cities'
    city_count.admin_order_field = 'city_count'

    def store_availability_summary(self, obj):
        """Display a summary of store availability for this product"""
        from django.db.models import Sum

        # Get sizes with store stocks
        sizes_with_stocks = ProductSize.objects.filter(product=obj).prefetch_related(
            'store_stocks', 'store_stocks__store', 'store_stocks__store__city'
        )

        if not sizes_with_stocks.exists():
            return "No store availability data"

        html = '<div style="max-height: 400px; overflow-y: auto;">'
        html += '<table style="border-collapse: collapse; width: 100%;">'
        html += '<tr style="background-color: #f2f2f2;">'
        html += '<th style="border: 1px solid #ddd; padding: 8px; text-align: left;">City</th>'
        html += '<th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Store</th>'
        html += '<th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Size</th>'
        html += '<th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Stock</th>'
        html += '</tr>'

        # Group by city, then store, then size
        cities = {}

        for size in sizes_with_stocks:
            for stock in size.store_stocks.all():
                city_name = stock.store.city.name
                store_name = stock.store.store_name

                if city_name not in cities:
                    cities[city_name] = {}

                if store_name not in cities[city_name]:
                    cities[city_name][store_name] = []

                cities[city_name][store_name].append({
                    'size': size.size_name,
                    'stock': stock.stock
                })

        # Sort cities alphabetically
        for city_name in sorted(cities.keys()):
            city_stores = cities[city_name]
            city_total = sum(sum(item['stock'] for item in size_data) for store_name, size_data in city_stores.items())

            html += f'<tr style="background-color: #e6f2ff;">'
            html += f'<td colspan="3" style="border: 1px solid #ddd; padding: 8px;"><strong>{city_name}</strong></td>'
            html += f'<td style="border: 1px solid #ddd; padding: 8px;"><strong>Total: {city_total}</strong></td>'
            html += '</tr>'

            # Sort stores alphabetically
            for store_name in sorted(city_stores.keys()):
                store_sizes = city_stores[store_name]
                store_total = sum(item['stock'] for item in store_sizes)

                html += f'<tr style="background-color: #f9f9f9;">'
                html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                html += f'<td colspan="2" style="border: 1px solid #ddd; padding: 8px;"><strong>{store_name}</strong></td>'
                html += f'<td style="border: 1px solid #ddd; padding: 8px;"><strong>Total: {store_total}</strong></td>'
                html += '</tr>'

                # Sort sizes
                for size_data in sorted(store_sizes, key=lambda x: x['size']):
                    html += f'<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{size_data["size"]}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{size_data["stock"]}</td>'
                    html += '</tr>'

        html += '</table>'
        html += '</div>'

        return format_html(html)
    store_availability_summary.short_description = 'Store Availability'

@admin.register(ProductSize)
class ProductSizeAdmin(ModelAdmin):
    list_display = ('id', 'product_title', 'size_name', 'size_id', 'size_general_stock', 'store_count')
    list_filter = ('size_name', 'size_general_stock')  
    search_fields = ('product__title', 'size_name', 'size_id')
    inlines = [SizeStoreStockInline]
    autocomplete_fields = ('product',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(store_count=Count('store_stocks', distinct=True))
        queryset = queryset.select_related('product')
        return queryset

    def product_title(self, obj):
        if obj.product.title:
            display_title = obj.product.title[:50] + '...' if len(obj.product.title) > 50 else obj.product.title
            return format_html('<a href="{}" target="_blank">{}</a>', obj.product.url, display_title)
        return format_html('<a href="{}" target="_blank">{}</a>', obj.product.url, obj.product.url)
    product_title.short_description = 'Product'
    product_title.admin_order_field = 'product__title'

    def store_count(self, obj):
        return obj.store_count
    store_count.short_description = 'Stores'
    store_count.admin_order_field = 'store_count'

# @admin.register(City)
# class CityAdmin(ModelAdmin):
#     list_display = ('city_id', 'name', 'store_count', 'product_count')
#     search_fields = ('city_id', 'name')

#     def get_queryset(self, request):
#         queryset = super().get_queryset(request)
#         queryset = queryset.annotate(
#             store_count=Count('stores', distinct=True),
#             product_count=Count('stores__size_stocks__product_size__product', distinct=True)
#         )
#         return queryset

#     def store_count(self, obj):
#         return obj.store_count
#     store_count.short_description = 'Stores'
#     store_count.admin_order_field = 'store_count'

#     def product_count(self, obj):
#         return obj.product_count
#     product_count.short_description = 'Products'
#     product_count.admin_order_field = 'product_count'

@admin.register(Store)
class StoreAdmin(ModelAdmin):
    list_display = ('store_code', 'store_name', 'city', 'store_county', 'store_phone', 'product_count', 'total_stock')
    list_filter = ('city', 'store_county')
    search_fields = ('store_code', 'store_name', 'store_county', 'store_phone', 'address')
    autocomplete_fields = ('city',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            product_count=Count('size_stocks__product_size__product', distinct=True),
            total_stock=Sum('size_stocks__stock')
        )
        queryset = queryset.select_related('city')
        return queryset

    def product_count(self, obj):
        return obj.product_count
    product_count.short_description = 'Products'
    product_count.admin_order_field = 'product_count'

    def total_stock(self, obj):
        return obj.total_stock or 0
    total_stock.short_description = 'Total Stock'
    total_stock.admin_order_field = 'total_stock'

@admin.register(SizeStoreStock)
class SizeStoreStockAdmin(ModelAdmin):
    list_display = ('id', 'product_info', 'size_name', 'store_name', 'stock')
    list_filter = ('stock', 'store__city')
    search_fields = ('product_size__product__title', 'product_size__size_name', 'store__store_name')
    autocomplete_fields = ('product_size', 'store')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('product_size', 'product_size__product', 'store', 'store__city')
        return queryset

    def product_info(self, obj):
        if obj.product_size.product.title:
            display_title = obj.product_size.product.title[:40] + '...' if len(obj.product_size.product.title) > 40 else obj.product_size.product.title
            return format_html('<a href="{}" target="_blank">{}</a>', obj.product_size.product.url, display_title)
        return format_html('<a href="{}" target="_blank">{}</a>', obj.product_size.product.url, obj.product_size.product.url)
    product_info.short_description = 'Product'

    def size_name(self, obj):
        return obj.product_size.size_name
    size_name.short_description = 'Size'
    size_name.admin_order_field = 'product_size__size_name'

    def store_name(self, obj):
        return f"{obj.store.store_name} ({obj.store.city.name})"
    store_name.short_description = 'Store'
    store_name.admin_order_field = 'store__store_name'


@admin.action(description='Apply price configuration')
def apply_price_config(modeladmin, request, queryset):
    from config.utils import apply_price_configuration
    for product in queryset:
        product.price = apply_price_configuration(product.price)
        product.save()