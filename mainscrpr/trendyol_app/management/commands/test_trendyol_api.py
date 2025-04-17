"""
Django yönetim komutu: Trendyol API'sini test etme

Bu komut, Trendyol API bağlantısını, kimlik doğrulamasını ve temel API işlevselliğini test eder.
"""

from django.core.management.base import BaseCommand
import logging
import json
from trendyol_app.models import TrendyolAPIConfig
from trendyol_app.services import TrendyolAPI, TrendyolCategoryFinder, get_active_api_config

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Trendyol API bağlantısını ve temel işlevselliği test eder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Detaylı log ve yanıtları göster'
        )
        parser.add_argument(
            '--category-id',
            type=int,
            default=None,
            help='Belirli bir kategori ID için öznitelikleri test et'
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        category_id = options['category_id']
        
        self.stdout.write(self.style.WARNING('Trendyol API testi başlıyor...'))
        
        try:
            # API yapılandırmasını kontrol et
            config = get_active_api_config()
            if not config:
                self.stdout.write(self.style.ERROR('Aktif Trendyol API yapılandırması bulunamadı!'))
                self.stdout.write('Lütfen önce bir yapılandırma oluşturun: /admin/trendyol_app/trendyolapiconfig/add/')
                return
                
            self.stdout.write(self.style.SUCCESS(f'API yapılandırması bulundu: {config.seller_id}'))
            
            # API istemcisini başlat
            api = TrendyolAPI(config)
            self.stdout.write(self.style.SUCCESS('API istemcisi başarıyla oluşturuldu'))
            
            # Temel bağlantıyı test et (kategorileri getir)
            self.stdout.write('Kategorileri getirme testi yapılıyor...')
            try:
                categories_data = api.get("product/product-categories")
                categories_count = len(categories_data.get('categories', []))
                self.stdout.write(self.style.SUCCESS(f'Kategoriler başarıyla alındı ({categories_count} kategori)'))
                
                if verbose:
                    self.stdout.write(json.dumps(categories_data, indent=2)[:1000] + '...')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Kategoriler alınırken hata: {str(e)}'))
                return
            
            # Belirli bir kategori için öznitelikleri test et
            if category_id:
                self.stdout.write(f'Kategori ID {category_id} için öznitelikler getiriliyor...')
                try:
                    attributes_data = api.get(f"product/product-categories/{category_id}/attributes")
                    attr_count = len(attributes_data.get('categoryAttributes', []))
                    self.stdout.write(self.style.SUCCESS(f'Öznitelikler başarıyla alındı ({attr_count} öznitelik)'))
                    
                    if verbose:
                        self.stdout.write(json.dumps(attributes_data, indent=2)[:1000] + '...')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Öznitelikler alınırken hata: {str(e)}'))
            
            # TrendyolCategoryFinder sınıfını test et
            self.stdout.write('Kategori bulucu sınıfı test ediliyor...')
            try:
                finder = TrendyolCategoryFinder(api)
                cats = finder.category_cache
                self.stdout.write(self.style.SUCCESS(f'Kategori önbelleği başarıyla oluşturuldu ({len(cats)} kategori)'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Kategori bulucu test edilirken hata: {str(e)}'))
                
            self.stdout.write(self.style.SUCCESS('\nTüm testler tamamlandı! API bağlantısı çalışıyor.'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'API testi sırasında beklenmeyen hata: {str(e)}'))
            logger.error(f"API testi sırasında hata: {str(e)}")