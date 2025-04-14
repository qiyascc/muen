"""
Gelişmiş Trendyol API istemcisi ile ürünleri senkronize eden komut.

Bu komut, ürünleri LC Waikiki'den Trendyol'a aktarır ve kategorileri,
öznitelikleri gerçek zamanlı olarak Trendyol API'sinden çeker.

python manage.py sync_with_new_api
"""

import time
import json
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from lcwaikiki.product_models import Product
from trendyol.models import TrendyolProduct
from trendyol.advanced_api_client import create_product_manager

logger = logging.getLogger('trendyol.sync')

class Command(BaseCommand):
    help = 'LCWaikiki ürünlerini gelişmiş API istemcisi kullanarak Trendyol ile senkronize eder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-items',
            type=int,
            default=50,
            help='İşlenecek maksimum ürün sayısı'
        )
        parser.add_argument(
            '--test-mode',
            action='store_true',
            help='Test modu (veritabanı güncellemeden çalıştırır)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Başarısız ürünleri zorla tekrar gönder'
        )

    def handle(self, *args, **options):
        max_items = options['max_items']
        test_mode = options['test_mode']
        force = options['force']

        self.stdout.write(self.style.SUCCESS(f"LCWaikiki → Trendyol senkronizasyonu başlatılıyor (gelişmiş API ile)"))
        self.stdout.write(f"Maksimum {max_items} ürün işlenecek, Test modu: {test_mode}, Zorlama: {force}")

        # Ürün yöneticisi oluştur
        product_manager = create_product_manager()
        if not product_manager:
            self.stdout.write(self.style.ERROR("Ürün yöneticisi oluşturulamadı. API yapılandırmasını kontrol edin."))
            return

        # Senkronize edilmemiş LCWaikiki ürünlerini al
        lcw_products = self._get_pending_lcw_products(max_items, force)
        
        if not lcw_products:
            self.stdout.write(self.style.WARNING("Senkronize edilecek yeni LCWaikiki ürünü bulunamadı."))
            return

        self.stdout.write(f"{lcw_products.count()} LCWaikiki ürünü senkronize edilecek.")

        # Her bir ürünü işle
        for lcw_product in lcw_products:
            self._process_product(lcw_product, product_manager, test_mode)

        self.stdout.write(self.style.SUCCESS("Senkronizasyon tamamlandı!"))

    def _get_pending_lcw_products(self, max_items, force):
        """Senkronize edilecek bekleyen LCWaikiki ürünlerini al"""
        # Trendyol'da zaten bulunan ürünlerin barkodlarını al
        existing_barcodes = set(TrendyolProduct.objects.values_list('barcode', flat=True))
        
        # Temel sorgu: Aktif ve görüntüsü olan ürünler
        query = Q(is_active=True) & ~Q(image_url='')
        
        # Force modunda değilse, zaten Trendyol'da olan ürünleri hariç tut
        if not force:
            query &= ~Q(barcode__in=existing_barcodes)
        
        # LCWaikiki ürünlerini al
        lcw_products = Product.objects.filter(query)[:max_items]
        
        return lcw_products

    def _process_product(self, lcw_product, product_manager, test_mode):
        """Bir LCWaikiki ürününü işle ve Trendyol'a gönder"""
        try:
            self.stdout.write(f"İşleniyor: {lcw_product.title} (Barkod: {lcw_product.barcode})")
            
            # Trendyol ürünü zaten var mı diye kontrol et
            trendyol_product = TrendyolProduct.objects.filter(barcode=lcw_product.barcode).first()
            
            if not trendyol_product:
                # Yeni Trendyol ürünü oluştur
                trendyol_product = self._create_trendyol_product(lcw_product)
                
                if test_mode:
                    self.stdout.write(self.style.WARNING("TEST MODU: Veritabanına kaydedilmedi"))
                else:
                    trendyol_product.save()
                    self.stdout.write(self.style.SUCCESS(f"Trendyol ürünü oluşturuldu: {trendyol_product.title}"))
            else:
                self.stdout.write(f"Mevcut Trendyol ürünü güncelleniyor: {trendyol_product.title}")
                self._update_trendyol_product(trendyol_product, lcw_product)
                
                if test_mode:
                    self.stdout.write(self.style.WARNING("TEST MODU: Veritabanına kaydedilmedi"))
                else:
                    trendyol_product.save()
                    self.stdout.write(self.style.SUCCESS(f"Trendyol ürünü güncellendi: {trendyol_product.title}"))
            
            # API'ye gönder
            if not test_mode:
                batch_id = product_manager.create_product(trendyol_product)
                self.stdout.write(self.style.SUCCESS(f"Trendyol'a gönderildi. Batch ID: {batch_id}"))
                time.sleep(0.5)  # API hız sınırlaması için kısa bir bekleme
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ürün işlenirken hata: {str(e)}"))
            
            if trendyol_product and not test_mode:
                trendyol_product.batch_status = 'failed'
                trendyol_product.status_message = f"Hata: {str(e)}"
                trendyol_product.save()

    def _create_trendyol_product(self, lcw_product):
        """LCWaikiki ürününden yeni bir Trendyol ürünü oluştur"""
        trendyol_product = TrendyolProduct(
            # Temel bilgiler
            title=lcw_product.title[:255],
            description=lcw_product.description or lcw_product.title,
            barcode=lcw_product.barcode,
            product_main_id=lcw_product.product_code,
            stock_code=lcw_product.stock_code or lcw_product.barcode,
            
            # Marka ve kategori
            brand_name="LC Waikiki",
            brand_id=7651,  # LC Waikiki Trendyol marka ID'si
            category_name=lcw_product.category_name,
            
            # Fiyat ve stok
            price=lcw_product.price,
            quantity=lcw_product.get_total_stock(),
            vat_rate=18,  # Varsayılan KDV oranı
            currency_type='TRY',
            
            # Görüntüler
            image_url=lcw_product.image_url,
            additional_images=json.loads(lcw_product.additional_images) if lcw_product.additional_images else [],
            
            # LCWaikiki ilişkisi
            lcwaikiki_product=lcw_product,
            
            # Varsayılan durumlar
            batch_status='pending',
            status_message='Yeni ürün oluşturuldu, gönderilmeyi bekliyor',
            attributes={"348": 4294}  # Varsayılan siyah renk (ID: 348, Değer: 4294)
        )
        
        return trendyol_product

    def _update_trendyol_product(self, trendyol_product, lcw_product):
        """Mevcut Trendyol ürününü LCWaikiki ürünü ile güncelle"""
        # Ürün güncelleme mantığı burada
        trendyol_product.title = lcw_product.title[:255]
        trendyol_product.description = lcw_product.description or lcw_product.title
        trendyol_product.price = lcw_product.price
        trendyol_product.quantity = lcw_product.get_total_stock()
        trendyol_product.image_url = lcw_product.image_url
        
        if lcw_product.additional_images:
            trendyol_product.additional_images = json.loads(lcw_product.additional_images)
        
        # Durum sıfırla
        trendyol_product.batch_status = 'pending'
        trendyol_product.status_message = 'Ürün güncellendi, gönderilmeyi bekliyor'
        
        # LC Waikiki ilişkisini kur
        trendyol_product.lcwaikiki_product = lcw_product
        
        return trendyol_product