import json
import os
import logging
import time
from typing import List, Dict, Any, Optional

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
from openai import OpenAI

logger = logging.getLogger(__name__)

class OpenAICategoryMatcher:
    """
    Matches product categories using OpenAI's GPT-4o model.
    """
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY environment variable not set. OpenAI category matching will be disabled.")
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
            return self._fallback_match(search_term, product_title, categories)
            
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
    
    def _respect_rate_limit(self):
        """
        Ensure we don't exceed OpenAI's rate limits by adding delay between requests
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last_request)
            
        self._last_request_time = time.time()