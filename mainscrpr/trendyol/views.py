import json
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

from .models import TrendyolProduct, TrendyolBrand, TrendyolCategory, TrendyolAPIConfig
from .serializers import TrendyolProductSerializer, TrendyolBrandSerializer, TrendyolCategorySerializer
from .api_client import get_api_client, check_product_batch_status, get_product_manager


class TrendyolProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Trendyol products.
    """
    queryset = TrendyolProduct.objects.all().order_by('-created_at')
    serializer_class = TrendyolProductSerializer
    
    def get_queryset(self):
        queryset = TrendyolProduct.objects.all().order_by('-created_at')
        
        # Filter by search query
        query = self.request.query_params.get('q', None)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(barcode__icontains=query) |
                Q(product_main_id__icontains=query) |
                Q(stock_code__icontains=query)
            )
        
        # Filter by date
        date_str = self.request.query_params.get('date', None)
        if date_str:
            try:
                date = parse_date(date_str)
                if date:
                    queryset = queryset.filter(
                        created_at__date=date
                    )
            except:
                pass
        
        # Pagination parameters
        page = self.request.query_params.get('page', None)
        in_page = self.request.query_params.get('in_page', None)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """
        Sync a product to Trendyol.
        """
        # Import directly from our implementation
        from .api_client import sync_product_to_trendyol
        
        product = self.get_object()
        try:
            batch_id = sync_product_to_trendyol(product)
            
            # If we got a batch_id, the sync was successful
            return Response({
                'success': True,
                'message': f"Product synced to Trendyol with batch ID: {batch_id}",
                'product_id': product.id,
                'batch_id': batch_id,
                'batch_status': product.batch_status
            })
        except Exception as e:
            # Log the error
            import logging
            logger = logging.getLogger('trendyol.views')
            logger.error(f"Failed to sync product {product.id}: {str(e)}")
            
            # Return error response
            return Response({
                'success': False,
                'message': f"Failed to sync product: {str(e)}",
                'product_id': product.id,
                'batch_id': product.batch_id,
                'batch_status': product.batch_status
            }, status=400)


class TrendyolBrandViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Trendyol brands.
    """
    queryset = TrendyolBrand.objects.all()
    serializer_class = TrendyolBrandSerializer


class TrendyolCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Trendyol categories.
    """
    queryset = TrendyolCategory.objects.all()
    serializer_class = TrendyolCategorySerializer


@method_decorator(staff_member_required, name='dispatch')
class BatchStatusView(TemplateView):
    """
    View to check the status of a batch request.
    """
    template_name = 'trendyol/batch_status.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        original_batch_id = kwargs.get('batch_id')
        context['batch_id'] = original_batch_id
        
        # DEBUG: Konsola tam batch ID'yi yazdır (original_batch_id)
        print(f"[DEBUG-VIEW] Orijinal batch ID: {original_batch_id}")
        
        # Get the API client
        client = get_api_client()
        if not client:
            context['error'] = "Aktif bir Trendyol API yapılandırması bulunamadı. Lütfen önce API yapılandırmasını ayarlayın."
            return context
        
        try:
            # Debug için batch ID'yi yazdır, API istemcisine gönderilmeden önce
            print(f"[DEBUG-VIEW] API istemcisine gönderilecek batch ID: {original_batch_id}")
            
            # Batch ID'yi değiştirmeden kullan (orijinal olarak tut)
            batch_id = original_batch_id
            
            # Debug için son durumu yazdır
            print(f"[DEBUG-VIEW] API isteği öncesi son batch ID: {batch_id}")
            
            # Create product manager instance for checking batch status
            product_manager = get_product_manager()
            
            # Get batch status from API using our manager
            response = product_manager.check_batch_status(batch_id)
            
            # Process the response to build a structured status object
            if response:
                status = {}
                
                # If the response is a dictionary, extract the relevant fields
                if isinstance(response, dict):
                    status = {
                        'source': json.dumps(response, indent=2),
                        'status': response.get('status', 'UNKNOWN'),
                        'creationDate': response.get('creationDate'),
                        'lastModification': response.get('lastModification'),
                        'itemCount': response.get('itemCount', 0),
                        'failedItemCount': response.get('failedItemCount', 0),
                        'items': response.get('items', [])
                    }
                # If the response is a string, try to parse it as JSON
                elif isinstance(response, str):
                    try:
                        resp_data = json.loads(response)
                        status = {
                            'source': response,
                            'status': resp_data.get('status', 'UNKNOWN'),
                            'creationDate': resp_data.get('creationDate'),
                            'lastModification': resp_data.get('lastModification'),
                            'itemCount': resp_data.get('itemCount', 0),
                            'failedItemCount': resp_data.get('failedItemCount', 0),
                            'items': resp_data.get('items', [])
                        }
                    except json.JSONDecodeError:
                        status = {
                            'source': response,
                            'status': 'RAW_RESPONSE',
                            'message': response
                        }
                
                context['status'] = status
            else:
                context['error'] = "API'den yanıt alınamadı. Batch ID geçerli olmayabilir veya API erişim sorunu olabilir."
        except Exception as e:
            context['error'] = f"Batch durumu kontrol edilirken hata oluştu: {str(e)}"
        
        return context