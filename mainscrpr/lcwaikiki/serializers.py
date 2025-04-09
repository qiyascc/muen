from rest_framework import serializers
from .models import Config


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
