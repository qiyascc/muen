from django.apps import AppConfig
from django.conf import settings
import logging
import sys

logger = logging.getLogger(__name__)


def run_sync_trendyol():
    """
    Function to run the sync_trendyol management command.
    This handles new, updated, and deleted products.
    
    This needs to be defined as a module-level function for proper serialization.
    """
    try:
        from django.core.management import call_command
        logger.info("Running Trendyol synchronization...")
        call_command('sync_trendyol', max_items=50)
        logger.info("Trendyol synchronization completed successfully.")
    except Exception as e:
        logger.error(f"Error running Trendyol synchronization: {str(e)}")


class TrendyolConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trendyol'
    verbose_name = 'Trendyol Integration'

    def ready(self):
        """
        Set up scheduled tasks when the application starts.
        This will run the sync_trendyol command at regular intervals.
        """
        # Avoid running scheduler in management commands
        if 'manage.py' in sys.argv:
            return
            
        if not settings.DEBUG or 'runserver' in sys.argv:
            try:
                from django_apscheduler.jobstores import DjangoJobStore
                from apscheduler.schedulers.background import BackgroundScheduler
                from apscheduler.triggers.interval import IntervalTrigger
                from django.core.management import call_command
                
                logger.info("Setting up Trendyol scheduler...")
                
                # Create scheduler
                scheduler = BackgroundScheduler()
                scheduler.add_jobstore(DjangoJobStore(), "default")
                
                # Add Trendyol synchronization job
                # Run every 12 hours
                scheduler.add_job(
                    run_sync_trendyol,
                    trigger=IntervalTrigger(hours=12),
                    id="trendyol_sync",
                    name="Synchronize with Trendyol API",
                    replace_existing=True,
                )
                
                # Start scheduler
                scheduler.start()
                logger.info("Trendyol scheduler started successfully.")
                
                # Run initial sync
                # call_command('sync_trendyol')
                
            except Exception as e:
                logger.error(f"Error setting up Trendyol scheduler: {str(e)}")