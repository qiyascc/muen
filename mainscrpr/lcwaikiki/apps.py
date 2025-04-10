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
    # Prevent running in non-server contexts
    if not self._is_main_process():
      return

    # Use a try-except block to handle the scheduler more gracefully
    try:
      self._start_scheduler()
    except Exception as e:
      import sys
      print(f"Error starting scheduler: {e}", file=sys.stderr)

  def _is_main_process(self):
    import sys
    is_runserver = 'runserver' in sys.argv
    is_uvicorn = 'uvicorn' in sys.argv and '--workers' not in sys.argv
    return is_runserver or is_uvicorn

  def _start_scheduler(self):
    # Delay imports to avoid AppRegistry issues
    from django_apscheduler.jobstores import DjangoJobStore
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    import datetime
    import atexit
    import threading

    try:
      scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
      scheduler.add_jobstore(DjangoJobStore(), "default")

      # Ensure job is added only once
      if not scheduler.get_job('refresh_product_list'):
        scheduler.add_job(run_refresh_products_command,
                          trigger=IntervalTrigger(hours=12),
                          id='refresh_product_list',
                          name='Refresh product list',
                          replace_existing=True,
                          max_instances=1,
                          next_run_time=datetime.datetime.now() +
                          datetime.timedelta(seconds=10),
                          coalesce=True,
                          misfire_grace_time=60)

      scheduler.start()

      # Only register atexit handler if we're in the main thread
      if threading.current_thread() is threading.main_thread():
        atexit.register(lambda: scheduler.shutdown())
      print("Scheduler started successfully!")
    except Exception as e:
      print(f"Error starting scheduler: {e}")
