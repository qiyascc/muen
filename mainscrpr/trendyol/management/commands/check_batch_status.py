"""
Django management command to check batch status for pending Trendyol products.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from trendyol.sync_manager import TrendyolSyncManager

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check batch status for pending Trendyol products'
    
    def add_arguments(self, parser):
        parser.add_argument('--max-items', type=int, default=50,
                            help='Maximum number of batches to check')
        parser.add_argument('--batch-id', type=str, default=None,
                            help='Specific batch ID to check')
    
    def handle(self, *args, **options):
        max_items = options['max_items']
        batch_id = options['batch_id']
        
        self.stdout.write(self.style.NOTICE(f"Starting batch check at {timezone.now()}"))
        
        # Initialize sync manager
        sync_manager = TrendyolSyncManager()
        
        if batch_id:
            self.stdout.write(self.style.NOTICE(f"Checking specific batch ID: {batch_id}"))
            
            # Check specific batch ID
            try:
                batch_status = sync_manager.client.check_batch_status(batch_id)
                
                if batch_status:
                    self.stdout.write(self.style.SUCCESS(f"Batch {batch_id} status:"))
                    self.stdout.write(self.style.SUCCESS(f"Status: {batch_status.get('status', 'Unknown')}"))
                    self.stdout.write(self.style.SUCCESS(f"Message: {batch_status.get('message', 'No message')}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Failed to retrieve batch status for {batch_id}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error checking batch {batch_id}: {str(e)}"))
        else:
            # Check all pending batches
            self.stdout.write(self.style.NOTICE(f"Checking up to {max_items} pending batches"))
            
            batch_count = sync_manager.check_batch_statuses(max_items=max_items)
            
            self.stdout.write(self.style.SUCCESS(f"Checked {batch_count} batch statuses"))
            
        self.stdout.write(self.style.SUCCESS(f"Batch check complete at {timezone.now()}"))