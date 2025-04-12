"""
Script to fix model schema issues and constraints in the Trendyol products model.

This script updated the test product with default values for required fields
to prevent not-null constraint violations.

Run this script with: python manage.py shell < fix_model_schema.py
"""

import logging
from trendyol.models import TrendyolProduct
from django.utils import timezone

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_test_product():
    """Update the test product with default values for required fields."""
    test_product = TrendyolProduct.objects.filter(title__startswith='TEST PRODUCT').first()
    if not test_product:
        logger.error("No test product found.")
        return False
    
    logger.info(f"Found test product: {test_product.id} - {test_product.title}")
    
    # Show current values
    logger.info("Current values:")
    for field in test_product._meta.fields:
        value = getattr(test_product, field.name)
        logger.info(f"- {field.name}: {value}")
    
    # Update with default values for required fields
    test_product.batch_id = 'pending'  # Default value for batch_id
    test_product.batch_status = 'pending'
    test_product.status_message = 'Ready for submission'
    test_product.save()
    
    logger.info("Test product updated with default values.")
    return True

def create_minimal_product():
    """Create a minimal test product with all required fields."""
    try:
        # Check if we already have a minimal test product
        existing = TrendyolProduct.objects.filter(title__startswith='MINIMAL TEST').first()
        if existing:
            logger.info(f"Using existing minimal test product: {existing.id} - {existing.title}")
            return existing
        
        # Create a new minimal test product
        new_product = TrendyolProduct(
            title='MINIMAL TEST PRODUCT',
            barcode='MINTEST123456',
            description='Minimal test product description',
            price='199.99',
            brand_id=102,  # LC Waikiki
            category_id=2356,
            image_url='https://img-lcwaikiki.mncdn.com/mnresize/1200/1800/pim/productimages/20231/5915299/l_20231-s37982z8-ctk-1-t2899_2.jpg',
            batch_id='pending',  # Set a default value
            batch_status='pending',
            status_message='Ready for submission'
        )
        new_product.save()
        
        logger.info(f"Created new minimal test product: {new_product.id} - {new_product.title}")
        return new_product
    except Exception as e:
        logger.error(f"Error creating minimal test product: {str(e)}")
        return None

def main():
    """Main function."""
    logger.info("Starting model schema fix...")
    
    # Update test product
    update_success = update_test_product()
    
    if not update_success:
        logger.info("Creating a new minimal test product...")
        create_minimal_product()
    
    logger.info("Model schema fix completed.")

if __name__ == "__main__":
    main()
else:
    # When imported from Django shell
    main()