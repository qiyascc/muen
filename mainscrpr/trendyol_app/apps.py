from django.apps import AppConfig


class TrendyolAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trendyol_app'
    verbose_name = 'Trendyol API Entegrasyonu'
    
    def ready(self):
        # Import signals
        try:
            from . import signals
        except ImportError:
            pass
            
        # Import scheduler if available
        try:
            from .scheduler import start_scheduler
            # start_scheduler()  # Uncomment when scheduler is ready
        except ImportError:
            pass