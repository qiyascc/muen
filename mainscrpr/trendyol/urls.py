from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'trendyol'

# API router setup
router = DefaultRouter()
router.register(r'products', views.TrendyolProductViewSet, basename='product')
router.register(r'brands', views.TrendyolBrandViewSet, basename='brand')
router.register(r'categories', views.TrendyolCategoryViewSet, basename='category')

urlpatterns = [
    # Batch status view
    path('batch-status/<str:batch_id>/', views.BatchStatusView.as_view(), name='batch_status'),
    
    # API endpoints
    path('api/', include(router.urls)),
]