"""
Django management command to fetch and store data from Trendyol API.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from trendyol.trendyol_client import TrendyolClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fetch and store data from Trendyol API'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-type', type=str, choices=['brands', 'categories', 'all'],
                            default='all', help='Type of data to fetch')
        parser.add_argument('--force', action='store_true',
                            help='Force fetch even if data already exists')
    
    def handle(self, *args, **options):
        data_type = options['data_type']
        force = options['force']
        
        self.stdout.write(self.style.NOTICE(f"Starting data fetch at {timezone.now()}"))
        
        # Initialize Trendyol client
        client = TrendyolClient()
        
        if not client.api_client:
            self.stdout.write(self.style.ERROR("Failed to initialize Trendyol client"))
            return
        
        # Check if API client is properly initialized
        if not hasattr(client, 'api_client') or not client.api_client:
            self.stdout.write(self.style.ERROR("Trendyol API client not properly initialized"))
            return
        
        # Fetch brands
        if data_type in ['brands', 'all']:
            self.stdout.write(self.style.NOTICE("Fetching brands..."))
            
            from trendyol.models import TrendyolBrand
            existing_count = TrendyolBrand.objects.count()
            
            if existing_count > 0 and not force:
                self.stdout.write(self.style.WARNING(
                    f"Found {existing_count} existing brands. Use --force to re-fetch."
                ))
            else:
                count = client.fetch_and_store_brands()
                self.stdout.write(self.style.SUCCESS(f"Fetched {count} brands"))
        
        # Fetch categories
        if data_type in ['categories', 'all']:
            self.stdout.write(self.style.NOTICE("Fetching categories..."))
            
            from trendyol.models import TrendyolCategory
            existing_count = TrendyolCategory.objects.count()
            
            if existing_count > 0 and not force:
                self.stdout.write(self.style.WARNING(
                    f"Found {existing_count} existing categories. Use --force to re-fetch."
                ))
            else:
                count = client.fetch_and_store_categories()
                self.stdout.write(self.style.SUCCESS(f"Fetched {count} categories"))
        
        self.stdout.write(self.style.SUCCESS(f"Data fetch complete at {timezone.now()}"))