"""
Trendyol toplu işlem durumlarını kontrol eden komut.

Bu komut, Trendyol'a gönderilen ve işlemde olan ürünlerin batch durumlarını kontrol eder
ve veritabanındaki durumlarını günceller.

python manage.py check_batch_status
"""

import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from trendyol.models import TrendyolProduct
from trendyol.advanced_api_client import create_product_manager

logger = logging.getLogger('trendyol.batch')

class Command(BaseCommand):
    help = 'Bekleyen Trendyol toplu işlemlerin durumlarını kontrol eder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-id',
            type=str,
            help='Kontrol edilecek belirli batch ID'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Tüm ürünleri kontrol et (tamamlanmış olanlar dahil)'
        )
        parser.add_argument(
            '--max-items',
            type=int,
            default=50,
            help='İşlenecek maksimum ürün sayısı'
        )

    def handle(self, *args, **options):
        batch_id = options.get('batch_id')
        check_all = options.get('all', False)
        max_items = options.get('max_items', 50)

        # Ürün yöneticisi oluştur
        product_manager = create_product_manager()
        if not product_manager:
            self.stdout.write(self.style.ERROR("Ürün yöneticisi oluşturulamadı. API yapılandırmasını kontrol edin."))
            return

        # Belirli bir batch ID kontrol ediliyor mu?
        if batch_id:
            self.stdout.write(f"Batch ID kontrolü: {batch_id}")
            status = product_manager.check_batch_status(batch_id)
            self.stdout.write(str(status))
            
            # İlgili ürünleri güncelle
            products = TrendyolProduct.objects.filter(batch_id=batch_id)
            if products:
                for product in products:
                    self._update_product_status(product, status)
                self.stdout.write(self.style.SUCCESS(f"{products.count()} ürün güncellendi"))
            else:
                self.stdout.write(self.style.WARNING(f"Batch ID {batch_id} ile ilişkili ürün bulunamadı"))
            
            return

        # Bekleyen toplu işlemleri kontrol et
        query = Q(batch_id__isnull=False) & Q(batch_id__ne='')
        
        if not check_all:
            # Sadece bekleyen veya işlemdeki işlemleri kontrol et
            query &= (Q(batch_status='pending') | Q(batch_status='processing'))
        
        products = TrendyolProduct.objects.filter(query).order_by('-last_check_time')[:max_items]
        
        if not products:
            self.stdout.write(self.style.WARNING("Kontrol edilecek bekleyen toplu işlem bulunamadı."))
            return
        
        self.stdout.write(f"{products.count()} ürün kontrol edilecek")
        
        # Her bir ürünün batch durumunu kontrol et
        batch_ids = set()
        for product in products:
            if not product.batch_id or product.batch_id in batch_ids:
                continue
                
            batch_ids.add(product.batch_id)
            self._check_batch(product, product_manager)
            
            # API hız sınırlaması için kısa bir bekleme
            time.sleep(0.5)
            
        self.stdout.write(self.style.SUCCESS(f"{len(batch_ids)} toplu işlem kontrol edildi"))

    def _check_batch(self, product, product_manager):
        """Bir ürünün batch durumunu kontrol et"""
        try:
            self.stdout.write(f"Kontrol ediliyor: {product.title} (Batch ID: {product.batch_id})")
            
            # Batch durumunu kontrol et
            status = product_manager.check_batch_status(product.batch_id)
            
            # Ürünü güncelle
            self._update_product_status(product, status)
            
            # Sonucu yazdır
            self.stdout.write(self.style.SUCCESS(f"Durum güncellendi: {product.batch_status}"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Batch durumu kontrol edilirken hata: {str(e)}"))
            
            # Hata durumunda bile son kontrol zamanını güncelle
            product.last_check_time = timezone.now()
            product.save()

    def _update_product_status(self, product, status):
        """Duruma göre ürünü güncelle"""
        try:
            if not status:
                product.status_message = "API'den durum alınamadı"
                product.batch_status = 'failed'
            else:
                # Batch durumunu al
                batch_status = status.get('status')
                
                if batch_status == 'COMPLETED':
                    product.batch_status = 'completed'
                    product.status_message = "Ürün başarıyla oluşturuldu"
                elif batch_status == 'FAILED':
                    product.batch_status = 'failed'
                    
                    # Hata mesajlarını al
                    failures = status.get('items', [{}])[0].get('failures', [])
                    if failures:
                        error_messages = [f"{f.get('errorCode', '')}: {f.get('errorMessage', '')}" for f in failures]
                        product.status_message = "; ".join(error_messages)
                    else:
                        product.status_message = "Bilinmeyen hata"
                else:
                    product.batch_status = 'processing'
                    product.status_message = f"İşlemde: {batch_status}"
            
            # Son kontrol zamanını güncelle
            product.last_check_time = timezone.now()
            product.save()
            
        except Exception as e:
            logger.error(f"Ürün durumu güncellenirken hata: {str(e)}")
            self.stdout.write(self.style.ERROR(f"Güncelleme hatası: {str(e)}"))
            
            # Hata durumunda bile son kontrol zamanını güncelle
            product.last_check_time = timezone.now()
            product.save()