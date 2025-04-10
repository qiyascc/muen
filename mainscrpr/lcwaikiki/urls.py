from django.urls import path
from .views import (
    ConfigBrandsAPIView, 
    ProductAvailableUrlsAPIView, 
    ProductDeletedUrlsAPIView, 
    ProductNewUrlsAPIView
)

# API URL patterns
urlpatterns = [
    # Configuration endpoints
    path('api/v1/lcwaikiki/config/brands/', ConfigBrandsAPIView.as_view(), name='config-brands'),
    
    # Product URL endpoints
    path('api/lcwaikiki/product/urls/available/', ProductAvailableUrlsAPIView.as_view(), name='product-available-urls'),
    path('api/lcwaikiki/product/urls/deleted/', ProductDeletedUrlsAPIView.as_view(), name='product-deleted-urls'),
    path('api/lcwaikiki/product/urls/new/', ProductNewUrlsAPIView.as_view(), name='product-new-urls'),
]