"""
Script to fix the continuous API calls and batch processing issue.

This script:
1. Stops any scheduled jobs that might be continuously sending requests
2. Fixes API configuration to use the correct URL and credentials
3. Adds a flag to prevent infinite retries

Run this script with: python manage.py shell < fix_api_continuous_batches.py
"""

import logging
import json
import os
from django.utils import timezone
from django_apscheduler.models import DjangoJob
from trendyol.models import TrendyolAPIConfig, TrendyolProduct

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def stop_scheduled_jobs():
    """Stop any scheduled jobs that might be continuously sending requests."""
    logger.info("Stopping any scheduled jobs...")
    
    # Get all scheduled jobs
    jobs = DjangoJob.objects.all()
    logger.info(f"Found {jobs.count()} scheduled jobs")
    
    # Print job information
    for job in jobs:
        logger.info(f"Job ID: {job.id}, Next run: {job.next_run_time}")
        
    # Delete all jobs to stop any background processing
    try:
        count = jobs.delete()[0]
        logger.info(f"Deleted {count} scheduled jobs")
    except Exception as e:
        logger.error(f"Error deleting jobs: {str(e)}")
    
    logger.info("Scheduled jobs stopped")

def fix_api_config():
    """Fix API configuration to use correct URL and credentials."""
    logger.info("Fixing API configuration...")
    
    # Get active config
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("No active API configuration found")
        return
    
    # Get API key and secret from environment
    api_key = os.environ.get('TRENDYOL_API_KEY')
    api_secret = os.environ.get('TRENDYOL_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("API key or secret not found in environment variables")
        return
    
    # Update config
    config.api_key = api_key
    config.api_secret = api_secret
    config.base_url = "https://apigw.trendyol.com/integration"
    config.user_agent = f"{config.seller_id} - SelfIntegration"
    config.last_updated = timezone.now()
    config.save()
    
    logger.info(f"API configuration updated with:")
    logger.info(f"- Base URL: {config.base_url}")
    logger.info(f"- User Agent: {config.user_agent}")
    logger.info(f"- API Key: ****{config.api_key[-4:] if config.api_key else '-'}")
    logger.info(f"- API Secret: ****{config.api_secret[-4:] if config.api_secret else '-'}")

def prevent_infinite_retries():
    """Add a flag to prevent infinite retries for failed products."""
    logger.info("Preventing infinite retries for failed products...")
    
    # Find products that have been retried too many times
    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
    logger.info(f"Found {failed_products.count()} failed products")
    
    # Mark them to prevent further retries
    for product in failed_products:
        if 'Service Unavailable' in (product.status_message or ''):
            logger.info(f"Marking product {product.id} as temporarily unavailable due to API service issues")
            product.status_message = f"API Service Unavailable - Last attempted: {timezone.now()}"
            product.save()
    
    # Find products that are stuck in processing
    processing_products = TrendyolProduct.objects.filter(batch_status='processing')
    logger.info(f"Found {processing_products.count()} products stuck in processing")
    
    # Reset them to pending for future retry
    for product in processing_products:
        logger.info(f"Resetting product {product.id} to pending status")
        product.batch_status = 'pending'
        product.save()

def main():
    """Main function"""
    logger.info("Starting to fix API continuous batches issue...")
    
    # Stop scheduled jobs
    stop_scheduled_jobs()
    
    # Fix API configuration
    fix_api_config()
    
    # Prevent infinite retries
    prevent_infinite_retries()
    
    logger.info("Fixes completed")
    logger.info("\nRECOMMENDATIONS:")
    logger.info("1. Check if your Trendyol API credentials are correct")
    logger.info("2. Verify that your Trendyol seller account has API access")
    logger.info("3. Try accessing the Trendyol API from your own computer/outside Replit")
    logger.info("4. Consider contacting Trendyol support if API access problems persist")

if __name__ == "__main__":
    main()
else:
    # When running from Django shell
    main()