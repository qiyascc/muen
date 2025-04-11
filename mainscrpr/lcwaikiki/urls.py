from django.urls import path
from .views import (ConfigBrandsAPIView, ProductAvailableUrlsAPIView,
                    ProductDeletedUrlsAPIView, ProductNewUrlsAPIView,
                    DashboardView, TerminalOutputView, RefreshProductDataView)

app_name = 'lcwaikiki'

# URL patterns
urlpatterns = [
    # Dashboard
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/terminal-output/',
         TerminalOutputView.as_view(),
         name='terminal-output'),

    # Configuration endpoints
    path('api/v1/lcwaikiki/config/brands/',
         ConfigBrandsAPIView.as_view(),
         name='config-brands'),

    # Product URL endpoints
    path('api/lcwaikiki/product/urls/available/',
         ProductAvailableUrlsAPIView.as_view(),
         name='product-available-urls'),
    path('api/lcwaikiki/product/urls/deleted/',
         ProductDeletedUrlsAPIView.as_view(),
         name='product-deleted-urls'),
    path('api/lcwaikiki/product/urls/new/',
         ProductNewUrlsAPIView.as_view(),
         name='product-new-urls'),
  
    path('api/lcwaikiki/product/refresh-products/',
         RefreshProductDataView.as_view(),
         name='refresh-products'),
]
