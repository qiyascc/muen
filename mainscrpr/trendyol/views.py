from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
import logging
import datetime

from .models import TrendyolProduct, TrendyolBrand, TrendyolCategory
from .serializers import TrendyolProductSerializer, TrendyolBrandSerializer, TrendyolCategorySerializer
from . import api_client

logger = logging.getLogger(__name__)


class TrendyolDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard view for Trendyol integration.
    Shows statistics and summary data.
    """
    template_name = 'trendyol/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get statistics
        products_count = TrendyolProduct.objects.count()
        brands_count = TrendyolBrand.objects.count()
        categories_count = TrendyolCategory.objects.count()
        
        pending_count = TrendyolProduct.objects.filter(batch_status='pending').count()
        processing_count = TrendyolProduct.objects.filter(batch_status='processing').count()
        completed_count = TrendyolProduct.objects.filter(batch_status='completed').count()
        failed_count = TrendyolProduct.objects.filter(batch_status='failed').count()
        
        # Recent products
        recent_products = TrendyolProduct.objects.order_by('-created_at')[:10]
        
        context.update({
            'products_count': products_count,
            'brands_count': brands_count,
            'categories_count': categories_count,
            'pending_count': pending_count,
            'processing_count': processing_count,
            'completed_count': completed_count,
            'failed_count': failed_count,
            'recent_products': recent_products,
        })
        
        return context


class SyncStatusView(LoginRequiredMixin, TemplateView):
    """
    View to display synchronization status.
    """
    template_name = 'trendyol/sync_status.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get products by status
        pending_products = TrendyolProduct.objects.filter(batch_status='pending').order_by('-created_at')[:20]
        processing_products = TrendyolProduct.objects.filter(batch_status='processing').order_by('-last_check_time')[:20]
        completed_products = TrendyolProduct.objects.filter(batch_status='completed').order_by('-last_sync_time')[:20]
        failed_products = TrendyolProduct.objects.filter(batch_status='failed').order_by('-last_check_time')[:20]
        
        context.update({
            'pending_products': pending_products,
            'processing_products': processing_products,
            'completed_products': completed_products,
            'failed_products': failed_products,
        })
        
        return context


class TrendyolProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint for TrendyolProduct.
    """
    queryset = TrendyolProduct.objects.all().order_by('-created_at')
    serializer_class = TrendyolProductSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'barcode', 'product_main_id', 'stock_code', 'brand_name', 'category_name']
    ordering_fields = ['title', 'price', 'created_at', 'last_sync_time', 'batch_status']
    
    def get_queryset(self):
        """
        Filter queryset based on query parameters.
        Supports:
        - ?q=search_term (searches all search_fields)
        - ?date=YYYY-MM-DD (filters by created_at date)
        - ?status=status_value (filters by batch_status)
        - ?synced=true|false (filters by whether the product has been synced)
        """
        queryset = super().get_queryset()
        
        # Search query
        query = self.request.query_params.get('q', None)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(barcode__icontains=query) |
                Q(product_main_id__icontains=query) |
                Q(stock_code__icontains=query) |
                Q(brand_name__icontains=query) |
                Q(category_name__icontains=query)
            )
        
        # Date filter
        date_str = self.request.query_params.get('date', None)
        if date_str:
            try:
                date = parse_date(date_str)
                if date:
                    queryset = queryset.filter(
                        created_at__date=date
                    )
            except ValueError:
                pass
        
        # Status filter
        status_value = self.request.query_params.get('status', None)
        if status_value:
            queryset = queryset.filter(batch_status=status_value)
        
        # Synced filter
        synced = self.request.query_params.get('synced', None)
        if synced:
            if synced.lower() == 'true':
                queryset = queryset.filter(last_sync_time__isnull=False)
            elif synced.lower() == 'false':
                queryset = queryset.filter(last_sync_time__isnull=True)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """
        Sync a product with Trendyol.
        """
        product = self.get_object()
        
        try:
            success = api_client.sync_product_to_trendyol(product)
            if success:
                return Response({'status': 'sync initiated'}, status=status.HTTP_200_OK)
            else:
                return Response({'status': 'sync failed'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def check_status(self, request, pk=None):
        """
        Check the synchronization status of a product.
        """
        product = self.get_object()
        
        if not product.batch_id:
            return Response(
                {'status': 'error', 'message': 'No batch ID available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            batch_status = api_client.check_product_batch_status(product)
            return Response({
                'batch_id': product.batch_id,
                'status': batch_status,
                'message': product.status_message,
                'last_check': product.last_check_time,
                'last_sync': product.last_sync_time
            })
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TrendyolBrandViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for TrendyolBrand (read-only).
    """
    queryset = TrendyolBrand.objects.all().order_by('name')
    serializer_class = TrendyolBrandSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'brand_id']
    
    def get_queryset(self):
        """
        Filter queryset based on query parameters.
        """
        queryset = super().get_queryset()
        
        # Search query
        query = self.request.query_params.get('q', None)
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | 
                Q(brand_id__icontains=query)
            )
        
        # Active filter
        active = self.request.query_params.get('active', None)
        if active:
            if active.lower() == 'true':
                queryset = queryset.filter(is_active=True)
            elif active.lower() == 'false':
                queryset = queryset.filter(is_active=False)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def refresh(self, request):
        """
        Refresh all brands from Trendyol.
        """
        try:
            brands = api_client.fetch_brands()
            return Response({'status': 'success', 'count': len(brands)})
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TrendyolCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for TrendyolCategory (read-only).
    """
    queryset = TrendyolCategory.objects.all().order_by('name')
    serializer_class = TrendyolCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'category_id', 'path']
    
    def get_queryset(self):
        """
        Filter queryset based on query parameters.
        """
        queryset = super().get_queryset()
        
        # Search query
        query = self.request.query_params.get('q', None)
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | 
                Q(category_id__icontains=query) |
                Q(path__icontains=query)
            )
        
        # Parent filter
        parent_id = self.request.query_params.get('parent', None)
        if parent_id:
            if parent_id == 'null':
                queryset = queryset.filter(parent_id__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)
        
        # Active filter
        active = self.request.query_params.get('active', None)
        if active:
            if active.lower() == 'true':
                queryset = queryset.filter(is_active=True)
            elif active.lower() == 'false':
                queryset = queryset.filter(is_active=False)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def refresh(self, request):
        """
        Refresh all categories from Trendyol.
        """
        try:
            categories = api_client.fetch_categories()
            return Response({'status': 'success', 'count': len(categories)})
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def attributes(self, request, pk=None):
        """
        Get attributes for a specific category.
        """
        category = self.get_object()
        
        try:
            attributes = api_client.get_required_attributes_for_category(category.category_id)
            return Response(attributes)
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )