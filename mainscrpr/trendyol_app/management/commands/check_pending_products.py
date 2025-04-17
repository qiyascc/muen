"""
Django yönetim komutu: Bekleyen ürünleri kontrol etme

Bu komut, tüm bekleyen Trendyol ürünlerinin batch durumlarını kontrol eder.
"""

import logging
from django.core.management.base import BaseCommand
from trendyol_app.models import TrendyolProduct, TrendyolAPIConfig
from trendyol_app.services import TrendyolAPIClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Tüm bekleyen Trendyol ürünlerinin batch durumlarını kontrol eder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Bir seferde kontrol edilecek maksimum ürün sayısı (varsayılan: 10)'
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Başarısız ürünleri yeniden deneme'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Detaylı çıktı göster'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        retry_failed = options['retry_failed']
        verbose = options['verbose']
        
        self.stdout.write(self.style.WARNING(
            f'Bekleyen Trendyol ürünlerinin batch durumları kontrol ediliyor '
            f'(batch boyutu: {batch_size})...'
        ))
        
        try:
            # API yapılandırmasını al
            api_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
            if not api_config:
                self.stdout.write(self.style.ERROR('Aktif bir Trendyol API yapılandırması bulunamadı.'))
                return
                
            # API istemcisi oluştur
            api_client = TrendyolAPIClient(api_config)
            
            # Bekleyen ürünleri filtrele
            query = TrendyolProduct.objects.filter(
                batch_id__isnull=False,
                status_code__isnull=True
            )
            
            if retry_failed:
                # Başarısız ürünleri de dahil et
                query = TrendyolProduct.objects.filter(
                    batch_id__isnull=False
                ).exclude(status='success')
                
            count = query.count()
            if count == 0:
                self.stdout.write(self.style.SUCCESS('Bekleyen ürün bulunamadı.'))
                return
                
            self.stdout.write(self.style.WARNING(f'Toplam {count} bekleyen ürün kontrol edilecek.'))
            
            # Batch işleme
            products_to_check = query[:batch_size]
            updated_count = 0
            success_count = 0
            
            for i, product in enumerate(products_to_check):
                try:
                    if verbose:
                        self.stdout.write(f'({i+1}/{len(products_to_check)}) Kontrol ediliyor: {product.title} (Batch ID: {product.batch_id})')
                    
                    # Batch durumunu kontrol et
                    result = api_client.check_batch_status(product.batch_id)
                    
                    if result:
                        product.status = result.get('status', 'error')
                        product.status_code = result.get('status_code')
                        product.status_message = result.get('message', '')
                        
                        if result.get('status') == 'success':
                            success_count += 1
                            self.stdout.write(self.style.SUCCESS(
                                f'({i+1}/{len(products_to_check)}) Ürün başarılı: {product.title}'
                            ))
                        else:
                            self.stdout.write(self.style.WARNING(
                                f'({i+1}/{len(products_to_check)}) Ürün durumu: {product.status}, Mesaj: {product.status_message}'
                            ))
                            
                        product.save()
                        updated_count += 1
                    else:
                        self.stdout.write(self.style.ERROR(
                            f'({i+1}/{len(products_to_check)}) Batch durumu alınamadı: {product.title}'
                        ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'({i+1}/{len(products_to_check)}) Kontrol hatası: {str(e)}'
                    ))
                    logger.error(f"Ürün kontrolü sırasında hata (ID: {product.id}): {str(e)}")
            
            self.stdout.write(self.style.SUCCESS(
                f'İşlem tamamlandı: {updated_count} ürün kontrol edildi, {success_count} başarılı. '
                f'{count - batch_size if count > batch_size else 0} ürün kaldı.'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ürün kontrolü sırasında hata: {str(e)}'))
            logger.error(f"Ürün kontrolü sırasında hata: {str(e)}")