"""
Gelişmiş Trendyol API istemcisi test komutu.

Bu komut, yeni gelişmiş API istemcisini test eder ve bir ürün kategorisinin
özniteliklerini gerçek zamanlı olarak API'den çeker.

python manage.py test_new_api
"""

import logging
from django.core.management.base import BaseCommand

from trendyol.models import TrendyolAPIConfig
from trendyol.advanced_api_client import APIConfig, TrendyolAPI, TrendyolCategoryFinder

logger = logging.getLogger('trendyol.test')

class Command(BaseCommand):
    help = 'Gelişmiş Trendyol API istemcisini test eder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category-id',
            type=int,
            default=2356,  # Varsayılan olarak erkek giyim kategorisi
            help='Test edilecek kategori ID'
        )

    def handle(self, *args, **options):
        category_id = options['category_id']
        
        self.stdout.write(self.style.SUCCESS(f"Gelişmiş Trendyol API istemcisi test ediliyor"))
        self.stdout.write(f"Kategori ID: {category_id}")
        
        # API istemcisi oluştur
        api_client = self._create_api_client()
        if not api_client:
            self.stdout.write(self.style.ERROR("API istemcisi oluşturulamadı. API yapılandırmasını kontrol edin."))
            return
            
        try:
            # Kategori bilgilerini getir
            category_finder = TrendyolCategoryFinder(api_client)
            categories = category_finder.category_cache
            
            self.stdout.write(self.style.SUCCESS(f"Kategoriler başarıyla alındı: {len(categories)} kategori"))
            
            # İlk 5 kategori göster
            self.stdout.write("İlk 5 kategori:")
            for i, cat in enumerate(categories[:5]):
                self.stdout.write(f"{i+1}. {cat['name']} (ID: {cat['id']})")
                
            # Belirli bir kategorinin özniteliklerini getir
            self.stdout.write(f"\n{category_id} ID'li kategori için öznitelikler alınıyor...")
            attributes = category_finder.get_category_attributes(category_id)
            
            # Öznitelikleri göster
            if not attributes:
                self.stdout.write(self.style.WARNING("Öznitelik bulunamadı."))
                return
                
            self.stdout.write(self.style.SUCCESS(f"Öznitelikler başarıyla alındı."))
            
            category_attrs = attributes.get('categoryAttributes', [])
            self.stdout.write(f"\nKategori öznitelikleri ({len(category_attrs)}):")
            
            for i, attr in enumerate(category_attrs[:10]):  # İlk 10 öznitelik göster
                attr_id = attr['attribute']['id']
                attr_name = attr['attribute']['name']
                required = attr['required']
                allowed_values = len(attr.get('attributeValues', []))
                
                self.stdout.write(f"{i+1}. ID: {attr_id}, Ad: {attr_name}, Zorunlu: {required}, Değer sayısı: {allowed_values}")
                
                # Renk özniteliği detaylarını göster
                if attr_id == 348:  # Renk özniteliği
                    self.stdout.write(self.style.SUCCESS(f"\nRenk özniteliği bulundu (ID: 348)"))
                    self.stdout.write("Mevcut renkler:")
                    
                    for j, color in enumerate(attr.get('attributeValues', [])[:5]):  # İlk 5 renk değeri göster
                        self.stdout.write(f"  {j+1}. ID: {color['id']}, Değer: {color['name']}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Test sırasında hata oluştu: {str(e)}"))
    
    def _create_api_client(self):
        """API istemcisi oluştur"""
        # Aktif API yapılandırmasını al
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            self.stdout.write(self.style.ERROR("Aktif Trendyol API yapılandırması bulunamadı"))
            return None
        
        self.stdout.write(f"API Yapılandırması: {config.name}, Base URL: {config.base_url}")
        
        # API yapılandırması oluştur
        api_config = APIConfig(
            api_key=config.api_key,
            api_secret=config.api_secret,
            seller_id=config.seller_id,
            base_url=config.base_url
        )
        
        # API istemcisi oluştur ve döndür
        return TrendyolAPI(api_config)