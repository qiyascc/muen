"""
Django yönetim komutu: Örnek Trendyol API yapılandırması oluşturma

Bu komut, test amaçlı örnek bir Trendyol API yapılandırması oluşturur.
"""

from django.core.management.base import BaseCommand
import logging
from django.conf import settings
from trendyol_app.models import TrendyolAPIConfig

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test amaçlı örnek bir Trendyol API yapılandırması oluşturur'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Zaten bir aktif yapılandırma varsa üzerine yaz'
        )
        parser.add_argument(
            '--seller-id',
            type=str,
            default=None,
            help='Satıcı ID (environment değerinden alınacak veya varsayılan kullanılacak)'
        )
        parser.add_argument(
            '--api-key',
            type=str,
            default=None,
            help='API Key (environment değerinden alınacak veya varsayılan kullanılacak)'
        )
        parser.add_argument(
            '--base-url',
            type=str,
            default='https://apigw.trendyol.com/integration/',
            help='API Base URL'
        )

    def handle(self, *args, **options):
        force = options['force']
        seller_id = options['seller_id'] or settings.TRENDYOL_SUPPLIER_ID
        api_key = options['api_key'] or settings.TRENDYOL_API_KEY
        base_url = options['base_url']
        
        # Mevcut yapılandırmaları kontrol et
        existing_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        
        if existing_config and not force:
            self.stdout.write(self.style.WARNING(
                f'Halihazırda aktif bir yapılandırma mevcut: {existing_config.seller_id}. '
                f'Üzerine yazmak için --force parametresini kullanın.'
            ))
            return
            
        if existing_config and force:
            self.stdout.write(self.style.WARNING(
                f'Mevcut yapılandırma üzerine yazılıyor: {existing_config.seller_id}'
            ))
            existing_config.delete()
        
        # Yeni yapılandırma oluştur
        config = TrendyolAPIConfig(
            seller_id=seller_id,
            api_key=api_key,
            base_url=base_url,
            is_active=True
        )
        config.save()
        
        self.stdout.write(self.style.SUCCESS(
            f'Trendyol API yapılandırması başarıyla oluşturuldu:'
            f'\n  Satıcı ID: {config.seller_id}'
            f'\n  API Key: {"*" * 8 + config.api_key[-4:] if len(config.api_key) > 8 else "*" * 4}'
            f'\n  Base URL: {config.base_url}'
        ))