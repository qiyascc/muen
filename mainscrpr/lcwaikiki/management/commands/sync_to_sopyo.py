"""
LC Waikiki ürünlerini Sopyo platformuna senkronize eden yönetim komutu.

Bu komut, LC Waikiki ürünlerini Sopyo platformuna gönderir.
Tüm ürünleri veya belirli ürünleri göndermeyi destekler.

Kullanım:
    python manage.py sync_to_sopyo [--limit 10] [--product_ids 1,2,3]
"""

import logging
from django.core.management.base import BaseCommand
from lcwaikiki.sopyo_api import send_multiple_products_to_sopyo
from lcwaikiki.product_models import Product

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'LC Waikiki ürünlerini Sopyo platformuna gönderir'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Gönderilecek maksimum ürün sayısı'
        )
        parser.add_argument(
            '--product_ids',
            type=str,
            help='Gönderilecek ürün ID\'leri, virgülle ayrılmış (örn: 1,2,3)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        product_ids = options.get('product_ids')
        
        if product_ids:
            try:
                product_ids = [int(id.strip()) for id in product_ids.split(',')]
                self.stdout.write(self.style.SUCCESS(
                    f"Belirtilen {len(product_ids)} ürün Sopyo'ya aktarılacak (limit: {limit})"
                ))
            except ValueError:
                self.stderr.write(self.style.ERROR(
                    'Geçersiz ürün ID formatı. Virgülle ayrılmış sayılar kullanın (örn: 1,2,3)'
                ))
                return
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Stokta olan en yeni {limit} ürün Sopyo'ya aktarılacak"
            ))
            
            # Stokta olan ürün sayısını kontrol et
            in_stock_count = Product.objects.filter(in_stock=True).count()
            if in_stock_count == 0:
                self.stderr.write(self.style.WARNING(
                    'Stokta ürün bulunamadı.'
                ))
                return
            elif in_stock_count < limit:
                self.stdout.write(self.style.WARNING(
                    f'Stokta sadece {in_stock_count} ürün bulunuyor. Tümü aktarılacak.'
                ))
                limit = in_stock_count
        
        # Ürünleri Sopyo'ya gönder
        self.stdout.write(self.style.SUCCESS("Sopyo API'ye bağlanılıyor..."))
        result = send_multiple_products_to_sopyo(product_ids, limit)
        
        if result.get('status', False):
            self.stdout.write(self.style.SUCCESS(result.get('message', 'Ürünler başarıyla gönderildi')))
            
            # Başarılı ve başarısız ürünleri listele
            results = result.get('results', {})
            if results:
                self.stdout.write(self.style.SUCCESS(
                    f"Toplam: {results.get('total', 0)}, "
                    f"Başarılı: {results.get('success', 0)}, "
                    f"Başarısız: {results.get('failed', 0)}"
                ))
                
                # Detaylı başarısız ürünleri göster
                for item in results.get('details', []):
                    if not item.get('result', {}).get('status', False):
                        self.stdout.write(self.style.ERROR(
                            f"Ürün ID: {item.get('product_id')}, "
                            f"Başlık: {item.get('title')}, "
                            f"Hata: {item.get('result', {}).get('message', 'Bilinmeyen hata')}"
                        ))
        else:
            self.stderr.write(self.style.ERROR(
                f"Sopyo API hatası: {result.get('message', 'Bilinmeyen hata')}"
            ))