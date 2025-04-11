from django.urls import path
from .views import (
    ConfigBrandsAPIView, 
    ProductAvailableUrlsAPIView, 
    ProductDeletedUrlsAPIView, 
    ProductNewUrlsAPIView,
    DashboardView,
    TerminalOutputView,
    ProductsAPIView,
    ProductDetailAPIView,
    CitiesAPIView,
    CityDetailAPIView,
    StoresAPIView,
    StoreDetailAPIView
)

app_name = 'lcwaikiki'

# URL patterns
urlpatterns = [
    # Dashboard
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/terminal-output/', TerminalOutputView.as_view(), name='terminal-output'),
    
    # Configuration endpoints
    path('api/v1/lcwaikiki/config/brands/', ConfigBrandsAPIView.as_view(), name='config-brands'),
    
    # Product URL endpoints
    path('api/lcwaikiki/product/urls/available/', ProductAvailableUrlsAPIView.as_view(), name='product-available-urls'),
    path('api/lcwaikiki/product/urls/deleted/', ProductDeletedUrlsAPIView.as_view(), name='product-deleted-urls'),
    path('api/lcwaikiki/product/urls/new/', ProductNewUrlsAPIView.as_view(), name='product-new-urls'),
    
    # Product Data endpoints
    path('api/lcwaikiki/products/', ProductsAPIView.as_view(), name='products-list'),
    path('api/lcwaikiki/products/<int:id>/', ProductDetailAPIView.as_view(), name='product-detail'),
    
    # City endpoints
    path('api/lcwaikiki/cities/', CitiesAPIView.as_view(), name='cities-list'),
    path('api/lcwaikiki/cities/<str:city_id>/', CityDetailAPIView.as_view(), name='city-detail'),
    
    # Store endpoints
    path('api/lcwaikiki/stores/', StoresAPIView.as_view(), name='stores-list'),
    path('api/lcwaikiki/stores/<str:store_code>/', StoreDetailAPIView.as_view(), name='store-detail'),
]