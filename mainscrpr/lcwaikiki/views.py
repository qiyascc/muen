from rest_framework import generics, status, filters
from rest_framework.response import Response
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils import timezone
import datetime
from .models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl
from .serializers import (
    ConfigSerializer, BrandsSerializer, 
    ProductAvailableUrlSerializer, ProductAvailableUrlListSerializer,
    ProductDeletedUrlSerializer, ProductDeletedUrlListSerializer,
    ProductNewUrlSerializer, ProductNewUrlListSerializer
)


class ConfigBrandsAPIView(generics.RetrieveAPIView):
    """
    API view to retrieve brands from the Config model.
    This endpoint returns the brands field of the first Config object in the database.
    If no Config object exists, it returns an empty list.
    """
    serializer_class = BrandsSerializer
    
    def get_object(self):
        """
        Get the first Config object or create a default one if none exists.
        """
        config, created = Config.objects.get_or_create(
            name='default',
            defaults={'brands': []}
        )
        return config
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve the brands field and return it directly.
        """
        instance = self.get_object()
        return Response({'brands': instance.brands})


class ProductAvailableUrlsAPIView(generics.ListAPIView):
    """
    API view to list available product URLs.
    
    Query parameters:
    - q: Search query that looks in all fields
    - date: Filter by date (YYYY-MM-DD)
    - page: Filter by page_id
    - in_page: Filter by product_id_in_page
    """
    serializer_class = ProductAvailableUrlSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['last_checking', 'created_at', 'updated_at']
    ordering = ['-last_checking']
    
    def get_queryset(self):
        queryset = ProductAvailableUrl.objects.all()
        
        # Generic search
        search_query = self.request.query_params.get('q', None)
        if search_query:
            queryset = queryset.filter(
                Q(page_id__icontains=search_query) |
                Q(product_id_in_page__icontains=search_query) |
                Q(url__icontains=search_query)
            )
        
        # Date filter
        date_param = self.request.query_params.get('date', None)
        if date_param:
            try:
                search_date = parse_date(date_param)
                if search_date:
                    start_of_day = datetime.datetime.combine(search_date, datetime.time.min)
                    end_of_day = datetime.datetime.combine(search_date, datetime.time.max)
                    start_of_day = timezone.make_aware(start_of_day)
                    end_of_day = timezone.make_aware(end_of_day)
                    queryset = queryset.filter(last_checking__range=(start_of_day, end_of_day))
            except (ValueError, TypeError):
                pass  # Invalid date format, ignore filter
                
        # Page filter
        page_param = self.request.query_params.get('page_id', None)
        if page_param:
            queryset = queryset.filter(page_id=page_param)
            
        # Product ID in page filter
        in_page_param = self.request.query_params.get('in_page', None)
        if in_page_param:
            queryset = queryset.filter(product_id_in_page=in_page_param)
            
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'urls': serializer.data})


class ProductDeletedUrlsAPIView(generics.ListAPIView):
    """
    API view to list deleted product URLs.
    
    Query parameters:
    - q: Search query that looks in URL
    - date: Filter by date (YYYY-MM-DD)
    """
    serializer_class = ProductDeletedUrlSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['last_checking', 'created_at', 'updated_at']
    ordering = ['-last_checking']
    
    def get_queryset(self):
        queryset = ProductDeletedUrl.objects.all()
        
        # Generic search
        search_query = self.request.query_params.get('q', None)
        if search_query:
            queryset = queryset.filter(url__icontains=search_query)
        
        # Date filter
        date_param = self.request.query_params.get('date', None)
        if date_param:
            try:
                search_date = parse_date(date_param)
                if search_date:
                    start_of_day = datetime.datetime.combine(search_date, datetime.time.min)
                    end_of_day = datetime.datetime.combine(search_date, datetime.time.max)
                    start_of_day = timezone.make_aware(start_of_day)
                    end_of_day = timezone.make_aware(end_of_day)
                    queryset = queryset.filter(last_checking__range=(start_of_day, end_of_day))
            except (ValueError, TypeError):
                pass  # Invalid date format, ignore filter
                
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'deleted_urls': serializer.data})


class ProductNewUrlsAPIView(generics.ListAPIView):
    """
    API view to list new product URLs.
    
    Query parameters:
    - q: Search query that looks in URL
    - date: Filter by date (YYYY-MM-DD)
    """
    serializer_class = ProductNewUrlSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['last_checking', 'created_at', 'updated_at']
    ordering = ['-last_checking']
    
    def get_queryset(self):
        queryset = ProductNewUrl.objects.all()
        
        # Generic search
        search_query = self.request.query_params.get('q', None)
        if search_query:
            queryset = queryset.filter(url__icontains=search_query)
        
        # Date filter
        date_param = self.request.query_params.get('date', None)
        if date_param:
            try:
                search_date = parse_date(date_param)
                if search_date:
                    start_of_day = datetime.datetime.combine(search_date, datetime.time.min)
                    end_of_day = datetime.datetime.combine(search_date, datetime.time.max)
                    start_of_day = timezone.make_aware(start_of_day)
                    end_of_day = timezone.make_aware(end_of_day)
                    queryset = queryset.filter(last_checking__range=(start_of_day, end_of_day))
            except (ValueError, TypeError):
                pass  # Invalid date format, ignore filter
                
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'new_urls': serializer.data})
