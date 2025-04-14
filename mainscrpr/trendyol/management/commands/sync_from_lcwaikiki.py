"""
Django management command to synchronize products from LCWaikiki to Trendyol.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from trendyol.sync_manager import TrendyolSyncManager

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Synchronize products from LCWaikiki to Trendyol'
    
    def add_arguments(self, parser):
        parser.add_argument('--max-items', type=int, default=100,
                            help='Maximum number of items to process')
        parser.add_argument('--batch-size', type=int, default=10,
                            help='Number of items to process in each batch')
        parser.add_argument('--include-failed', action='store_true',
                            help='Include previously failed products')
        parser.add_argument('--dry-run', action='store_true',
                            help='Do not actually submit to Trendyol')
    
    def handle(self, *args, **options):
        max_items = options['max_items']
        batch_size = options['batch_size']
        include_failed = options['include_failed']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.NOTICE(f"Starting synchronization at {timezone.now()}"))
        self.stdout.write(self.style.NOTICE(f"Max items: {max_items}, Batch size: {batch_size}"))
        
        if include_failed:
            self.stdout.write(self.style.WARNING("Including previously failed products"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No actual API submissions will be made"))
        
        # Initialize sync manager
        sync_manager = TrendyolSyncManager()
        
        # Perform synchronization
        success_count, failed_count, total_count = sync_manager.sync_products(
            max_items=max_items,
            batch_size=batch_size,
            include_failed=include_failed,
            dry_run=dry_run
        )
        
        # Check batch statuses
        batch_count = sync_manager.check_batch_statuses(max_items=50)
        
        # Report results
        self.stdout.write(self.style.SUCCESS(f"Synchronization complete at {timezone.now()}"))
        self.stdout.write(self.style.SUCCESS(f"Processed: {total_count} products"))
        self.stdout.write(self.style.SUCCESS(f"Successful: {success_count}"))
        self.stdout.write(self.style.WARNING(f"Failed: {failed_count}"))
        self.stdout.write(self.style.SUCCESS(f"Checked {batch_count} batch statuses"))