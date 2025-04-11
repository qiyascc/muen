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
    # Dashboard and sync status views
    path('dashboard/', views.TrendyolDashboardView.as_view(), name='dashboard'),
    path('sync-status/', views.SyncStatusView.as_view(), name='sync-status'),
    
    # API endpoints
    path('api/', include(router.urls)),
]