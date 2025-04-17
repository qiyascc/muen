"""
Django yönetim komutu: Bekleyen ürünleri kontrol etme

Bu komut, tüm bekleyen Trendyol ürünlerinin batch durumlarını kontrol eder.
"""

from django.core.management.base import BaseCommand
import logging
import time
from trendyol_app.models import TrendyolProduct
from trendyol_app.services import check_product_batch_status

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Tüm bekleyen Trendyol ürünlerinin batch durumlarını kontrol eder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Bir seferde kontrol edilecek max ürün sayısı (varsayılan: 10)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='İki istek arasındaki bekleme süresi, saniye cinsinden (varsayılan: 0.5)'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        delay = options['delay']
        
        self.stdout.write(self.style.WARNING(f'Bekleyen ürünler kontrol ediliyor (batch boyutu: {batch_size}, gecikme: {delay} saniye)...'))
        
        try:
            pending_products = TrendyolProduct.objects.filter(
                batch_id__isnull=False,
                batch_status__in=['pending', 'processing']
            )
            
            count = pending_products.count()
            if count == 0:
                self.stdout.write(self.style.SUCCESS('Bekleyen ürün bulunamadı.'))
                return
                
            self.stdout.write(self.style.WARNING(f'Toplam {count} bekleyen ürün bulundu.'))
            
            updated = 0
            for i, product in enumerate(pending_products[:batch_size]):
                if product.needs_status_check():
                    old_status = product.batch_status
                    check_product_batch_status(product)
                    new_status = product.batch_status
                    
                    if old_status != new_status:
                        self.stdout.write(self.style.SUCCESS(
                            f'Ürün {product.id} ({product.title}) durumu güncellendi: {old_status} -> {new_status}'
                        ))
                    else:
                        self.stdout.write(
                            f'Ürün {product.id} ({product.title}) durumu aynı kaldı: {old_status}'
                        )
                    
                    updated += 1
                    
                    # API rate limiting'i önlemek için bekleme
                    if i < batch_size - 1 and delay > 0:
                        time.sleep(delay)
            
            remaining = count - batch_size if count > batch_size else 0
            self.stdout.write(self.style.SUCCESS(
                f'{updated} ürünün durumu kontrol edildi. {remaining} ürün kaldı.'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ürün durumu kontrol edilirken hata: {str(e)}'))
            logger.error(f"Ürün durumu kontrol edilirken hata: {str(e)}")