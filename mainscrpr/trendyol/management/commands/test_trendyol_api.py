from django.core.management.base import BaseCommand
from django.utils import timezone
from trendyol.test_connection import (
    test_trendyol_api_connection,
    test_categories_api,
    test_fetch_and_store
)
from loguru import logger

class Command(BaseCommand):
    help = 'Test the Trendyol API connection'

    def handle(self, *args, **options):
        logger.info("Starting Trendyol API connection tests...")
        
        # Test API connection
        connection_ok = test_trendyol_api_connection()
        if connection_ok:
            self.stdout.write(self.style.SUCCESS('Successfully connected to Trendyol API'))
        else:
            self.stdout.write(self.style.ERROR('Failed to connect to Trendyol API'))
        
        # Test categories API
        categories_ok = test_categories_api()
        if categories_ok:
            self.stdout.write(self.style.SUCCESS('Successfully fetched categories from Trendyol API'))
        else:
            self.stdout.write(self.style.ERROR('Failed to fetch categories from Trendyol API'))
        
        # Test fetch and store functionality
        fetch_ok = test_fetch_and_store()
        if fetch_ok:
            self.stdout.write(self.style.SUCCESS('Successfully fetched and stored data in the database'))
        else:
            self.stdout.write(self.style.ERROR('Failed to fetch and store data'))
        
        # Overall status
        if connection_ok and categories_ok and fetch_ok:
            self.stdout.write(self.style.SUCCESS('All tests passed! API connection is working correctly.'))
        else:
            self.stdout.write(self.style.ERROR('Some tests failed. Check logs for details.'))