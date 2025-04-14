"""
Enhanced OpenAI Product Processor

This module provides advanced AI-powered processing for product data,
with flexible attribute handling without requiring mandatory fields.
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# OpenAI client configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)
DEFAULT_MODEL = "gpt-4o"  # Use the latest model (released May 13, 2024)

class ProductAttributeProcessor:
    """Enhanced AI-powered product attribute processor"""
    
    def __init__(self, category_finder, model=DEFAULT_MODEL):
        self.category_finder = category_finder
        self.model = model
    
    def optimize_product_data(self, lcw_product, category_id=None):
        """
        Process product data using AI to optimize it for Trendyol
        with flexible attribute handling
        """
        try:
            # Get basic product info
            product_info = self._extract_product_info(lcw_product)
            
            # Find category if not provided
            if not category_id:
                category_name = product_info.get('category_name', '')
                if not category_name:
                    category_name = lcw_product.category_name or lcw_product.category or ''
                    
                # If we still don't have a category, extract from title
                if not category_name and product_info.get('title'):
                    category_name = self._extract_category_from_title(product_info['title'])
                    
                category_id = self.category_finder.find_best_category(category_name)
                logger.info(f"AI found category ID: {category_id} for '{category_name}'")
            
            # Get attributes for this category
            all_attributes = self.category_finder.get_all_attributes(category_id)
            
            # Analyze product details with AI to set attributes
            attributes = self._process_attributes_with_ai(
                product_info=product_info,
                category_id=category_id,
                category_attributes=all_attributes
            )
            
            # Enhance product data
            enhanced_data = {
                'title': self._optimize_title(product_info['title']),
                'description': product_info.get('description', ''),
                'categoryId': category_id,
                'attributes': attributes
            }
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Error in AI processing: {str(e)}")
            # Return limited data if AI processing fails
            return {
                'title': lcw_product.title[:100] if lcw_product.title else '',
                'categoryId': category_id or 1,
                'attributes': []
            }
    
    def _extract_product_info(self, lcw_product):
        """Extract key information from LC Waikiki product"""
        product_info = {
            'title': lcw_product.title if hasattr(lcw_product, 'title') else '',
            'description': lcw_product.description if hasattr(lcw_product, 'description') else '',
            'category_name': lcw_product.category_name if hasattr(lcw_product, 'category_name') else '',
            'price': lcw_product.price if hasattr(lcw_product, 'price') else 0
        }
        
        # Add color information if available
        if hasattr(lcw_product, 'color') and lcw_product.color:
            product_info['color'] = lcw_product.color
        
        # Add any other available information
        if hasattr(lcw_product, 'sizes'):
            product_info['sizes'] = lcw_product.sizes
            
        if hasattr(lcw_product, 'material'):
            product_info['material'] = lcw_product.material
            
        return product_info
    
    def _extract_category_from_title(self, title):
        """Extract potential category from product title"""
        if not title:
            return ""
            
        # Extract noun phrases that might indicate category
        common_categories = [
            'elbise', 'gömlek', 'tişört', 't-shirt', 'pantolon', 'jean',
            'ayakkabı', 'çanta', 'ceket', 'mont', 'kazak', 'hırka',
            'etek', 'şort', 'mayo', 'bikini', 'pijama', 'çorap',
            'iç çamaşırı', 'takım', 'set'
        ]
        
        title_lower = title.lower()
        for category in common_categories:
            if category in title_lower:
                return category
                
        # If no specific category found, use general type
        if 'kadın' in title_lower or 'kadin' in title_lower:
            return 'kadın giyim'
        elif 'erkek' in title_lower:
            return 'erkek giyim'
        elif 'çocuk' in title_lower or 'cocuk' in title_lower:
            return 'çocuk giyim'
        elif 'bebek' in title_lower:
            return 'bebek giyim'
            
        return "giyim"  # Default
    
    def _optimize_title(self, title):
        """Optimize product title - truncate if needed and normalize whitespace"""
        if not title:
            return ""
            
        # Remove excessive whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Truncate if longer than 100 characters
        if len(title) > 100:
            title = title[:97] + '...'
            
        return title
    
    def _process_attributes_with_ai(self, product_info, category_id, category_attributes):
        """Use AI to process and determine product attributes"""
        try:
            # Prepare attribute info for AI
            attribute_info = []
            for attr in category_attributes:
                attr_name = attr['attribute']['name']
                attr_id = attr['attribute']['id']
                required = attr.get('required', False)
                
                values = []
                for val in attr.get('attributeValues', []):
                    values.append({
                        'id': val['id'],
                        'name': val['name']
                    })
                
                attribute_info.append({
                    'name': attr_name,
                    'id': attr_id,
                    'required': required,
                    'values': values
                })
            
            # Create AI prompt
            prompt = f"""
            Analyze this product information and determine the appropriate attribute values for Trendyol:
            
            Product Title: {product_info.get('title', 'Unknown')}
            Product Description: {product_info.get('description', 'Not available')}
            """
            
            # Add color if available
            if 'color' in product_info:
                prompt += f"\nProduct Color: {product_info['color']}"
            
            # Add sizes if available
            if 'sizes' in product_info:
                sizes_text = ', '.join(str(s) for s in product_info['sizes'])
                prompt += f"\nAvailable Sizes: {sizes_text}"
            
            prompt += "\n\nAttributes to determine:"
            for attr in attribute_info:
                values_text = ', '.join(f"{v['name']} (ID: {v['id']})" for v in attr['values'][:5])
                if len(attr['values']) > 5:
                    values_text += f", ... ({len(attr['values'])-5} more)"
                    
                prompt += f"\n- {attr['name']} (ID: {attr['id']}), Required: {attr['required']}"
                prompt += f"\n  Available values: {values_text}"
            
            prompt += """
            
            For each attribute, determine the most appropriate value based on the product information.
            Response format:
            {
              "attributes": [
                {"attributeId": id_number, "attributeValueId": value_id_number},
                ...
              ]
            }
            
            Include ALL required attributes in your response. For optional attributes, include them only if you can determine appropriate values.
            Use numeric IDs for both attributeId and attributeValueId.
            """
            
            # Call OpenAI API
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a product categorization expert for e-commerce platforms."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            # Check result format
            if 'attributes' not in result or not isinstance(result['attributes'], list):
                logger.warning("Invalid AI response format, using empty attributes")
                return []
                
            # Validate the attributes
            valid_attributes = []
            for attr in result['attributes']:
                if 'attributeId' in attr and 'attributeValueId' in attr:
                    # Ensure the IDs are integers
                    try:
                        attr['attributeId'] = int(attr['attributeId'])
                        attr['attributeValueId'] = int(attr['attributeValueId'])
                        valid_attributes.append(attr)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid attribute values: {attr}")
            
            logger.info(f"AI processed {len(valid_attributes)} valid attributes")
            return valid_attributes
            
        except Exception as e:
            logger.error(f"AI attribute processing failed: {str(e)}")
            return []