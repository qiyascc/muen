from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'trendyol_app'

router = DefaultRouter()
router.register(r'products', views.TrendyolProductViewSet)

urlpatterns = [
    path('', include(router.urls)),
]