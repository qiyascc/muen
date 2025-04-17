from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import TrendyolProduct
from .serializers import TrendyolProductSerializer
from .services import check_product_batch_status

class TrendyolProductViewSet(viewsets.ModelViewSet):
    queryset = TrendyolProduct.objects.all()
    serializer_class = TrendyolProductSerializer
    
    @action(detail=True, methods=['post'])
    def check_status(self, request, pk=None):
        product = self.get_object()
        
        if not product.batch_id:
            return Response(
                {'error': 'Bu ürün henüz Trendyol\'a gönderilmemiş'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            check_product_batch_status(product)
            return Response({
                'batch_id': product.batch_id,
                'batch_status': product.batch_status,
                'status_message': product.status_message,
                'last_check_time': product.last_check_time
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )