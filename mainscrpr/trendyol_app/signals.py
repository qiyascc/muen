from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TrendyolProduct
from .services import create_trendyol_product

@receiver(post_save, sender=TrendyolProduct)
def product_post_save(sender, instance, created, **kwargs):
    if created and not instance.batch_id:
        # Yeni ürün oluşturulduğunda Trendyol'a gönder
        create_trendyol_product(instance)