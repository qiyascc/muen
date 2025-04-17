from rest_framework import serializers
from .models import TrendyolProduct

class TrendyolProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrendyolProduct
        fields = '__all__'
        read_only_fields = ('batch_id', 'batch_status', 'status_message', 'last_check_time')