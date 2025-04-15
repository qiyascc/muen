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
    Helper class for using OpenAI's GPT-4o model for different tasks.
    """
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY environment variable not set. OpenAI functions will be disabled.")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.model = "gpt-4o"
        self._last_request_time = 0
        self.rate_limit_delay = 1  # Seconds between API calls to avoid rate limiting

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
            return self._fallback_category_match(search_term, product_title, categories)
            
        # Ensure we don't exceed rate limits
        self._respect_rate_limit()
        
        # Prepare category data for the API
        category_data = []
        for cat in categories[:30]:  # Limit to 30 categories as requested
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
                return self._fallback_category_match(search_term, product_title, categories)
                
            # Get the selected category
            selected_category = next((cat for cat in categories if cat.get("id") == result["categoryId"]), None)
            
            if not selected_category:
                logger.warning(f"Selected category ID {result['categoryId']} not found in provided categories")
                return self._fallback_category_match(search_term, product_title, categories)
                
            # Return the selected category with confidence score
            return {
                "id": selected_category.get("id"),
                "name": selected_category.get("name", ""),
                "score": result["confidence"]
            }
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API for category matching: {str(e)}")
            return self._fallback_category_match(search_term, product_title, categories)
    
    def match_product_attributes(self, product_title: str, product_description: str, 
                             category_attributes: List[Dict]) -> List[Dict]:
        """
        Match product attributes using GPT-4o intelligence
        
        Args:
            product_title: The product title
            product_description: The product description
            category_attributes: List of category attributes from Trendyol API
            
        Returns:
            List of attribute dictionaries with matched values
        """
        if not self.client:
            logger.warning("OpenAI client not initialized. Using fallback method for attribute matching.")
            return []
            
        # Ensure we don't exceed rate limits
        self._respect_rate_limit()
        
        # Clean product description
        clean_description = ""
        if product_description:
            # Remove HTML tags
            import re
            clean_description = re.sub(r'<[^>]+>', ' ', product_description)
            # Remove extra spaces
            clean_description = re.sub(r'\s+', ' ', clean_description).strip()
        
        # Create a simplified version of attributes for the prompt
        simplified_attributes = []
        for attr in category_attributes:
            if 'attribute' not in attr:
                continue
                
            attribute_values = []
            if 'attributeValues' in attr and attr['attributeValues']:
                attribute_values = [val['name'] for val in attr['attributeValues']]
                
            simplified_attributes.append({
                "id": attr['attribute']['id'],
                "name": attr['attribute']['name'],
                "required": attr.get('required', False),
                "allowCustom": attr.get('allowCustom', False),
                "values": attribute_values
            })
        
        # Build the prompt
        prompt = self._build_attribute_matching_prompt(
            product_title, 
            clean_description, 
            simplified_attributes
        )
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert e-commerce product attribute analyzer. Your task is to extract and match product attributes from product information."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for more accurate results
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate the response
            if not isinstance(result, dict) or "attributes" not in result:
                logger.warning(f"Invalid response format from OpenAI for attribute matching: {result}")
                return []
                
            # Convert OpenAI results to the expected format
            formatted_attributes = []
            for attr in result["attributes"]:
                if "attributeId" not in attr:
                    continue
                    
                attribute_entry = {
                    "attributeId": attr["attributeId"],
                    "attributeName": attr["attributeName"]
                }
                
                # Add either attributeValueId or customAttributeValue
                if "attributeValueId" in attr:
                    attribute_entry["attributeValueId"] = attr["attributeValueId"]
                    attribute_entry["attributeValue"] = attr["attributeValue"]
                elif "customAttributeValue" in attr:
                    attribute_entry["customAttributeValue"] = attr["customAttributeValue"]
                else:
                    # Skip attributes without a value
                    continue
                    
                formatted_attributes.append(attribute_entry)
                
            # Check if all required attributes are present
            required_attrs = [a for a in simplified_attributes if a.get('required', False)]
            required_attr_ids = set(a['id'] for a in required_attrs)
            matched_attr_ids = set(a['attributeId'] for a in formatted_attributes)
            
            missing_required_ids = required_attr_ids - matched_attr_ids
            if missing_required_ids:
                missing_attrs = [a for a in required_attrs if a['id'] in missing_required_ids]
                logger.warning(f"Missing required attributes after OpenAI matching: {missing_attrs}")
                
                # Try to add defaults for missing required attributes
                for missing_attr in missing_attrs:
                    # Find original attribute data
                    orig_attr = next((a for a in category_attributes 
                                    if 'attribute' in a and a['attribute']['id'] == missing_attr['id']), None)
                    
                    if not orig_attr:
                        continue
                        
                    # Add default attribute
                    attr_entry = {
                        "attributeId": missing_attr['id'],
                        "attributeName": missing_attr['name'],
                    }
                    
                    # If it has values, use the first one
                    if orig_attr.get('attributeValues') and len(orig_attr['attributeValues']) > 0:
                        attr_entry["attributeValueId"] = orig_attr['attributeValues'][0]['id']
                        attr_entry["attributeValue"] = orig_attr['attributeValues'][0]['name']
                    # If custom values are allowed, use a default
                    elif orig_attr.get('allowCustom'):
                        attr_entry["customAttributeValue"] = f"Sample {missing_attr['name']}"
                    
                    formatted_attributes.append(attr_entry)
            
            return formatted_attributes
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API for attribute matching: {str(e)}")
            return []
    
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
    
    def _build_attribute_matching_prompt(self, product_title: str, product_description: str, 
                                     category_attributes: List[Dict]) -> str:
        """
        Build a prompt for the OpenAI model to match product attributes
        """
        attributes_json = json.dumps(category_attributes, ensure_ascii=False)
        
        return f"""
        I need to match product attributes for a Trendyol product listing.

        PRODUCT INFORMATION:
        - Title: "{product_title}"
        - Description: "{product_description}"

        AVAILABLE ATTRIBUTES:
        {attributes_json}

        TASK:
        Analyze the product information and match appropriate attribute values from the available attributes.
        For each attribute, either:
        1. Select the most appropriate value from the "values" array if there's a good match
        2. OR provide a custom value if "allowCustom" is true and no good match exists

        Pay special attention to the "required" attributes, as they must be included.

        For required color ("Renk") attributes, try to extract the color from the title or description.
        Common colors in Turkish include: "Siyah" (Black), "Beyaz" (White), "Kırmızı" (Red), 
        "Mavi" (Blue), "Yeşil" (Green), "Sarı" (Yellow), "Turuncu" (Orange), "Mor" (Purple),
        "Pembe" (Pink), "Gri" (Gray), "Kahverengi" (Brown), "Bej" (Beige), "Lacivert" (Navy Blue).

        RESPONSE FORMAT:
        Respond with a JSON object containing an "attributes" array with objects for each attribute:
        {{
          "attributes": [
            {{
              "attributeId": <id of the attribute>,
              "attributeName": <name of the attribute>,
              "attributeValueId": <id of the selected attribute value>,  // Use if selecting from available values
              "attributeValue": <name of the selected attribute value>   // Use if selecting from available values
            }},
            {{
              "attributeId": <id of attribute with custom value>,
              "attributeName": <name of attribute with custom value>,
              "customAttributeValue": <the custom value string>  // Use if providing a custom value
            }}
          ]
        }}

        Include values for ALL required attributes. If you're unsure about a non-required attribute, omit it from the results.
        """
    
    def _fallback_category_match(self, search_term: str, product_title: str, categories: List[Dict]) -> Dict:
        """
        Fallback method when OpenAI category matching fails
        Simply returns the first category with a placeholder score
        """
        if not categories:
            return {"id": None, "name": "", "score": 0}
            
        return {
            "id": categories[0].get("id"),
            "name": categories[0].get("name", ""),
            "score": 0.5  # Default medium confidence
        }
    
    def _respect_rate_limit(self):
        """
        Ensure we don't exceed OpenAI's rate limits by adding delay between requests
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last_request)
            
        self._last_request_time = time.time()

# Maintain backwards compatibility with existing code
OpenAICategoryMatcher = OpenAIHelper