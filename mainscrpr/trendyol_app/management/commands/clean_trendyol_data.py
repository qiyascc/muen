"""
Django yönetim komutu: Trendyol verilerini temizleme

Bu komut, Trendyol ürünlerini ve geçici verileri veritabanından temizler.
Tüm ürünleri silme, sadece hatalı ürünleri silme, API önbelleğini temizleme vb. 
işlemleri içerir.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import logging
from trendyol_app.models import TrendyolProduct

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Trendyol verilerini veritabanından temizler'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all', 
            action='store_true',
            help='Tüm Trendyol ürünlerini sil'
        )
        parser.add_argument(
            '--failed', 
            action='store_true',
            help='Sadece hatalı ürünleri sil'
        )
        parser.add_argument(
            '--pending',
            action='store_true',
            help='Bekleyen ürünleri sil (batch_id mevcut, status_code yok)'
        )
        parser.add_argument(
            '--success', 
            action='store_true',
            help='Başarılı ürünleri sil (status = success)'
        )
        parser.add_argument(
            '--status-reset',
            action='store_true',
            help='Ürünlerin durum bilgilerini sıfırla (batch_id ve status_message)'
        )

    def handle(self, *args, **options):
        all_products = options['all']
        failed_products = options['failed']
        pending_products = options['pending']
        success_products = options['success']
        status_reset = options['status_reset']
        
        # Hiçbir seçenek seçilmezse kullanıcıya bilgi ver
        if not any([all_products, failed_products, pending_products, success_products, status_reset]):
            self.stdout.write(self.style.WARNING(
                "Hiçbir seçenek belirtilmedi. Lütfen bir temizleme seçeneği belirtin:"
                "\n  --all: Tüm Trendyol ürünlerini sil"
                "\n  --failed: Sadece hatalı ürünleri sil"
                "\n  --pending: Bekleyen ürünleri sil"
                "\n  --success: Başarılı ürünleri sil"
                "\n  --status-reset: Ürünlerin durum bilgilerini sıfırla"
            ))
            return
            
        try:
            with transaction.atomic():
                if all_products:
                    count = TrendyolProduct.objects.count()
                    TrendyolProduct.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS(f'Tüm Trendyol ürünleri silindi ({count} ürün)'))
                    
                elif failed_products:
                    failed_query = TrendyolProduct.objects.filter(
                        status_message__isnull=False
                    ).exclude(batch_status='success')
                    count = failed_query.count()
                    failed_query.delete()
                    self.stdout.write(self.style.SUCCESS(f'Hatalı Trendyol ürünleri silindi ({count} ürün)'))
                    
                elif pending_products:
                    pending_query = TrendyolProduct.objects.filter(
                        batch_id__isnull=False,
                        status_code__isnull=True
                    )
                    count = pending_query.count()
                    pending_query.delete()
                    self.stdout.write(self.style.SUCCESS(f'Bekleyen Trendyol ürünleri silindi ({count} ürün)'))
                    
                elif success_products:
                    success_query = TrendyolProduct.objects.filter(batch_status='success')
                    count = success_query.count()
                    success_query.delete()
                    self.stdout.write(self.style.SUCCESS(f'Başarılı Trendyol ürünleri silindi ({count} ürün)'))
                    
                elif status_reset:
                    count = TrendyolProduct.objects.update(
                        batch_id=None,
                        status_message=None,
                        status_code=None,
                        batch_status='pending',
                        trendyol_id=None,
                        approved=False
                    )
                    self.stdout.write(self.style.SUCCESS(f'Trendyol ürünlerinin durum bilgileri sıfırlandı ({count} ürün)'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Veri temizleme sırasında hata: {str(e)}'))
            logger.error(f"Veri temizleme sırasında hata: {str(e)}")