from rest_framework import serializers
from .models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl
from .product_models import Product, ProductSize, City, Store, SizeStoreStock


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
        fields = ['id', 'page_id', 'product_id_in_page', 'url', 'last_checking', 'created_at', 'updated_at']
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


# Product Data Model Serializers

class ProductSizeSerializer(serializers.ModelSerializer):
    """
    Serializer for ProductSize model.
    """
    class Meta:
        model = ProductSize
        fields = ['id', 'size_name', 'size_id', 'size_general_stock', 'product_option_size_reference', 'barcode_list']


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for Product model.
    """
    sizes = ProductSizeSerializer(many=True, read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'url', 'title', 'category', 'description', 'product_code', 
                  'color', 'price', 'discount_ratio', 'in_stock', 'images', 
                  'status', 'timestamp', 'sizes']
        read_only_fields = ['timestamp']


class ProductListSerializer(serializers.Serializer):
    """
    Serializer for list of Product objects.
    """
    products = ProductSerializer(many=True, read_only=True)


class CitySerializer(serializers.ModelSerializer):
    """
    Serializer for City model.
    """
    class Meta:
        model = City
        fields = ['city_id', 'name']


class SizeStoreStockSerializer(serializers.ModelSerializer):
    """
    Serializer for SizeStoreStock model.
    """
    class Meta:
        model = SizeStoreStock
        fields = ['id', 'product_size', 'store', 'stock']


class StoreSerializer(serializers.ModelSerializer):
    """
    Serializer for Store model.
    """
    size_stocks = SizeStoreStockSerializer(many=True, read_only=True)
    
    class Meta:
        model = Store
        fields = ['store_code', 'store_name', 'city', 'store_county', 
                  'store_phone', 'address', 'latitude', 'longitude', 'size_stocks']
