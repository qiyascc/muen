"""
Helper functions for Trendyol integration
"""
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from .api_integration import TrendyolAPI, ProductData

logger = logging.getLogger(__name__)

def convert_lcwaikiki_to_trendyol_product(
    lcw_product, 
    brand_id: int, 
    category_id: int,
    trendyol_product=None
) -> ProductData:
    """
    Convert LCWaikiki product data to Trendyol product format
    
    Args:
        lcw_product: LCWaikiki product instance
        brand_id: Trendyol brand ID 
        category_id: Trendyol category ID
        trendyol_product: Existing Trendyol product if updating
        
    Returns:
        ProductData instance
    """
    # Extract barcode and product code
    barcode = lcw_product.barcode or f"LCW-{lcw_product.id}"
    product_code = lcw_product.product_code or barcode
    
    # Parse price
    price = parse_turkish_price(lcw_product.price) if hasattr(lcw_product, 'price') else Decimal('0')
    
    # Extract images
    images = []
    if hasattr(lcw_product, 'image_url') and lcw_product.image_url:
        images.append(lcw_product.image_url)
        
    if hasattr(lcw_product, 'additional_images') and lcw_product.additional_images:
        if isinstance(lcw_product.additional_images, list):
            images.extend(lcw_product.additional_images)
    
    # Ensure we have valid images
    if not images:
        logger.warning(f"No valid images found for product {lcw_product.id}")
        images = ["https://www.lcwaikiki.com/images/no-image.jpg"]
    
    # Get product stock quantity
    quantity = 0
    if hasattr(lcw_product, 'stock_quantity') and lcw_product.stock_quantity is not None:
        quantity = lcw_product.stock_quantity
    elif hasattr(lcw_product, 'sizes') and lcw_product.sizes:
        # Sum up all size quantities
        for size in lcw_product.sizes:
            if hasattr(size, 'stock') and size.stock is not None:
                quantity += size.stock
    
    # Cap quantity at 20,000 (Trendyol API limit)
    quantity = min(quantity, 20000)
    if quantity <= 0:
        quantity = 0  # Ensure non-negative
    
    # Create ProductData object
    product_data = ProductData(
        barcode=barcode,
        title=lcw_product.title or "LC Waikiki Product",
        product_main_id=product_code,
        brand_id=brand_id,
        category_id=category_id,
        quantity=quantity,
        stock_code=product_code,
        price=price,
        sale_price=price,  # Same as regular price
        description=lcw_product.description or lcw_product.title or "LC Waikiki Product Description",
        image_url=images[0],
        additional_images=images[1:] if len(images) > 1 else [],
        attributes=[],  # Will be populated by API later
        vat_rate=18,  # Default VAT rate in Turkey
        currency_type="TRY",
    )
    
    return product_data

def parse_turkish_price(price_str: str) -> Decimal:
    """
    Parse price from Turkish format string
    
    Args:
        price_str: Price string (e.g., "159,99 TL")
        
    Returns:
        Decimal price value
    """
    if not price_str:
        return Decimal('0')
    
    # Remove any currency symbols and spaces
    price_str = re.sub(r'[^\d,.]', '', price_str)
    
    # Replace comma with period (Turkish decimal separator)
    price_str = price_str.replace(',', '.')
    
    try:
        return Decimal(price_str)
    except Exception as e:
        logger.error(f"Error converting price '{price_str}': {str(e)}")
        return Decimal('0')

def prepare_attributes_for_category(api: TrendyolAPI, category_id: int, product_data: Dict) -> List[Dict]:
    """
    Prepare required attributes for a category
    
    Args:
        api: TrendyolAPI instance
        category_id: Category ID
        product_data: Product data including color information
        
    Returns:
        List of attribute dictionaries
    """
    attributes = []
    
    try:
        # Fetch category attributes
        endpoint = f"product/product-categories/{category_id}/attributes"
        category_attrs = api.get(endpoint)
        
        # If API failed and returned an error dict instead of proper data
        if isinstance(category_attrs, dict) and category_attrs.get('error'):
            logger.error(f"Error fetching category attributes: {category_attrs.get('message')}")
            # Add default color attribute since it's usually required
            return [
                {
                    "attributeId": 348,  # Standard color attribute ID
                    "attributeName": "Renk",
                    "attributeValueId": 4294765628,  # Black/Siyah
                    "attributeValue": "Siyah" 
                }
            ]
        
        # Get color attribute (ID 348)
        color_info = None
        if 'color' in product_data and product_data['color']:
            color_info = product_data['color']
        
        # Track if we've added a color attribute
        has_color_attribute = False
        
        # Process category attributes
        for attr in category_attrs.get('categoryAttributes', []):
            # Skip if no values and not customizable
            if not attr.get('attributeValues') and not attr.get('allowCustom'):
                continue
                
            attribute = {
                "attributeId": attr['attribute']['id'],
                "attributeName": attr['attribute']['name']
            }
            
            # For color attribute (usually ID 348)
            if attr['attribute']['id'] == 348:
                has_color_attribute = True
                
                if color_info and attr.get('allowCustom'):
                    attribute["customAttributeValue"] = color_info
                else:
                    # Try to find color in available values if we have color info
                    color_found = False
                    if color_info and attr.get('attributeValues'):
                        for val in attr.get('attributeValues', []):
                            if color_info.lower() in val['name'].lower():
                                attribute["attributeValueId"] = val['id']
                                attribute["attributeValue"] = val['name']
                                color_found = True
                                break
                    
                    if not color_found and attr.get('attributeValues'):
                        # Use first available color if exact match not found
                        attribute["attributeValueId"] = attr['attributeValues'][0]['id']
                        attribute["attributeValue"] = attr['attributeValues'][0]['name']
            
            # For other required attributes
            elif attr.get('required', False):
                if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                    attribute["attributeValueId"] = attr['attributeValues'][0]['id']
                    attribute["attributeValue"] = attr['attributeValues'][0]['name']
                elif attr.get('allowCustom'):
                    attribute["customAttributeValue"] = f"Default {attr['attribute']['name']}"
            
            attributes.append(attribute)
        
        # If no color attribute was found but we know color is usually required
        if not has_color_attribute:
            # Add a default color attribute (black/siyah)
            attributes.append({
                "attributeId": 348,  # Standard color attribute ID
                "attributeName": "Renk",
                "attributeValueId": 4294765628,  # Black/Siyah
                "attributeValue": "Siyah"
            })
        
        # Always return at least some attributes (Trendyol usually requires some)
        if not attributes:
            # Add a default color attribute as fallback
            attributes.append({
                "attributeId": 348,  # Standard color attribute ID
                "attributeName": "Renk",
                "attributeValueId": 4294765628,  # Black/Siyah
                "attributeValue": "Siyah"
            })
                
        return attributes
    except Exception as e:
        logger.error(f"Error preparing attributes for category {category_id}: {str(e)}")
        # Return default color attribute as fallback
        return [{
            "attributeId": 348,  # Standard color attribute ID
            "attributeName": "Renk",
            "attributeValueId": 4294765628,  # Black/Siyah
            "attributeValue": "Siyah"
        }]