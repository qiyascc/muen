from django.apps import AppConfig


class TrendyolConfig(AppConfig):
    name = 'trendyol'
    verbose_name = 'Trendyol Integration'

    def ready(self):
        # Register any signals here
        pass