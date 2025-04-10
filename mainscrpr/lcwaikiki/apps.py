from django.apps import AppConfig
from django.conf import settings


def run_refresh_products_command():
    """
    Function to run the refresh_product_list management command.
    This needs to be defined as a module-level function for proper serialization.
    """
    from django.core.management import call_command
    call_command('refresh_product_list')


class LcwaikikiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lcwaikiki'
    
    def ready(self):
        """
        Set up scheduled tasks when the application starts.
        This will run the refresh_product_list command on startup and every 12 hours.
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
            
            # Add the job to run every 12 hours
            scheduler.add_job(
                run_refresh_products_command,
                trigger=IntervalTrigger(hours=12),
                id='refresh_product_list',
                name='Refresh LC Waikiki product list',
                replace_existing=True,
            )
            
            # Run once on startup (in 60 seconds to allow Django to fully initialize)
            scheduler.add_job(
                run_refresh_products_command,
                id='refresh_product_list_startup',
                name='Refresh LC Waikiki product list on startup',
                replace_existing=True,
                next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=60),
            )
            
            # Start the scheduler
            scheduler.start()
            print("Scheduled jobs successfully!")
            
        except Exception as e:
            print(f"Scheduler setup error: {e}")
