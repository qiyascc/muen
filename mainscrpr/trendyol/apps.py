from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class TrendyolConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trendyol'
    verbose_name = 'Trendyol Integration'
    
    def ready(self):
        """
        Set up scheduled tasks when the application starts.
        This will run the sync_trendyol command on startup and at regular intervals.
        """
        if settings.SCHEDULER_AUTOSTART:
            try:
                from django_apscheduler.jobstores import DjangoJobStore
                from apscheduler.schedulers.background import BackgroundScheduler
                from apscheduler.triggers.interval import IntervalTrigger
                import django.core.management
                
                scheduler = BackgroundScheduler()
                scheduler.add_jobstore(DjangoJobStore(), 'default')
                
                # Define the function to run the management command
                def run_sync_trendyol_full():
                    """
                    Function to run the sync_trendyol management command with all operations.
                    This handles new products, deleted products, and updates to existing products.
                    """
                    logger.info("Running scheduled task: sync_trendyol")
                    django.core.management.call_command('sync_trendyol')
                
                # Schedule the full sync job to run every 12 hours
                scheduler.add_job(
                    run_sync_trendyol_full,
                    trigger=IntervalTrigger(hours=12),
                    id='sync_trendyol_full',
                    max_instances=1,
                    replace_existing=True,
                )
                
                # Start the scheduler
                try:
                    logger.info("Starting scheduler for Trendyol product sync")
                    scheduler.start()
                    logger.info("Scheduled Trendyol product sync jobs successfully!")
                except Exception as e:
                    logger.error(f"Could not start scheduler: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Error setting up Trendyol scheduler: {str(e)}")