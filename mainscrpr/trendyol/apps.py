"""
Django app configuration for Trendyol integration
"""
from django.apps import AppConfig

class TrendyolConfig(AppConfig):
    name = 'trendyol'
    verbose_name = 'Trendyol'
    
    def ready(self):
        """
        Initialize app when Django starts
        """
        pass