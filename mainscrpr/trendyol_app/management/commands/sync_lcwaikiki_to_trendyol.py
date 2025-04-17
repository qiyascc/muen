"""
Django yönetim komutu: LCWaikiki'den Trendyol'a ürün aktarımı

Bu komut, LCWaikiki veritabanından ürünleri alıp Trendyol'a gönderir.
"""

from django.core.management.base import BaseCommand
import logging
import time
import random
from django.db import transaction
from lcwaikiki.product_models import Product
from trendyol_app.models import TrendyolProduct

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'LCWaikiki ürünlerini Trendyol\'a aktarır'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Bir seferde işlenecek max ürün sayısı (varsayılan: 10)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='İki ürün işleme arasındaki bekleme süresi, saniye cinsinden (varsayılan: 0.5)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Zaten Trendyol\'a aktarılmış ürünleri de yeniden aktar'
        )
        parser.add_argument(
            '--min-stock',
            type=int,
            default=1,
            help='Minimum stok miktarı (varsayılan: 1)'
        )
        parser.add_argument(
            '--filter-category',
            type=str,
            default='',
            help='Belirli bir kategori içeren ürünleri filtrele (opsiyonel)'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        delay = options['delay']
        force = options['force']
        min_stock = options['min_stock']
        filter_category = options['filter_category']
        
        self.stdout.write(self.style.WARNING(
            f'LCWaikiki\'den Trendyol\'a ürün aktarımı başlıyor '
            f'(batch boyutu: {batch_size}, gecikme: {delay} saniye)...'
        ))
        
        try:
            # Aktarılacak ürünleri filtrele
            query = Product.objects.filter(in_stock=True)
            
            if filter_category:
                query = query.filter(category__icontains=filter_category)
                
            if not force:
                # Daha önce aktarılmış ürünleri hariç tut (product_code kullanarak)
                existing_products = TrendyolProduct.objects.values_list('product_main_id', flat=True)
                query = query.exclude(product_code__in=existing_products)
                
            count = query.count()
            if count == 0:
                self.stdout.write(self.style.SUCCESS('Aktarılacak ürün bulunamadı.'))
                return
                
            self.stdout.write(self.style.WARNING(f'Toplam {count} ürün aktarılacak.'))
            
            # Batch işleme
            products_to_process = query[:batch_size]
            created_count = 0
            
            for i, lcw_product in enumerate(products_to_process):
                try:
                    with transaction.atomic():
                        # LCWaikiki'den Trendyol'a ürün dönüşümü
                        trendyol_product = self._lcwaikiki_to_trendyol(lcw_product)
                        trendyol_product.save()
                        
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'({i+1}/{len(products_to_process)}) Ürün başarıyla aktarıldı: {trendyol_product.title}'
                        ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'({i+1}/{len(products_to_process)}) Ürün aktarım hatası: {str(e)}'
                    ))
                    logger.error(f"Ürün aktarım hatası (ID: {lcw_product.id}): {str(e)}")
                
                # API rate limiting'i önlemek için bekleme
                if i < len(products_to_process) - 1 and delay > 0:
                    time.sleep(delay)
            
            remaining = count - batch_size if count > batch_size else 0
            self.stdout.write(self.style.SUCCESS(
                f'İşlem tamamlandı: {created_count} ürün aktarıldı. {remaining} ürün kaldı.'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ürün aktarımı sırasında hata: {str(e)}'))
            logger.error(f"Ürün aktarımı sırasında hata: {str(e)}")
    
    def _lcwaikiki_to_trendyol(self, lcw_product):
        """LCWaikiki ürününü Trendyol ürününe dönüştürür"""
        # Temel bilgileri al
        # Rastgele bir barkod oluştur
        barcode = f"LCW{str(lcw_product.id).zfill(8)}{random.randint(1000, 9999)}"
            
        # Ana ürün ID'sini al
        product_main_id = lcw_product.product_code
        if not product_main_id:
            # Eksikse rastgele bir ID oluştur
            product_main_id = f"LCW-{str(lcw_product.id).zfill(8)}"
        
        # Başlık temizleme
        title = lcw_product.title
        if title:
            # Fazla boşlukları temizle
            import re
            title = re.sub(r'\s+', ' ', title).strip()
            # 150 karakterle sınırla
            title = title[:150]
        
        # Marka adını al (LC Waikiki)
        brand_name = "LC Waikiki"
        
        # Stok hesaplama
        total_stock = lcw_product.get_total_stock()
        if total_stock <= 0 and lcw_product.in_stock:
            total_stock = 10  # Varsayılan stok miktarı
        
        # İlk görseli al
        image_url = ""
        if lcw_product.images and isinstance(lcw_product.images, list) and len(lcw_product.images) > 0:
            image_url = lcw_product.images[0]
        
        # Trendyol ürününü oluştur
        trendyol_product = TrendyolProduct(
            barcode=barcode,
            title=title,
            product_main_id=product_main_id,
            brand_name=brand_name,
            category_name=lcw_product.category or "Giyim",
            quantity=total_stock,
            stock_code=lcw_product.product_code or str(lcw_product.id),
            price=lcw_product.price,
            sale_price=lcw_product.price,
            description=lcw_product.description or f"{title} - LC Waikiki",
            image_url=image_url,
            vat_rate=10,  # Varsayılan KDV oranı
            currency_type="TRY"
        )
        
        return trendyol_product