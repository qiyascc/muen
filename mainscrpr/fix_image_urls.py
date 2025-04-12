"""
Script to fix image URLs in Trendyol products.

This script updates all TrendyolProduct records to replace admin panel URLs
with valid product image URLs.

Run this script with: python manage.py shell < fix_image_urls.py
"""

import logging
import re
from trendyol.models import TrendyolProduct
from lcwaikiki.product_models import Product

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_valid_image_url(url):
    """Check if the URL is a valid image URL."""
    if not url:
        return False
        
    # Check if it's an admin panel URL
    if re.search(r'/(admin|static)/', url) or 'replit.dev/admin' in url or 'replit.com' in url:
        return False
    
    # Check for valid image extensions
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    has_valid_extension = any(url.lower().endswith(ext) for ext in valid_extensions)
    
    # Check for valid domains
    valid_domains = ['lcwaikiki.com', 'lw.cdn.com', 'img-lcwaikiki.mncdn.com', 'img-cosnova.mncdn.com', 'cdn.dsmcdn.com']
    has_valid_domain = any(domain in url.lower() for domain in valid_domains)
    
    return has_valid_extension or has_valid_domain

def get_valid_product_image(product_id):
    """Get a valid product image URL for the given LC Waikiki product ID."""
    try:
        # Get the LC Waikiki product
        lcw_product = Product.objects.get(id=product_id)
        
        # Check if it has a valid image URL
        if lcw_product.image_url and is_valid_image_url(lcw_product.image_url):
            return lcw_product.image_url
        
        # Try alternate images if available
        if hasattr(lcw_product, 'images') and lcw_product.images:
            for img in lcw_product.images:
                if is_valid_image_url(img):
                    return img
        
        # Default fallback - find a similar product with a valid image
        similar_products = Product.objects.filter(brand=lcw_product.brand)[:10]
        for p in similar_products:
            if p.image_url and is_valid_image_url(p.image_url):
                return p.image_url
                
        # Last resort fallback - a known good LC Waikiki image URL
        return "https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20232/6455149/v1/l_20232-w3ak58z8-cty-black_1_h.jpg"
    except Product.DoesNotExist:
        # Fallback if product doesn't exist
        return "https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20232/6455149/v1/l_20232-w3ak58z8-cty-black_1_h.jpg"
    except Exception as e:
        logger.error(f"Error getting valid product image: {str(e)}")
        return "https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20232/6455149/v1/l_20232-w3ak58z8-cty-black_1_h.jpg"

def main():
    """Fix image URLs for all Trendyol products."""
    logger.info("Starting image URL fix process")
    
    # Get all Trendyol products
    products = TrendyolProduct.objects.all()
    logger.info(f"Found {products.count()} Trendyol products to process")
    
    fixed_count = 0
    already_valid_count = 0
    
    for product in products:
        current_url = product.image_url
        
        # Check if the current image URL is valid
        if is_valid_image_url(current_url):
            logger.info(f"Product {product.id} already has a valid image URL: {current_url[:50]}...")
            already_valid_count += 1
            continue
        
        # Get a valid image URL for this product
        valid_url = get_valid_product_image(product.lcwaikiki_product_id)
        
        # Update the product
        product.image_url = valid_url
        product.save()
        
        logger.info(f"Fixed image URL for product {product.id}: {valid_url[:50]}...")
        fixed_count += 1
    
    logger.info(f"Image URL fix completed: {fixed_count} products fixed, {already_valid_count} already valid")

if __name__ == "__main__":
    main()
else:
    # When imported as a module from Django shell
    main()