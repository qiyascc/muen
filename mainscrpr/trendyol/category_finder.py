"""
Trendyol Category Finder

This module provides the TrendyolCategoryFinder class that helps with:
1. Finding the best matching Trendyol category for a product
2. Managing required and optional attributes for categories
3. Providing default attributes for certain product types

This is an enhanced version that focuses on:
- Reliability and error handling
- Proper attribute management
- Default attribute values for common categories

The module is designed to work with both basic and advanced search strategies
depending on the available libraries.
"""

import json
import logging
import re
from functools import lru_cache
from typing import Dict, List, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)

# Required attributes that need to be included for all product categories
DEFAULT_REQUIRED_ATTRIBUTES = {
    "Gender": {  # Cinsiyet
        "id": 338,
        "values": {
            "Erkek": 7188,      # Men
            "Kadın": 7189,      # Women
            "Unisex": 7190,     # Unisex
            "Erkek Çocuk": 7191, # Boy
            "Kız Çocuk": 7192   # Girl
        }
    },
    "Origin": {  # Menşei
        "id": 47,
        "values": {
            "Türkiye": 8201,    # Turkey
            "İthal": 346662     # Imported
        }
    },
    "Color": {  # Renk
        "id": 348,
        "values": {
            "Bej": 1011,            # Beige
            "Beyaz": 1012,          # White
            "Bordo": 1013,          # Burgundy
            "Ekru": 1014,           # Ecru
            "Gri": 1015,            # Gray
            "Haki": 1016,           # Khaki
            "Kahverengi": 1017,     # Brown
            "Kırmızı": 1018,        # Red
            "Lacivert": 1019,       # Navy Blue
            "Mavi": 1020,           # Blue
            "Mor": 1021,            # Purple
            "Pembe": 1022,          # Pink
            "Sarı": 1023,           # Yellow
            "Siyah": 1024,          # Black
            "Turuncu": 1025,        # Orange
            "Yeşil": 1026,          # Green
            "Çok Renkli": 1027,     # Multi-color
            "Fuşya": 3839,          # Fuchsia
            "Antrasit": 5060,       # Anthracite
            "Petrol": 6551,         # Petrol
            "Vizon": 3957,          # Mink
            "Gümüş": 9393,          # Silver
            "Taş": 9644,            # Stone
            "Pudra": 12482,         # Powder
            "Turkuaz": 12693,       # Turquoise
            "Altın": 9407,          # Gold
            "İndigo": 12352         # Indigo
        }
    },
    "Size": {  # Beden
        "id": 14,
        "values": {
            "3XS": 254,       # 3XS
            "2XS": 11,        # 2XS
            "XS": 12,         # XS
            "S": 13,          # S
            "M": 14,          # M
            "L": 15,          # L
            "XL": 16,         # XL
            "XXL": 17,        # XXL
            "3XL": 18,        # 3XL
            "4XL": 19,        # 4XL
            "5XL": 20,        # 5XL
            "6XL": 21,        # 6XL
            "7XL": 1174,      # 7XL
            "8XL": 1175,      # 8XL
            "9XL": 1176,      # 9XL
            "STD": 43,        # Standard
            "36": 100,        # 36
            "38": 101,        # 38
            "40": 102,        # 40
            "42": 103,        # 42
            "44": 104,        # 44
            "46": 105,        # 46
            "48": 106,        # 48
            "50": 107,        # 50
            "52": 108,        # 52
            "54": 109,        # 54
            "56": 110,        # 56
            "58": 111,        # 58
            "0-3 Ay": 500,    # 0-3 Months
            "3-6 Ay": 501,    # 3-6 Months
            "6-9 Ay": 502,    # 6-9 Months
            "9-12 Ay": 503,   # 9-12 Months
            "12-18 Ay": 504,  # 12-18 Months
            "18-24 Ay": 505,  # 18-24 Months
            "2-3 Yaş": 506,   # 2-3 Years
            "3-4 Yaş": 507,   # 3-4 Years
            "4-5 Yaş": 508,   # 4-5 Years
            "5-6 Yaş": 509,   # 5-6 Years
            "6-7 Yaş": 510,   # 6-7 Years
            "7-8 Yaş": 511,   # 7-8 Years
            "8-9 Yaş": 512,   # 8-9 Years
            "9-10 Yaş": 513,  # 9-10 Years
            "10-11 Yaş": 514, # 10-11 Years
            "11-12 Yaş": 515, # 11-12 Years
            "12-13 Yaş": 516, # 12-13 Years
            "13-14 Yaş": 517  # 13-14 Years
        }
    },
    "Age Group": {  # Yaş Grubu
        "id": 60,
        "values": {
            "Yetişkin": 902,    # Adult
            "Çocuk": 903,       # Child
            "Bebek": 904,       # Baby
            "Genç": 905         # Teen/Youth
        }
    }
}

# Map LCWaikiki color names to Trendyol color IDs
COLOR_MAPPING = {
    "bej": "Bej",
    "beyaz": "Beyaz",
    "bordo": "Bordo",
    "ekru": "Ekru",
    "gri": "Gri",
    "haki": "Haki",
    "kahve": "Kahverengi",
    "kahverengi": "Kahverengi",
    "kirmizi": "Kırmızı",
    "kırmızı": "Kırmızı",
    "lacivert": "Lacivert",
    "mavi": "Mavi",
    "mor": "Mor",
    "pembe": "Pembe",
    "sarı": "Sarı",
    "sari": "Sarı",
    "siyah": "Siyah",
    "turuncu": "Turuncu",
    "yesil": "Yeşil",
    "yeşil": "Yeşil",
    "çok renkli": "Çok Renkli",
    "renkli": "Çok Renkli",
    "fuşya": "Fuşya",
    "fusya": "Fuşya",
    "antrasit": "Antrasit",
    "petrol": "Petrol",
    "vizon": "Vizon",
    "gumus": "Gümüş",
    "gümüş": "Gümüş",
    "tas": "Taş",
    "taş": "Taş",
    "pudra": "Pudra",
    "turkuaz": "Turkuaz",
    "altin": "Altın",
    "altın": "Altın",
    "indigo": "İndigo",
    # Add more colors as needed
}

# Map LCWaikiki size to Trendyol size
SIZE_MAPPING = {
    "3xs": "3XS",
    "2xs": "2XS",
    "xs": "XS",
    "s": "S",
    "m": "M",
    "l": "L",
    "xl": "XL",
    "xxl": "XXL",
    "3xl": "3XL",
    "4xl": "4XL",
    "5xl": "5XL",
    "6xl": "6XL",
    "7xl": "7XL",
    "8xl": "8XL",
    "9xl": "9XL",
    "std": "STD",
    "36": "36",
    "38": "38",
    "40": "40",
    "42": "42",
    "44": "44",
    "46": "46",
    "48": "48",
    "50": "50",
    "52": "52",
    "54": "54",
    "56": "56",
    "58": "58",
    "0-3 ay": "0-3 Ay",
    "3-6 ay": "3-6 Ay",
    "6-9 ay": "6-9 Ay",
    "9-12 ay": "9-12 Ay",
    "12-18 ay": "12-18 Ay",
    "18-24 ay": "18-24 Ay",
    "2-3 yaş": "2-3 Yaş",
    "3-4 yaş": "3-4 Yaş",
    "4-5 yaş": "4-5 Yaş",
    "5-6 yaş": "5-6 Yaş",
    "6-7 yaş": "6-7 Yaş",
    "7-8 yaş": "7-8 Yaş",
    "8-9 yaş": "8-9 Yaş",
    "9-10 yaş": "9-10 Yaş",
    "10-11 yaş": "10-11 Yaş",
    "11-12 yaş": "11-12 Yaş",
    "12-13 yaş": "12-13 Yaş",
    "13-14 yaş": "13-14 Yaş",
    # Add more sizes as needed
}

# Map product title patterns to Gender
GENDER_PATTERNS = [
    (r'\b(?:erkek|men|man)\b', 'Erkek'),
    (r'\b(?:kadın|kadin|women|woman|bayan)\b', 'Kadın'),
    (r'\b(?:unisex)\b', 'Unisex'),
    (r'\b(?:erkek çocuk|erkek cocuk|boy)\b', 'Erkek Çocuk'),
    (r'\b(?:kız çocuk|kiz cocuk|girl)\b', 'Kız Çocuk'),
]

# Map product title patterns to Age Group
AGE_GROUP_PATTERNS = [
    (r'\b(?:bebek|baby|infant)\b', 'Bebek'),
    (r'\b(?:çocuk|cocuk|child|kid)\b', 'Çocuk'),
    (r'\b(?:genç|genc|teen|youth)\b', 'Genç'),
    (r'\b(?:yetişkin|yetiskin|adult)\b', 'Yetişkin'),
    # Age patterns for children's clothing
    (r'\b(?:0-3|3-6|6-9|9-12|12-18|18-24)\s*(?:ay|month)\b', 'Bebek'),
    (r'\b(?:2-3|3-4|4-5|5-6|6-7|7-8|8-9|9-10|10-11|11-12|12-13|13-14)\s*(?:yaş|yas|year|yil|age)\b', 'Çocuk'),
]

class TrendyolCategoryFinder:
    """
    A class for finding Trendyol categories and managing their attributes.
    This implementation focuses on reliability and performance, using a basic
    search algorithm but with comprehensive fallbacks and defaults.
    """
    
    def __init__(self, api_client):
        """
        Initialize the category finder with an API client
        
        Args:
            api_client: A Trendyol API client with get/post methods
        """
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
    
    @property
    def category_cache(self):
        """Get or load the category cache"""
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self):
        """Fetch all categories from Trendyol API"""
        try:
            response = self.api.categories.get_categories()
            categories = response.get('categories', [])
            logger.info(f"Fetched {len(categories)} top-level categories from Trendyol")
            return categories
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise Exception("Failed to load categories. Please check your API credentials and try again.")
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id):
        """Get attributes for a specific category with caching"""
        if category_id in self._attribute_cache:
            return self._attribute_cache[category_id]
        
        try:
            response = self.api.categories.get_category_attributes(category_id)
            self._attribute_cache[category_id] = response
            required_attributes = [attr.get('name') for attr in response.get('categoryAttributes', []) 
                                if attr.get('required') is True]
            logger.info(f"Category {category_id} has {len(required_attributes)} required attributes: {required_attributes}")
            return response
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            # Return a default set of attributes on failure, so we don't block the entire process
            return {"categoryAttributes": []}
    
    def find_category_id(self, product_title, category_keywords=None):
        """
        Find a suitable category ID for the given product
        
        Args:
            product_title (str): The product title to search for
            category_keywords (list, optional): Additional category keywords to try
            
        Returns:
            int: The category ID of the best matching category
        """
        # Try finding by exact match first (most reliable)
        try:
            categories = self.category_cache
            if not categories:
                logger.error("No categories available")
                return 385  # Default to "Kadın Giyim Ceket" if no categories
            
            # Normalize the product title for better matching
            title_words = self._normalize_text(product_title)
            
            # Collect all search terms
            search_terms = [title_words]
            if category_keywords:
                search_terms.extend([self._normalize_text(kw) for kw in category_keywords])
            
            # Try to find matches for any of the search terms
            all_matches = []
            for term in search_terms:
                matches = self._find_matches(term, categories)
                all_matches.extend(matches)
            
            # If we found any matches, return the first one
            if all_matches:
                best_match = self._select_best_match(all_matches)
                logger.info(f"Found category match: {best_match['name']} (ID: {best_match['id']})")
                return best_match['id']
            
            # Special handling for common product types
            if 'ceket' in title_words:
                logger.info("Defaulting to 'Kadın Giyim Ceket' category")
                return 385  # Kadın Giyim Ceket (Women's Jacket)
            if 'tshirt' in title_words or 'tişört' in title_words or 't-shirt' in title_words:
                logger.info("Defaulting to 'Kadın T-shirt' category")
                return 392  # Kadın T-shirt (Women's T-shirt)
            if 'gömlek' in title_words or 'gomlek' in title_words:
                logger.info("Defaulting to 'Kadın Gömlek' category")
                return 389  # Kadın Gömlek (Women's Shirt)
            if 'pantolon' in title_words or 'şort' in title_words or 'sort' in title_words:
                logger.info("Defaulting to 'Kadın Pantolon' category")
                return 386  # Kadın Pantolon (Women's Pants)
            if 'elbise' in title_words:
                logger.info("Defaulting to 'Kadın Elbise' category")
                return 387  # Kadın Elbise (Women's Dress)
            if 'erkek' in title_words and ('gömlek' in title_words or 'gomlek' in title_words):
                logger.info("Defaulting to 'Erkek Gömlek' category")
                return 544  # Erkek Gömlek (Men's Shirt)
            if 'erkek' in title_words and ('tshirt' in title_words or 'tişört' in title_words or 't-shirt' in title_words):
                logger.info("Defaulting to 'Erkek T-shirt' category")
                return 546  # Erkek T-shirt (Men's T-shirt)
            
            # If all else fails, default to a general clothing category
            logger.warning(f"No category match found for: {product_title}, defaulting to general clothing")
            return 385  # Default to "Kadın Giyim Ceket" if nothing matches
            
        except Exception as e:
            logger.error(f"Error finding category: {str(e)}")
            return 385  # Default to "Kadın Giyim Ceket" on error
    
    def _normalize_text(self, text):
        """Normalize text for better matching"""
        if not text:
            return ""
        # Convert to lowercase and remove special characters
        text = text.lower()
        # Replace Turkish characters
        replacements = {
            'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
            'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c'
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        return text
    
    def _find_matches(self, search_term, categories):
        """Find all possible category matches for the search term"""
        matches = []
        self._find_matches_recursive(search_term, categories, matches)
        return matches
    
    def _find_matches_recursive(self, search_term, categories, matches):
        """Recursively search for category matches"""
        for category in categories:
            category_name = self._normalize_text(category.get('name', ''))
            
            # Look for either exact matches or category name contained in search term
            if category_name in search_term or search_term in category_name:
                # Prioritize leaf categories (those without subcategories)
                if not category.get('subCategories'):
                    matches.append(category)
            
            # Continue searching subcategories
            if category.get('subCategories'):
                self._find_matches_recursive(search_term, category.get('subCategories'), matches)
    
    def _select_best_match(self, matches):
        """Select the best match from the potential matches"""
        # If there's only one match, return it
        if len(matches) == 1:
            return matches[0]
        
        # Otherwise, prefer leaf categories (those without subcategories)
        leaf_matches = [m for m in matches if not m.get('subCategories')]
        if leaf_matches:
            return leaf_matches[0]
        
        # If no leaf categories, return the first match
        return matches[0]
    
    def get_required_attributes(self, category_id, product_title=None, product_color=None, product_size=None):
        """
        Get required attributes for a category, filling in default values when possible
        
        Args:
            category_id (int): The category ID to get attributes for
            product_title (str, optional): The product title, used to infer attributes
            product_color (str, optional): The product color, if known
            product_size (str, optional): The product size, if known
            
        Returns:
            list: List of attribute dictionaries in the format required by Trendyol API
        """
        attributes = []
        
        try:
            # Get the category attributes from the API
            category_attributes_response = self.get_category_attributes(category_id)
            category_attributes = category_attributes_response.get('categoryAttributes', [])
            
            # Log the required attributes
            required_attrs = [attr.get('name') for attr in category_attributes if attr.get('required') is True]
            logger.info(f"Required attributes for category {category_id}: {required_attrs}")
            
            # Process known attributes that might be required
            # Create normalized version of product title for pattern matching
            normalized_title = product_title.lower() if product_title else ""
            
            # 1. Process Gender attribute (almost always required)
            gender_attr = self._get_gender_attribute(normalized_title)
            if gender_attr:
                attributes.append(gender_attr)
            
            # 2. Process Origin attribute (always required)
            attributes.append({
                "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Origin"]["id"],
                "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Origin"]["values"]["Türkiye"]
            })
            
            # 3. Process Color attribute (always required)
            color_attr = self._get_color_attribute(product_color, normalized_title)
            if color_attr:
                attributes.append(color_attr)
            
            # 4. Process Size attribute (always required)
            size_attr = self._get_size_attribute(product_size, normalized_title)
            if size_attr:
                attributes.append(size_attr)
            
            # 5. Process Age Group attribute (often required)
            age_group_attr = self._get_age_group_attribute(normalized_title)
            if age_group_attr:
                attributes.append(age_group_attr)
            
            # Check if we're missing any required attributes that we know about
            required_attr_ids = set()
            for attr in category_attributes:
                if attr.get('required') is True:
                    required_attr_ids.add(attr.get('id'))
            
            # Check if we've handled all the required attributes
            current_attr_ids = {attr['attributeId'] for attr in attributes}
            missing_attr_ids = required_attr_ids - current_attr_ids
            
            if missing_attr_ids:
                logger.warning(f"Missing required attribute IDs: {missing_attr_ids}")
                
                # Try to add missing attributes with default values
                for attr_id in missing_attr_ids:
                    # Find the attribute in the category attributes
                    matching_attr = next((attr for attr in category_attributes if attr.get('id') == attr_id), None)
                    if matching_attr and matching_attr.get('attributeValues'):
                        # Use the first attribute value as default
                        first_value = matching_attr['attributeValues'][0]
                        attributes.append({
                            "attributeId": attr_id,
                            "attributeValueId": first_value.get('id')
                        })
                        logger.info(f"Added default value for attribute {matching_attr.get('name')}: {first_value.get('name')}")
            
            return attributes
            
        except Exception as e:
            logger.error(f"Error getting attributes for category {category_id}: {str(e)}")
            # Return default attributes on error
            return self._get_default_attributes()
    
    def _get_gender_attribute(self, product_title):
        """Determine gender attribute from product title"""
        # Check pattern matches in product title
        for pattern, gender in GENDER_PATTERNS:
            if re.search(pattern, product_title, re.IGNORECASE):
                return {
                    "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Gender"]["id"],
                    "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Gender"]["values"][gender]
                }
        
        # Default to Women's if we can't determine
        logger.info(f"Defaulting to 'Kadın' gender attribute for: {product_title}")
        return {
            "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Gender"]["id"],
            "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Gender"]["values"]["Kadın"]
        }
    
    def _get_color_attribute(self, product_color, product_title):
        """Determine color attribute from product color or title"""
        if product_color:
            # Clean and normalize color name
            color_lower = product_color.lower().strip()
            
            # Check for exact matches in COLOR_MAPPING
            if color_lower in COLOR_MAPPING:
                color_name = COLOR_MAPPING[color_lower]
                return {
                    "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["id"],
                    "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["values"][color_name]
                }
            
            # Check for partial matches
            for key, value in COLOR_MAPPING.items():
                if key in color_lower or color_lower in key:
                    return {
                        "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["id"],
                        "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["values"][value]
                    }
        
        # If no color provided or no match found, try to extract from title
        if product_title:
            for key, value in COLOR_MAPPING.items():
                if key in product_title:
                    return {
                        "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["id"],
                        "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["values"][value]
                    }
        
        # Default to Black if we can't determine
        logger.info(f"Defaulting to 'Siyah' color attribute")
        return {
            "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["id"],
            "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["values"]["Siyah"]
        }
    
    def _get_size_attribute(self, product_size, product_title):
        """Determine size attribute from product size or title"""
        if product_size:
            # Clean and normalize size name
            size_lower = product_size.lower().strip()
            
            # Check for exact matches in SIZE_MAPPING
            if size_lower in SIZE_MAPPING:
                size_name = SIZE_MAPPING[size_lower]
                return {
                    "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["id"],
                    "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["values"][size_name]
                }
            
            # Check for partial matches
            for key, value in SIZE_MAPPING.items():
                if key in size_lower or size_lower in key:
                    return {
                        "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["id"],
                        "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["values"][value]
                    }
        
        # If no size provided or no match found, check for age patterns in title
        for pattern, _ in AGE_GROUP_PATTERNS:
            match = re.search(pattern, product_title, re.IGNORECASE)
            if match:
                if "ay" in match.group(0) or "month" in match.group(0):
                    size_key = next((k for k in SIZE_MAPPING.keys() if k in match.group(0)), None)
                    if size_key:
                        size_name = SIZE_MAPPING[size_key]
                        return {
                            "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["id"],
                            "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["values"][size_name]
                        }
                elif "yaş" in match.group(0) or "yas" in match.group(0) or "year" in match.group(0):
                    size_key = next((k for k in SIZE_MAPPING.keys() if k in match.group(0)), None)
                    if size_key:
                        size_name = SIZE_MAPPING[size_key]
                        return {
                            "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["id"],
                            "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["values"][size_name]
                        }
        
        # Default to M if we can't determine
        logger.info(f"Defaulting to 'M' size attribute")
        return {
            "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["id"],
            "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["values"]["M"]
        }
    
    def _get_age_group_attribute(self, product_title):
        """Determine age group attribute from product title"""
        # Check pattern matches in product title
        for pattern, age_group in AGE_GROUP_PATTERNS:
            if re.search(pattern, product_title, re.IGNORECASE):
                return {
                    "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Age Group"]["id"],
                    "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Age Group"]["values"][age_group]
                }
        
        # Default to Adult if we can't determine
        logger.info(f"Defaulting to 'Yetişkin' age group attribute for: {product_title}")
        return {
            "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Age Group"]["id"],
            "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Age Group"]["values"]["Yetişkin"]
        }
    
    def _get_default_attributes(self):
        """Get a default set of attributes for when all else fails"""
        # Default set of most commonly required attributes
        return [
            # Gender = Women
            {
                "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Gender"]["id"],
                "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Gender"]["values"]["Kadın"]
            },
            # Origin = Turkey 
            {
                "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Origin"]["id"],
                "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Origin"]["values"]["Türkiye"]
            },
            # Color = Black
            {
                "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["id"],
                "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Color"]["values"]["Siyah"]
            },
            # Size = M
            {
                "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["id"],
                "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Size"]["values"]["M"]
            },
            # Age Group = Adult
            {
                "attributeId": DEFAULT_REQUIRED_ATTRIBUTES["Age Group"]["id"],
                "attributeValueId": DEFAULT_REQUIRED_ATTRIBUTES["Age Group"]["values"]["Yetişkin"]
            }
        ]