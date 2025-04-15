import json
import os
import logging
import time
from typing import List, Dict, Any, Optional

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
from openai import OpenAI

logger = logging.getLogger(__name__)

class OpenAIHelper:
    """
    Base class for OpenAI operations providing common functionality
    """
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY environment variable not set. OpenAI features will be disabled.")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.model = "gpt-4o"
        self._last_request_time = 0
        self.rate_limit_delay = 1  # Seconds between API calls to avoid rate limiting
        
    def _respect_rate_limit(self):
        """
        Ensure we don't exceed OpenAI's rate limits by adding delay between requests
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last_request)
            
        self._last_request_time = time.time()
    
    def is_available(self) -> bool:
        """Check if OpenAI client is available"""
        return self.client is not None

class OpenAICategoryMatcher(OpenAIHelper):
    """
    Matches product categories using OpenAI's GPT-4o model.
    """
    def __init__(self):
        super().__init__()
        logger.info("Initialized OpenAI category matcher")

    def find_best_category_match(self, search_term: str, product_title: str, categories: List[Dict]) -> Dict:
        """
        Find the best category match for a search term using GPT-4o intelligence
        
        Args:
            search_term: The search term (usually a category name)
            product_title: The product title for additional context
            categories: List of category dictionaries, each containing at least 'name' and 'id'
            
        Returns:
            The best matching category as a dictionary with 'id', 'name', and 'score'
        """
        if not self.client:
            logger.warning("OpenAI client not initialized. Using fallback method.")
            return self._fallback_match(search_term, product_title, categories)
            
        # Ensure we don't exceed rate limits
        self._respect_rate_limit()
        
        # Prepare category data for the API
        category_data = []
        for cat in categories[:60]:  # Limit to 60 categories as requested
            category_data.append({
                "id": cat.get("id"),
                "name": cat.get("name", ""),
            })
        
        # Prepare the prompt
        prompt = self._build_category_matching_prompt(search_term, product_title, category_data)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert e-commerce category matching system. Your task is to identify the most appropriate category for a product."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for more predictable results
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate the response
            if not isinstance(result, dict) or "categoryId" not in result or "confidence" not in result:
                logger.warning(f"Invalid response format from OpenAI: {result}")
                return self._fallback_match(search_term, product_title, categories)
                
            # Get the selected category
            selected_category = next((cat for cat in categories if cat.get("id") == result["categoryId"]), None)
            
            if not selected_category:
                logger.warning(f"Selected category ID {result['categoryId']} not found in provided categories")
                return self._fallback_match(search_term, product_title, categories)
                
            # Return the selected category with confidence score
            return {
                "id": selected_category.get("id"),
                "name": selected_category.get("name", ""),
                "score": result["confidence"]
            }
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return self._fallback_match(search_term, product_title, categories)
    
    def _build_category_matching_prompt(self, search_term: str, product_title: str, categories: List[Dict]) -> str:
        """
        Build a prompt for the OpenAI model to match categories
        """
        categories_json = json.dumps(categories, ensure_ascii=False)
        
        return f"""
        I need to find the most appropriate product category for a product.

        PRODUCT INFORMATION:
        - Category search term: "{search_term}"
        - Product title: "{product_title}"

        AVAILABLE CATEGORIES:
        {categories_json}

        TASK:
        Analyze the product information and choose the most appropriate category from the available categories.
        Consider both the search term and product title in your decision.
        
        For children's clothing products with "Set" or "Takım" in the name, prefer categories like "Takım" or "Set" if available.
        
        RESPONSE FORMAT:
        Respond with a JSON object containing:
        1. The ID of the selected category as "categoryId" (integer)
        2. Your confidence score from 0.0 to 1.0 as "confidence" (float)
        3. A brief explanation of your choice as "explanation" (string)
        
        Example response:
        {{
            "categoryId": 123,
            "confidence": 0.95,
            "explanation": "Selected 'Bebek Takım' because the product is a baby outfit set."
        }}
        """
    
    def _fallback_match(self, search_term: str, product_title: str, categories: List[Dict]) -> Dict:
        """
        Fallback method when OpenAI matching fails
        Simply returns the first category with a placeholder score
        """
        if not categories:
            return {"id": None, "name": "", "score": 0}
            
        return {
            "id": categories[0].get("id"),
            "name": categories[0].get("name", ""),
            "score": 0.5  # Default medium confidence
        }


class OpenAIAttributeMatcher(OpenAIHelper):
    """
    Matches product attributes using OpenAI's GPT-4o model.
    """
    def __init__(self):
        super().__init__()
        logger.info("Initialized OpenAI attribute matcher")
        
    def match_attributes(self, product_title: str, product_description: str, category_attributes: List[Dict]) -> List[Dict]:
        """
        Find the best matching attributes for a product based on its title and description
        
        Args:
            product_title: The product title
            product_description: The product description
            category_attributes: List of category attribute dictionaries with available values
            
        Returns:
            List of attribute dictionaries ready to be used in the Trendyol API
        """
        if not self.client:
            logger.warning("OpenAI client not initialized. Using fallback method.")
            return self._fallback_attribute_matching(category_attributes)
            
        # Ensure we don't exceed rate limits
        self._respect_rate_limit()
        
        # Prepare the prompt
        prompt = self._build_attribute_matching_prompt(product_title, product_description, category_attributes)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert e-commerce product attribute matching system. Your task is to identify the most appropriate attribute values for a product based on its title and description."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Low temperature for more predictable results
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate the response
            if not isinstance(result, dict) or "attributes" not in result:
                logger.warning(f"Invalid response format from OpenAI: {result}")
                return self._fallback_attribute_matching(category_attributes)
                
            attributes = result["attributes"]
            if not isinstance(attributes, list):
                logger.warning(f"Invalid attributes format from OpenAI: {attributes}")
                return self._fallback_attribute_matching(category_attributes)
                
            # Convert to the format expected by Trendyol API
            trendyol_attributes = []
            for attr in attributes:
                if "attributeId" in attr and "attributeValueId" in attr:
                    trendyol_attributes.append({
                        "attributeId": attr["attributeId"],
                        "attributeValueId": attr["attributeValueId"]
                    })
                    
            logger.info(f"OpenAI matched {len(trendyol_attributes)} attributes for product")
            return trendyol_attributes
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API for attribute matching: {str(e)}")
            return self._fallback_attribute_matching(category_attributes)
    
    def _build_attribute_matching_prompt(self, product_title: str, product_description: str, category_attributes: List[Dict]) -> str:
        """
        Build a prompt for the OpenAI model to match attributes
        """
        # Clean and format the product description
        clean_description = product_description or ""
        if len(clean_description) > 2000:
            clean_description = clean_description[:2000] + "..."
        
        # Format only the first 8 category attributes to show available options
        formatted_attributes = []
        attr_count = 0
        for attr in category_attributes:
            # Only include the first 8 attributes
            if attr_count >= 8:
                break
                
            if attr.get('attributeValues'):
                attr_values = []
                for val in attr.get('attributeValues', []):
                    attr_values.append({
                        "id": val.get("id"),
                        "name": val.get("name")
                    })
                
                formatted_attributes.append({
                    "attributeId": attr.get('attribute', {}).get('id'),
                    "attributeName": attr.get('attribute', {}).get('name'),
                    "required": attr.get('required', False),
                    "values": attr_values
                })
                attr_count += 1
        
        attributes_json = json.dumps(formatted_attributes, ensure_ascii=False)
        
        return f"""
        I need to match appropriate attributes for a product based on its title and description.

        PRODUCT INFORMATION:
        - Title: "{product_title}"
        - Description: "{clean_description}"

        AVAILABLE ATTRIBUTES:
        {attributes_json}

        TASK:
        Analyze the product information and select the most appropriate attribute values from the available options.
        Focus on identifying required attributes first, then try to fill in as many optional attributes as possible with confidence.
        
        MATCHING RULES:
        1. Pay close attention to structured information in the description, like "Marka:", "Ürün Tipi:", "Cinsiyet:", etc.
        2. For Gender attribute:
           - If description mentions "Kız Çocuk", select "Kadın / Kız"
           - If description mentions "Erkek Çocuk", select "Erkek"
           - Only select "Unisex" if explicitly stated
        3. For Material/Fabric: 
           - IMPORTANT: For any attribute that contains "kumaş", "malzeme", "fabric" or "material", 
             ALWAYS select "Belirtilmemiş" if it exists as an option
           - If "Belirtilmemiş" doesn't exist, only then look for specific fabric values
           - Look for "Malzeme:" or "Kumaş:" in the description
           - If description mentions "Pamuk" or "Cotton", look for cotton-related options
           - If description mentions "Penye", look for "Penye Kumaş" or similar options
        4. For Pattern/Fit (Kalıp/Kesim/Tip):
           - IMPORTANT: For any attribute that contains "kalıp", "kesim", "fit", "pattern", "form" or "tip", 
             ALWAYS select "Belirtilmemiş" if it exists as an option
           - Only look for specific fit values if "Belirtilmemiş" doesn't exist
        5. For Color (Renk):
           - Look for color information in both title and description
           - Only select a color if you're highly confident, otherwise don't include it
        6. Match values that are directly mentioned in the description or title EXACTLY when possible
        
        If you cannot confidently determine an attribute value, do not include it in your response.
        
        RESPONSE FORMAT:
        Respond with a JSON object containing an "attributes" array with your selected attribute values:
        
        Example response:
        {{
            "attributes": [
                {{
                    "attributeId": 123,
                    "attributeValueId": 456,
                    "explanation": "Selected 'Kırmızı' color based on product description mention of 'red' color."
                }},
                {{
                    "attributeId": 789,
                    "attributeValueId": 101112,
                    "explanation": "Selected 'Pamuk' material from description stating '100% cotton'."
                }}
            ],
            "confidence": 0.95
        }}
        """
    
    def _fallback_attribute_matching(self, category_attributes: List[Dict]) -> List[Dict]:
        """
        Fallback method when OpenAI matching fails
        Try to select the first value for required attributes, but only for the first 8 attributes
        For fabric and pattern attributes, try to select "Belirtilmemiş" if available
        """
        attributes = []
        attr_count = 0
        
        # Özel işleme için anahtar kelimeler
        # Keywords for special processing
        fabric_keywords = ['kumaş', 'fabric', 'material', 'malzeme', 'içerik', 'content']
        pattern_keywords = ['kalıp', 'kesim', 'fit', 'pattern', 'form', 'tip']
        
        for attr in category_attributes:
            # Only include the first 8 attributes
            if attr_count >= 8:
                break
                
            # Get attribute name
            attr_name = attr.get('attribute', {}).get('name', '').lower()
            
            # Check if this is a fabric or pattern attribute
            is_fabric_attribute = any(keyword in attr_name for keyword in fabric_keywords)
            is_pattern_attribute = any(keyword in attr_name for keyword in pattern_keywords)
            
            if (is_fabric_attribute or is_pattern_attribute) and attr.get('attributeValues'):
                # Look for "Belirtilmemiş" option
                belirtilmemis_value = None
                for val in attr['attributeValues']:
                    val_name = val.get('name', '').lower()
                    if val_name in ['belirtilmemiş', 'belirtilmemis', 'bilinmiyor', 'other', 'diğer']:
                        belirtilmemis_value = val
                        break
                
                # If found "Belirtilmemiş", use it
                if belirtilmemis_value:
                    attributes.append({
                        "attributeId": attr.get('attribute', {}).get('id'),
                        "attributeValueId": belirtilmemis_value.get('id')
                    })
                    logger.info(f"Used fallback to select 'Belirtilmemiş' for {attr_name} attribute")
                # If not found but required, use first value
                elif attr.get('required') and attr.get('attributeValues'):
                    first_value = attr['attributeValues'][0]
                    attributes.append({
                        "attributeId": attr.get('attribute', {}).get('id'),
                        "attributeValueId": first_value.get('id')
                    })
                    logger.info(f"Used fallback to select '{first_value.get('name')}' for required attribute '{attr_name}'")
            # Handle regular required attributes
            elif attr.get('required') and attr.get('attributeValues'):
                # Just pick the first value for required attributes
                first_value = attr['attributeValues'][0]
                attributes.append({
                    "attributeId": attr.get('attribute', {}).get('id'),
                    "attributeValueId": first_value.get('id')
                })
                logger.info(f"Used fallback to select '{first_value.get('name')}' for required attribute '{attr_name}'")
                
            attr_count += 1
        
        return attributes