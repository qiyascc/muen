from rest_framework import generics, status, filters
from rest_framework.response import Response
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
import datetime
import os
from .models import Config, ProductAvailableUrl, ProductDeletedUrl, ProductNewUrl
from .product_models import Product, ProductSize, City, Store, SizeStoreStock
from .serializers import (
    ConfigSerializer, BrandsSerializer, 
    ProductAvailableUrlSerializer, ProductAvailableUrlListSerializer,
    ProductDeletedUrlSerializer, ProductDeletedUrlListSerializer,
    ProductNewUrlSerializer, ProductNewUrlListSerializer,
    ProductSerializer, ProductListSerializer, ProductSizeSerializer,
    CitySerializer, StoreSerializer, SizeStoreStockSerializer
)
from .dashboard import DashboardView


class TerminalOutputView(LoginRequiredMixin, TemplateView):
    """
    View to handle AJAX requests for terminal output.
    Shows real-time console output from both log files and system output.
    """
    template_name = 'lcwaikiki/terminal_output.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Combine multiple sources for comprehensive output
        terminal_output = []
        
        # 1. Try to get Django server logs from system logs
        try:
            import subprocess
            # Get Django development server logs (recent logs - last 30 lines)
            result = subprocess.run(
                ["tail", "-n", "30", "/tmp/django.log"], 
                capture_output=True, 
                text=True, 
                check=False
            )
            if result.stdout:
                terminal_output.append("=== DJANGO SERVER LOGS ===")
                terminal_output.append(result.stdout)
            
            # If we don't have Django logs, try the supervisor logs
            if not result.stdout:
                result = subprocess.run(
                    ["tail", "-n", "30", "/tmp/supervisor.log"], 
                    capture_output=True, 
                    text=True, 
                    check=False
                )
                if result.stdout:
                    terminal_output.append("=== SUPERVISOR LOGS ===")
                    terminal_output.append(result.stdout)
        except Exception as e:
            terminal_output.append(f"Error getting server logs: {str(e)}")
        
        # 2. Create logs directory if it doesn't exist
        log_path = os.path.join('logs', 'scraper.log')
        os.makedirs('logs', exist_ok=True)
        
        # If the log file doesn't exist yet, create it
        if not os.path.exists(log_path):
            with open(log_path, 'w') as f:
                f.write("Scraper log initialized at: {}".format(timezone.now()))
        
        # Read the log file for application logs
        try:
            with open(log_path, 'r') as f:
                log_content = f.readlines()[-50:]  # Get last 50 lines
                if log_content:
                    terminal_output.append("\n=== APPLICATION LOGS ===")
                    terminal_output.append(''.join(log_content))
        except Exception as e:
            terminal_output.append(f"\nError reading application log file: {str(e)}")
            
        # 3. Try to get console output by checking standard output files
        try:
            if os.path.exists('/tmp/stdout.log'):
                result = subprocess.run(
                    ["tail", "-n", "20", "/tmp/stdout.log"], 
                    capture_output=True, 
                    text=True, 
                    check=False
                )
                if result.stdout:
                    terminal_output.append("\n=== CONSOLE OUTPUT ===")
                    terminal_output.append(result.stdout)
        except Exception as e:
            terminal_output.append(f"\nError getting console output: {str(e)}")
        
        # If we have no data yet, check if we can get any output
        if not terminal_output:
            try:
                result = subprocess.run(
                    ["ps", "aux"], 
                    capture_output=True, 
                    text=True, 
                    check=False
                )
                if result.stdout:
                    terminal_output.append("\n=== RUNNING PROCESSES ===")
                    terminal_output.append(result.stdout)
            except Exception as e:
                terminal_output.append(f"\nError getting process list: {str(e)}")
        
        # Combine all the output
        context['terminal_output'] = "\n".join(terminal_output)
        
        return context


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


# Product Data API Views

class ProductsAPIView(generics.ListAPIView):
    """
    API view to list products.
    
    Query parameters:
    - q: Search query that looks in title, product_code, or description
    - date: Filter by date (YYYY-MM-DD)
    - category: Filter by category
    - in_stock: Filter by in_stock status (true/false)
    """
    serializer_class = ProductSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp', 'price']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = Product.objects.all().prefetch_related('sizes')
        
        # Generic search
        search_query = self.request.query_params.get('q', None)
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(product_code__icontains=search_query) |
                Q(description__icontains=search_query)
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
                    queryset = queryset.filter(timestamp__range=(start_of_day, end_of_day))
            except (ValueError, TypeError):
                pass  # Invalid date format, ignore filter
        
        # Category filter
        category_param = self.request.query_params.get('category', None)
        if category_param:
            queryset = queryset.filter(category__icontains=category_param)
            
        # In stock filter
        in_stock_param = self.request.query_params.get('in_stock', None)
        if in_stock_param is not None:
            in_stock_value = in_stock_param.lower() == 'true'
            queryset = queryset.filter(in_stock=in_stock_value)
                
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'products': serializer.data})


class ProductDetailAPIView(generics.RetrieveAPIView):
    """
    API view to retrieve a single product by its ID.
    """
    queryset = Product.objects.all().prefetch_related('sizes')
    serializer_class = ProductSerializer
    lookup_field = 'id'


class CitiesAPIView(generics.ListAPIView):
    """
    API view to list cities.
    """
    queryset = City.objects.all()
    serializer_class = CitySerializer
    

class CityDetailAPIView(generics.RetrieveAPIView):
    """
    API view to retrieve a single city by its ID.
    """
    queryset = City.objects.all()
    serializer_class = CitySerializer
    lookup_field = 'city_id'


class StoresAPIView(generics.ListAPIView):
    """
    API view to list stores.
    
    Query parameters:
    - q: Search query that looks in store_name, store_code, or address
    - city: Filter by city_id
    """
    serializer_class = StoreSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['store_name', 'city']
    ordering = ['city', 'store_name']
    
    def get_queryset(self):
        queryset = Store.objects.all().prefetch_related('size_stocks__product_size')
        
        # Generic search
        search_query = self.request.query_params.get('q', None)
        if search_query:
            queryset = queryset.filter(
                Q(store_name__icontains=search_query) |
                Q(store_code__icontains=search_query) |
                Q(address__icontains=search_query)
            )
        
        # City filter
        city_param = self.request.query_params.get('city', None)
        if city_param:
            queryset = queryset.filter(city__city_id=city_param)
                
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'stores': serializer.data})


class StoreDetailAPIView(generics.RetrieveAPIView):
    """
    API view to retrieve a single store by its code.
    """
    queryset = Store.objects.all().prefetch_related('size_stocks__product_size')
    serializer_class = StoreSerializer
    lookup_field = 'store_code'
