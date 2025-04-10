"""
URL configuration for mainscrpr project.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('lcwaikiki.urls')),  # Include all lcwaikiki URLs directly
    path('', RedirectView.as_view(url='/admin/', permanent=False)),  # Redirect root URL to admin
]
