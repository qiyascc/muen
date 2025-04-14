from django.urls import path
from . import views

urlpatterns = [
    # API endpoints
    path('api/products/', views.product_list, name='product_list'),
    path('api/products/<int:product_id>/', views.product_detail, name='product_detail'),
    
    # Admin action URLs
    path('admin/sync-product/<int:product_id>/', views.sync_product_to_trendyol, name='admin:sync_product_to_trendyol'),
    path('admin/check-product-status/<int:product_id>/', views.check_product_status, name='admin:check_product_status'),
    path('admin/update-product-price/<int:product_id>/', views.update_product_price, name='admin:update_product_price'),
    path('admin/update-product-stock/<int:product_id>/', views.update_product_stock, name='admin:update_product_stock'),
    path('admin/check-batch-status/<int:batch_id>/', views.check_batch_status, name='admin:check_batch_status'),
]