from rest_framework import serializers
from .models import TrendyolProduct, TrendyolBrand, TrendyolCategory, TrendyolAPIConfig


class TrendyolBrandSerializer(serializers.ModelSerializer):
    """
    Serializer for the TrendyolBrand model.
    """
    class Meta:
        model = TrendyolBrand
        fields = ['id', 'brand_id', 'name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class TrendyolCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for the TrendyolCategory model.
    """
    class Meta:
        model = TrendyolCategory
        fields = ['id', 'category_id', 'name', 'parent_id', 'path', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class TrendyolProductSerializer(serializers.ModelSerializer):
    """
    Serializer for the TrendyolProduct model.
    """
    lcwaikiki_product_title = serializers.CharField(source='lcwaikiki_product.title', read_only=True, allow_null=True)
    lcwaikiki_product_id = serializers.IntegerField(source='lcwaikiki_product.id', allow_null=True, required=False)
    
    class Meta:
        model = TrendyolProduct
        fields = [
            'id', 'title', 'description', 'barcode', 'product_main_id', 'stock_code',
            'brand_name', 'category_name', 'brand_id', 'category_id',
            'price', 'quantity', 'vat_rate', 'currency_type',
            'image_url', 'additional_images', 'attributes',
            'lcwaikiki_product_id', 'lcwaikiki_product_title', 
            'trendyol_id', 'trendyol_url',
            'batch_id', 'batch_status', 'status_message', 
            'last_check_time', 'last_sync_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_check_time', 'last_sync_time',
                           'batch_id', 'batch_status', 'status_message',
                           'trendyol_id', 'trendyol_url']
    
    def create(self, validated_data):
        """
        Create a new TrendyolProduct instance.
        If lcwaikiki_product_id is provided, link to that product.
        """
        from lcwaikiki.models import Product
        
        lcwaikiki_product_id = None
        if 'lcwaikiki_product' in validated_data and validated_data['lcwaikiki_product']:
            lcwaikiki_product_id = validated_data.pop('lcwaikiki_product').get('id', None)
        
        product = TrendyolProduct(**validated_data)
        
        # Link to LCWaikiki product if provided
        if lcwaikiki_product_id:
            try:
                lcwaikiki_product = Product.objects.get(id=lcwaikiki_product_id)
                product.lcwaikiki_product = lcwaikiki_product
            except Product.DoesNotExist:
                pass
        
        product.save()
        return product
    
    def update(self, instance, validated_data):
        """
        Update a TrendyolProduct instance.
        Update lcwaikiki_product link if lcwaikiki_product_id is provided.
        """
        from lcwaikiki.models import Product
        
        lcwaikiki_product_id = None
        if 'lcwaikiki_product' in validated_data:
            lcwaikiki_data = validated_data.pop('lcwaikiki_product', None)
            if lcwaikiki_data:
                lcwaikiki_product_id = lcwaikiki_data.get('id', None)
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update LCWaikiki product link
        if lcwaikiki_product_id:
            try:
                lcwaikiki_product = Product.objects.get(id=lcwaikiki_product_id)
                instance.lcwaikiki_product = lcwaikiki_product
            except Product.DoesNotExist:
                pass
        
        instance.save()
        return instance