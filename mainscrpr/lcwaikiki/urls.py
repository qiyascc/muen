from django.urls import path
from .views import (
    ConfigBrandsAPIView,
    ProductAvailableUrlsAPIView,
    ProductDeletedUrlsAPIView,
    ProductNewUrlsAPIView
)

urlpatterns = [
    path('lcwaikiki/config/brands/', ConfigBrandsAPIView.as_view(), name='config-brands'),
    path('lcwaikiki/product/urls/available/', ProductAvailableUrlsAPIView.as_view(), name='product-available-urls'),
    path('lcwaikiki/product/urls/deleted/', ProductDeletedUrlsAPIView.as_view(), name='product-deleted-urls'),
    path('lcwaikiki/product/urls/new/', ProductNewUrlsAPIView.as_view(), name='product-new-urls'),
]
