"""
Trendyol API Helpers Module

This module contains helper functions for interacting with the Trendyol API,
especially for fetching categories, attributes, and other data directly from the API.
"""

import logging
import json
import requests
from typing import Dict, List, Optional, Any, Union
from .models import TrendyolProduct, TrendyolCategory, TrendyolBrand
from .api_client import get_api_client

logger = logging.getLogger(__name__)

def fetch_categories():
    """
    Fetch all categories from Trendyol API and update the local database.
    Returns the list of categories.
    """
    client = get_api_client()
    if not client:
        logger.error("Could not get API client to fetch categories")
        return []
    
    try:
        # Fetch categories via the API
        url = "product/product-categories"
        response = client.make_request("GET", url)
        
        if not response or response.status_code != 200:
            error_msg = f"Error fetching categories: {response.status_code if response else 'No response'}"
            logger.error(error_msg)
            return []
        
        data = response.json()
        categories = data.get('categories', [])
        
        # Log the number of categories fetched
        logger.info(f"Fetched {len(categories)} categories from Trendyol API")
        
        # Process and save categories
        _process_categories(categories)
        
        return categories
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        return []

def _process_categories(categories, parent_id=None, parent_path=""):
    """
    Process and save categories recursively.
    """
    for category in categories:
        category_id = category.get('id')
        name = category.get('name', '')
        
        # Build the category path
        path = f"{parent_path}{'/' if parent_path else ''}{name}"
        
        # Save or update the category
        try:
            cat_obj, created = TrendyolCategory.objects.update_or_create(
                category_id=category_id,
                defaults={
                    'name': name,
                    'parent_id': parent_id,
                    'path': path,
                    'is_active': True,
                    'has_children': bool(category.get('subCategories'))
                }
            )
            
            if created:
                logger.info(f"Created new category: {name} (ID: {category_id})")
            else:
                logger.info(f"Updated existing category: {name} (ID: {category_id})")
                
            # Process subcategories recursively
            if category.get('subCategories'):
                _process_categories(
                    category['subCategories'], 
                    parent_id=category_id,
                    parent_path=path
                )
                
        except Exception as e:
            logger.error(f"Error saving category {name} (ID: {category_id}): {str(e)}")

def fetch_category_attributes(category_id):
    """
    Fetch attributes for a specific category from Trendyol API.
    Returns the attribute data.
    """
    client = get_api_client()
    if not client:
        logger.error(f"Could not get API client to fetch attributes for category {category_id}")
        return {}
    
    try:
        # Fetch attributes via the API
        url = f"product/product-categories/{category_id}/attributes"
        response = client.make_request("GET", url)
        
        if not response or response.status_code != 200:
            error_msg = f"Error fetching attributes for category {category_id}: {response.status_code if response else 'No response'}"
            logger.error(error_msg)
            return {}
        
        data = response.json()
        logger.info(f"Fetched attributes for category {category_id} from Trendyol API")
        
        # Debug log for empty attributes
        if not data.get('categoryAttributes'):
            logger.warning(f"No attributes found for category {category_id}")
            
        return data
    except Exception as e:
        logger.error(f"Error fetching attributes for category {category_id}: {str(e)}")
        return {}

def get_required_attributes(category_id, product_title=None, product_color=None, product_size=None):
    """
    Get required attributes for a specific category.
    Returns a list of attribute dictionaries in the format required by Trendyol API.
    
    Args:
        category_id: The category ID
        product_title: The product title to infer attributes from (optional)
        product_color: The product color if known (optional)
        product_size: The product size if known (optional)
    
    Returns:
        List of attribute dictionaries in the format required by Trendyol API
    """
    logger.info(f"Getting required attributes for category ID={category_id}")
    
    try:
        # Fetch category attributes
        data = fetch_category_attributes(category_id)
        if not data:
            logger.warning(f"No attributes data for category {category_id}")
            return []
        
        attributes = []
        
        # Process category attributes
        logger.info(f"Processing {len(data.get('categoryAttributes', []))} attributes for category {category_id}")
        
        for attr in data.get('categoryAttributes', []):
            # Skip attributes without ID
            if not attr.get('attribute') or not attr['attribute'].get('id'):
                logger.warning(f"Skipping attribute without ID")
                continue
            
            # Get attribute details
            attribute_id = attr['attribute']['id']
            attribute_name = attr['attribute'].get('name', 'Unknown')
            
            # Check if attribute is required
            is_required = attr.get('required', False)
            logger.info(f"Processing attribute: {attribute_name} (ID: {attribute_id}, Required: {is_required})")
            
            # Only add required attributes
            if not is_required:
                logger.info(f"Skipping non-required attribute: {attribute_name}")
                continue
            
            # Special handling for color attribute if product_color is provided
            if attribute_name.lower() in ['renk', 'color'] and product_color:
                # Try to find a matching color value
                if attr.get('attributeValues'):
                    for value in attr['attributeValues']:
                        if value.get('name', '').lower() == product_color.lower():
                            attributes.append({
                                "attributeId": attribute_id,
                                "attributeValueId": value['id']
                            })
                            logger.info(f"Added color attribute: {attribute_name}={value.get('name', 'Unknown')}")
                            break
                    else:
                        # If no exact match, use the first value
                        if attr['attributeValues']:
                            attributes.append({
                                "attributeId": attribute_id,
                                "attributeValueId": attr['attributeValues'][0]['id']
                            })
                            logger.info(f"Added default color attribute: {attribute_name}={attr['attributeValues'][0].get('name', 'Unknown')}")
                continue
            
            # Skip if no values are available and custom is not allowed
            if not attr.get('attributeValues') and not attr.get('allowCustom'):
                logger.info(f"Skipping attribute {attribute_name} with no values")
                continue
            
            # If there are attribute values, use the first one
            if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                attribute_value_id = attr['attributeValues'][0]['id']
                attribute_value_name = attr['attributeValues'][0].get('name', 'Unknown')
                
                attributes.append({
                    "attributeId": attribute_id,
                    "attributeValueId": attribute_value_id
                })
                logger.info(f"Added attribute: {attribute_name}={attribute_value_name}")
        
        # Log summary of attributes
        logger.info(f"Returning {len(attributes)} attributes for category {category_id}")
        return attributes
        
    except Exception as e:
        logger.error(f"Error getting required attributes: {str(e)}")
        return []

def fetch_brands():
    """
    Fetch all brands from Trendyol API and update the local database.
    Returns the list of brands.
    """
    client = get_api_client()
    if not client:
        logger.error("Could not get API client to fetch brands")
        return []
    
    try:
        # Fetch brands via the API
        url = "brands"
        response = client.make_request("GET", url)
        
        if not response or response.status_code != 200:
            error_msg = f"Error fetching brands: {response.status_code if response else 'No response'}"
            logger.error(error_msg)
            return []
        
        data = response.json()
        brands = data.get('brands', [])
        
        # Log the number of brands fetched
        logger.info(f"Fetched {len(brands)} brands from Trendyol API")
        
        # Process and save brands
        for brand in brands:
            brand_id = brand.get('id')
            name = brand.get('name', '')
            
            # Save or update the brand
            try:
                brand_obj, created = TrendyolBrand.objects.update_or_create(
                    brand_id=brand_id,
                    defaults={
                        'name': name,
                        'is_active': True
                    }
                )
                
                if created:
                    logger.debug(f"Created new brand: {name} (ID: {brand_id})")
                else:
                    logger.debug(f"Updated existing brand: {name} (ID: {brand_id})")
                    
            except Exception as e:
                logger.error(f"Error saving brand {name} (ID: {brand_id}): {str(e)}")
        
        return brands
    except Exception as e:
        logger.error(f"Error fetching brands: {str(e)}")
        return []

def find_category_for_product(api_client, product_name, category_name=None):
    """
    Find the best category ID for a product using Trendyol API.
    
    Args:
        api_client: The Trendyol API client
        product_name: The product name/title
        category_name: The category name (optional)
        
    Returns:
        The category ID if found, None otherwise
    """
    logger.info(f"Finding category for product using API helpers")
    
    # Prefer category_name if available
    search_term = category_name if category_name else product_name
    
    if not search_term:
        logger.warning("No search term provided for category search")
        return None
    
    try:
        # First try finding in database for exact match
        if category_name:
            db_category = TrendyolCategory.objects.filter(
                name__iexact=category_name,
                is_active=True
            ).first()
            
            if db_category:
                logger.info(f"Found exact category match in database: {db_category.name} (ID: {db_category.category_id})")
                return db_category.category_id
        
        # Get categories from the API
        url = "product/product-categories"
        response = api_client.make_request("GET", url)
        
        if response and response.status_code == 200:
            data = response.json()
            categories = data.get('categories', [])
            
            # Log how many categories we got
            logger.info(f"Got {len(categories)} categories from API")
            
            # First try exact match
            exact_matches = []
            for category in _find_matching_categories(categories, search_term, match_type='exact'):
                exact_matches.append(category)
            
            if exact_matches:
                chosen_category = exact_matches[0]
                logger.info(f"Found exact category match: {chosen_category['name']} (ID: {chosen_category['id']})")
                return chosen_category['id']
            
            # Try contains match
            contains_matches = []
            for category in _find_matching_categories(categories, search_term, match_type='contains'):
                contains_matches.append(category)
            
            if contains_matches:
                chosen_category = contains_matches[0]
                logger.info(f"Found partial category match: {chosen_category['name']} (ID: {chosen_category['id']})")
                return chosen_category['id']
        
        # If we get here, no match was found
        logger.warning(f"No category match found for '{search_term}'")
        return None
        
    except Exception as e:
        logger.error(f"Error finding category: {str(e)}")
        return None

def _find_matching_categories(categories, search_term, match_type='exact'):
    """
    Recursively find categories that match the search term.
    
    Args:
        categories: List of category dictionaries
        search_term: The term to search for
        match_type: Type of match ('exact', 'contains', or 'partial')
        
    Yields:
        Matching category dictionaries
    """
    search_term_lower = search_term.lower()
    
    for category in categories:
        category_name_lower = category.get('name', '').lower()
        
        if match_type == 'exact' and search_term_lower == category_name_lower:
            yield category
        elif match_type == 'contains' and (search_term_lower in category_name_lower or category_name_lower in search_term_lower):
            yield category
        
        # Recursively search subcategories
        if 'subCategories' in category and category['subCategories']:
            for subcategory in _find_matching_categories(category['subCategories'], search_term, match_type):
                yield subcategory

def find_brand_by_name(name):
    """
    Find a brand by name in the Trendyol API.
    Returns the brand ID if found, None otherwise.
    """
    if not name:
        return None
    
    client = get_api_client()
    if not client:
        logger.error("Could not get API client to find brand")
        return None
    
    try:
        # Try exact match first from database
        brand = TrendyolBrand.objects.filter(name__iexact=name, is_active=True).first()
        if brand:
            logger.info(f"Found exact brand match in database: {brand.name} (ID: {brand.brand_id})")
            return brand.brand_id
        
        # Try partial match from database
        brand = TrendyolBrand.objects.filter(name__icontains=name, is_active=True).first()
        if brand:
            logger.info(f"Found partial brand match in database: {brand.name} (ID: {brand.brand_id})")
            return brand.brand_id
        
        # If not found in database, try API
        url = f"brands/by-name?name={name}"
        response = client.make_request("GET", url)
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get('id'):
                logger.info(f"Found brand in API: {data.get('name')} (ID: {data.get('id')})")
                
                # Save to database for future use
                try:
                    TrendyolBrand.objects.update_or_create(
                        brand_id=data['id'],
                        defaults={
                            'name': data.get('name', ''),
                            'is_active': True
                        }
                    )
                except Exception as e:
                    logger.error(f"Error saving brand from API: {str(e)}")
                
                return data['id']
        
        # Use default brand ID of 7651 (LC Waikiki) if not found
        logger.warning(f"Brand '{name}' not found, using default brand ID 7651")
        return 7651
        
    except Exception as e:
        logger.error(f"Error finding brand by name '{name}': {str(e)}")
        return 7651  # Default to LC Waikiki brand ID

def submit_product_to_trendyol(product_id, api_client=None):
    """
    Submit a product to Trendyol using the API.
    This function is a wrapper around the API client's sync_product_to_trendyol function.
    
    Args:
        product_id: The ID of the TrendyolProduct to submit
        api_client: Optional API client to use (if None, a new one will be created)
        
    Returns:
        Dict with status info about the submission
    """
    from .models import TrendyolProduct
    from . import api_client as api_client_module
    
    logger.info(f"Submitting product ID {product_id} to Trendyol")
    
    try:
        # Get the product
        product = TrendyolProduct.objects.get(id=product_id)
        
        # If no API client was provided, get a new one
        client = api_client or api_client_module.get_api_client()
        if not client:
            logger.error("Could not get API client to submit product")
            return {
                'success': False,
                'message': "No active Trendyol API configuration found"
            }
        
        # Use the API client to sync the product
        result = api_client_module.sync_product_to_trendyol(product)
        
        if result:
            logger.info(f"Successfully submitted product {product_id} to Trendyol")
            return {
                'success': True,
                'batch_id': product.batch_id,
                'message': f"Product submitted with batch ID: {product.batch_id}"
            }
        else:
            logger.error(f"Failed to submit product {product_id} to Trendyol")
            return {
                'success': False,
                'message': product.status_message or "Failed to submit product"
            }
    except TrendyolProduct.DoesNotExist:
        logger.error(f"Product with ID {product_id} does not exist")
        return {
            'success': False,
            'message': f"Product with ID {product_id} does not exist"
        }
    except Exception as e:
        logger.error(f"Error submitting product {product_id} to Trendyol: {str(e)}")
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }

def prepare_product_for_submission(product_id):
    """
    Prepare a product for submission to Trendyol.
    This function calls the API client's prepare_product_data function.
    
    Args:
        product_id: The ID of the TrendyolProduct to prepare
        
    Returns:
        Dict with the prepared product data or error info
    """
    from .models import TrendyolProduct
    from . import api_client as api_client_module
    
    logger.info(f"Preparing product ID {product_id} for Trendyol submission")
    
    try:
        # Get the product
        product = TrendyolProduct.objects.get(id=product_id)
        
        # Use the API client to prepare the product data
        data = api_client_module.prepare_product_data(product)
        
        if data:
            logger.info(f"Successfully prepared product {product_id} for Trendyol")
            return {
                'success': True,
                'data': data
            }
        else:
            logger.error(f"Failed to prepare product {product_id} for Trendyol")
            return {
                'success': False,
                'message': "Failed to prepare product data"
            }
    except TrendyolProduct.DoesNotExist:
        logger.error(f"Product with ID {product_id} does not exist")
        return {
            'success': False,
            'message': f"Product with ID {product_id} does not exist"
        }
    except Exception as e:
        logger.error(f"Error preparing product {product_id} for Trendyol: {str(e)}")
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }