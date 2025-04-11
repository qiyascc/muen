from rest_framework import serializers
from .models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl


class ConfigSerializer(serializers.ModelSerializer):
  """
    Serializer for the Config model.
    """

  class Meta:
    model = Config
    fields = ['id', 'name', 'brands', 'created_at', 'updated_at']
    read_only_fields = ['created_at', 'updated_at']


class BrandsSerializer(serializers.ModelSerializer):
  """
    Serializer for just the brands field of the Config model.
    """

  class Meta:
    model = Config
    fields = ['brands']


class ProductAvailableUrlSerializer(serializers.ModelSerializer):
  """
    Serializer for ProductAvailableUrl model.
    """

  class Meta:
    model = ProductAvailableUrl
    fields = [
        'id', 'page_id', 'product_id_in_page', 'url', 'last_checking',
        'created_at', 'updated_at'
    ]
    read_only_fields = ['created_at', 'updated_at']


class ProductAvailableUrlListSerializer(serializers.Serializer):
  """
    Serializer for list of ProductAvailableUrl objects.
    """
  urls = ProductAvailableUrlSerializer(many=True, read_only=True)


class ProductDeletedUrlSerializer(serializers.ModelSerializer):
  """
    Serializer for ProductDeletedUrl model.
    """

  class Meta:
    model = ProductDeletedUrl
    fields = ['id', 'url', 'last_checking', 'created_at', 'updated_at']
    read_only_fields = ['created_at', 'updated_at']


class ProductDeletedUrlListSerializer(serializers.Serializer):
  """
    Serializer for list of ProductDeletedUrl objects.
    """
  deleted_urls = ProductDeletedUrlSerializer(many=True, read_only=True)


class ProductNewUrlSerializer(serializers.ModelSerializer):
  """
    Serializer for ProductNewUrl model.
    """

  class Meta:
    model = ProductNewUrl
    fields = ['id', 'url', 'last_checking', 'created_at', 'updated_at']
    read_only_fields = ['created_at', 'updated_at']


class ProductNewUrlListSerializer(serializers.Serializer):
  """
    Serializer for list of ProductNewUrl objects.
    """
  new_urls = ProductNewUrlSerializer(many=True, read_only=True)


# serializers.py
from rest_framework import serializers
from .models import Product, ProductSize, SizeStoreStock, Store
from .models import CityConfiguration as City


class StoreStockSerializer(serializers.ModelSerializer):

  class Meta:
    model = SizeStoreStock
    fields = '__all__'


class CityStockSerializer(serializers.ModelSerializer):
  stores = StoreStockSerializer(many=True, read_only=True)

  class Meta:
    model = City
    fields = '__all__'


class ProductSizeSerializer(serializers.ModelSerializer):
  city_stocks = CityStockSerializer(many=True, read_only=True)

  class Meta:
    model = ProductSize
    fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
  sizes = ProductSizeSerializer(many=True, read_only=True)

  class Meta:
    model = Product
    fields = '__all__'
    depth = 2


class StoreSerializer(serializers.ModelSerializer):
  city_name = serializers.CharField(source='city.name', read_only=True)

  class Meta:
    model = Store
    fields = ('store_code', 'store_name', 'city_name', 'store_county',
              'store_phone', 'address')


class SizeStoreStockSerializer(serializers.ModelSerializer):
  store = StoreSerializer(read_only=True)

  class Meta:
    model = SizeStoreStock
    fields = ('store', 'stock')


class ProductSizeDetailSerializer(serializers.ModelSerializer):
  store_stocks = SizeStoreStockSerializer(many=True, read_only=True)
  total_stock = serializers.SerializerMethodField()
  city_availability = serializers.SerializerMethodField()

  class Meta:
    model = ProductSize
    fields = ('id', 'size_name', 'size_id', 'size_general_stock',
              'total_stock', 'store_stocks', 'city_availability')

  def get_total_stock(self, obj):
    """Calculate total stock across all stores"""
    return sum(stock.stock for stock in obj.store_stocks.all())

  def get_city_availability(self, obj):
    """Group stock by city"""
    city_data = {}

    for stock in obj.store_stocks.all():
      city_id = stock.store.city.city_id
      city_name = stock.store.city.name

      if city_id not in city_data:
        city_data[city_id] = {
            'city_id': city_id,
            'name': city_name,
            'total_stock': 0,
            'store_count': 0,
            'stores': {}
        }

      city_data[city_id]['total_stock'] += stock.stock

      store_code = stock.store.store_code
      if store_code not in city_data[city_id]['stores']:
        city_data[city_id]['stores'][store_code] = {
            'store_code': store_code,
            'store_name': stock.store.store_name,
            'stock': stock.stock
        }
        city_data[city_id]['store_count'] += 1

    # Convert to list and sort by total stock (descending)
    result = list(city_data.values())
    for city in result:
      city['stores'] = list(city['stores'].values())
      city['stores'].sort(key=lambda x: x['stock'], reverse=True)

    result.sort(key=lambda x: x['total_stock'], reverse=True)
    return result


class ProductDetailSerializer(serializers.ModelSerializer):
  sizes = ProductSizeDetailSerializer(many=True, read_only=True)
  total_sizes = serializers.SerializerMethodField()
  available_sizes = serializers.SerializerMethodField()
  city_availability = serializers.SerializerMethodField()

  class Meta:
    model = Product
    fields = '__all__'

  def get_total_sizes(self, obj):
    return obj.sizes.count()

  def get_available_sizes(self, obj):
    return obj.sizes.filter(size_general_stock__gt=0).count()

  def get_city_availability(self, obj):
    """Aggregate city availability across all sizes"""
    from django.db.models import Sum
    from collections import defaultdict

    city_data = defaultdict(
        lambda: {
            'city_id': '',
            'name': '',
            'total_stock': 0,
            'size_count': 0,
            'store_count': set()
        })

    # Get all sizes with their store stocks
    sizes = obj.sizes.prefetch_related('store_stocks', 'store_stocks__store',
                                       'store_stocks__store__city')

    for size in sizes:
      for stock in size.store_stocks.all():
        if stock.stock <= 0:
          continue

        city = stock.store.city
        city_id = city.city_id

        if not city_data[city_id]['city_id']:
          city_data[city_id]['city_id'] = city_id
          city_data[city_id]['name'] = city.name

        city_data[city_id]['total_stock'] += stock.stock
        city_data[city_id]['store_count'].add(stock.store.store_code)

    # Count sizes available in each city
    for city_id in city_data:
      sizes_in_city = set()
      for size in sizes:
        has_stock_in_city = size.store_stocks.filter(
            store__city__city_id=city_id, stock__gt=0).exists()

        if has_stock_in_city:
          sizes_in_city.add(size.id)

      city_data[city_id]['size_count'] = len(sizes_in_city)
      # Convert set to count
      city_data[city_id]['store_count'] = len(
          city_data[city_id]['store_count'])

    # Convert to list and sort by total stock
    result = list(city_data.values())
    result.sort(key=lambda x: x['total_stock'], reverse=True)
    return result


class ProductListSerializer(serializers.ModelSerializer):
  size_count = serializers.IntegerField(read_only=True)
  store_count = serializers.IntegerField(read_only=True)
  city_count = serializers.IntegerField(read_only=True)

  class Meta:
    model = Product
    fields = ('id', 'url', 'title', 'category', 'color', 'price',
              'product_code', 'discount_ratio', 'in_stock', 'size_count',
              'store_count', 'city_count', 'timestamp', 'status')
