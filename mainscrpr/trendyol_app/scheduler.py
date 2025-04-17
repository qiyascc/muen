from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.utils import timezone
import logging
from .services import check_pending_products

logger = logging.getLogger(__name__)

def start_scheduler():
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")
        
        # 2 dakikada bir bekleyen ürünlerin durumunu kontrol et
        scheduler.add_job(
            check_pending_products,
            'interval',
            minutes=2,
            id='check_pending_products',
            replace_existing=True
        )
        
        logger.info("Trendyol batch status check scheduler started")
        scheduler.start()
    except Exception as e:
        logger.error(f"Could not start scheduler: {e}")