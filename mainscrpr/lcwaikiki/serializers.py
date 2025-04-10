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
