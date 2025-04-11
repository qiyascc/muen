from django.apps import AppConfig
from django.conf import settings


def run_sync_products_full():
    """
    Function to run the sync_products management command with all operations.
    This handles new products, deleted products, and updates to existing products.
    This needs to be defined as a module-level function for proper serialization.
    
    The max-items parameter is set to 100 to avoid processing too many items at once
    and causing timeouts or excessive resource usage.
    """
    from django.core.management import call_command
    call_command('sync_products', '--all', '--max-items=100')


def run_sync_products_new_only():
    """
    Function to run the sync_products management command to check for new products only.
    This is a lightweight operation that can run more frequently.
    
    The max-items parameter is set to 50 since this operation runs more frequently.
    """
    from django.core.management import call_command
    call_command('sync_products', '--check-new', '--max-items=50')


def run_sync_products_deleted_only():
    """
    Function to run the sync_products management command to check for deleted products only.
    This is a lightweight operation that can run at a medium frequency.
    
    The max-items parameter is set to 75 for this medium frequency operation.
    """
    from django.core.management import call_command
    call_command('sync_products', '--check-deleted', '--max-items=75')


class LcwaikikiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lcwaikiki'
    
    def ready(self):
        """
        Set up scheduled tasks when the application starts.
        This will run the sync_products command on startup and at regular intervals.
        """
        # Avoid running scheduler in management commands like migrate
        import sys
        if 'runserver' not in sys.argv and 'uvicorn' not in sys.argv:
            return
            
        # Import here to avoid AppRegistryNotReady exception
        from django_apscheduler.jobstores import DjangoJobStore
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        import datetime
        
        try:
            # Configure the scheduler
            scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
            scheduler.add_jobstore(DjangoJobStore(), "default")
            
            # Schedule the main sync job to run every 4 hours
            # This runs all sync operations (new, deleted, and updates)
            scheduler.add_job(
                run_sync_products_full,
                trigger=IntervalTrigger(hours=4),
                id='sync_products_full',
                name='Sync all LC Waikiki product data',
                replace_existing=True,
                next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=60),
            )
            
            # Schedule specialized jobs that run at different intervals:
            
            # Check for new products every hour (lightweight)
            scheduler.add_job(
                run_sync_products_new_only,
                trigger=IntervalTrigger(hours=1),
                id='sync_products_new',
                name='Check for new LC Waikiki products',
                replace_existing=True,
            )
            
            # Check for deleted products every 2 hours (lightweight)
            scheduler.add_job(
                run_sync_products_deleted_only,
                trigger=IntervalTrigger(hours=2),
                id='sync_products_deleted',
                name='Check for deleted LC Waikiki products',
                replace_existing=True,
            )
            
            # Start the scheduler
            scheduler.start()
            print("Scheduled product sync jobs successfully!")
            
        except Exception as e:
            print(f"Scheduler setup error: {e}")
