from django.urls import path
from .views import ConfigBrandsAPIView

urlpatterns = [
    path('lcwaikiki/config/brands/', ConfigBrandsAPIView.as_view(), name='config-brands'),
]
