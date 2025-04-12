"""
TrendyolCategoryFinder - A utility class for finding and managing Trendyol categories and attributes
"""
import logging
import re
from functools import lru_cache
from typing import List, Dict, Any, Optional, Tuple

from .api_client import TrendyolAPIClient, get_api_client
from .models import TrendyolProduct

logger = logging.getLogger(__name__)

class TrendyolCategoryFinder:
    """
    Handles category discovery and attribute management for Trendyol products.
    
    This class provides tools to:
    1. Find appropriate categories for products
    2. Get required attributes for categories
    3. Map product data to Trendyol attributes
    """
    
    def __init__(self, api_client=None):
        """
        Initialize the TrendyolCategoryFinder with an API client.
        
        Args:
            api_client: A TrendyolAPIClient instance. If not provided, one will be fetched.
        """
        self.api = api_client if api_client else get_api_client()
        self._category_cache = None
        self._attribute_cache = {}
        self._gender_map = {
            "kadın": 1000, "bayan": 1000, "woman": 1000, "kadın": 1000, "female": 1000,
            "erkek": 1001, "bay": 1001, "man": 1001, "male": 1001,
            "unisex": 1002, "uniseks": 1002,
            "kız çocuk": 1003, "kız": 1003, "girl": 1003,
            "erkek çocuk": 1004, "erkek": 1004, "boy": 1004,
            "unisex çocuk": 1005, "unisex çocuk": 1005,
            "bebek": 1006, "baby": 1006,
        }
        self._color_map = {
            "beyaz": 1001, "white": 1001,
            "ekru": 1012, "ekru": 1012, "cream": 1012, "bej": 1012,
            "sarı": 1004, "yellow": 1004,
            "turuncu": 1005, "orange": 1005,
            "kırmızı": 1006, "red": 1006,
            "pembe": 1007, "pink": 1007,
            "mor": 1008, "purple": 1008,
            "mavi": 1009, "blue": 1009,
            "lacivert": 1010, "navy": 1010, "navy blue": 1010,
            "yeşil": 1011, "green": 1011,
            "gri": 1013, "gray": 1013, "grey": 1013,
            "siyah": 1002, "black": 1002,
            "kahverengi": 1003, "brown": 1003,
            "petrol": 1014, "petrol": 1014, "petrol green": 1014, "petrol mavisi": 1014,
            "altın": 1015, "gold": 1015,
            "gümüş": 1016, "silver": 1016,
            "bordo": 1017, "burgundy": 1017,
            "haki": 1018, "khaki": 1018,
            "füme": 1019, "smoke": 1019,
            "antrasit": 1020, "anthracite": 1020,
            "bakır": 1021, "copper": 1021,
            "bronz": 1022, "bronze": 1022,
            "vizon": 1023, "mink": 1023, "taupe": 1023,
            "turkuaz": 1024, "turquoise": 1024,
            "indigo": 1025, "indigo": 1025,
            "lila": 1026, "lilac": 1026,
            "mercan": 1027, "coral": 1027,
            "mint": 1028, "mint": 1028,
            "pudra": 1029, "powder": 1029,
            "şampanya": 1030, "champagne": 1030,
            "kiremit": 1031, "tile": 1031, "terra cotta": 1031, "terracotta": 1031,
            "taş": 1032, "stone": 1032,
            "fuşya": 1033, "fuchsia": 1033,
            "hardal": 1034, "mustard": 1034,
            "açık mavi": 1035, "light blue": 1035,
            "açık pembe": 1036, "light pink": 1036,
            "açık yeşil": 1037, "light green": 1037,
            "koyu mavi": 1038, "dark blue": 1038,
            "koyu yeşil": 1039, "dark green": 1039,
            "koyu gri": 1040, "dark grey": 1040, "dark gray": 1040,
            "latte": 1041, "latte": 1041,
            "aqua": 1042, "aqua": 1042,
            "boncuk mavisi": 1043, "bead blue": 1043, "periwinkle": 1043,
            "şeftali": 1044, "peach": 1044,
            "kot": 1045, "denim": 1045, "jean": 1045,
            "leopar": 1046, "leopard": 1046,
            "karışık": 1047, "mixed": 1047, "multi color": 1047, "çok renkli": 1047,
            "yavruağzı": 1048, "salmon": 1048, "somon": 1048,
            "bej": 1049, "beige": 1049,
            "taba": 1050, "tan": 1050,
            "kamel": 1051, "camel": 1051
        }
        self._size_map = {
            # Genel bedenler
            "xs": 2001, "xs": 2001, "extra small": 2001,
            "s": 2002, "small": 2002,
            "m": 2003, "medium": 2003,
            "l": 2004, "large": 2004,
            "xl": 2005, "extra large": 2005,
            "xxl": 2006, "2xl": 2006, "xx large": 2006, "2x large": 2006,
            "3xl": 2007, "xxxl": 2007, "xxx large": 2007, "3x large": 2007,
            "4xl": 2008, "xxxxl": 2008, "xxxx large": 2008, "4x large": 2008,
            
            # Çocuk yaş bedenler
            "1-2 yaş": 3001, "1-2": 3001, "2 yaş": 3001,
            "3-4 yaş": 3002, "3-4": 3002, "4 yaş": 3002,
            "5-6 yaş": 3003, "5-6": 3003, "6 yaş": 3003,
            "7-8 yaş": 3004, "7-8": 3004, "8 yaş": 3004,
            "9-10 yaş": 3005, "9-10": 3005, "10 yaş": 3005,
            "11-12 yaş": 3006, "11-12": 3006, "12 yaş": 3006,
            "13-14 yaş": 3007, "13-14": 3007, "14 yaş": 3007,
            
            # Ayakkabı numaraları
            "35": 4001, "36": 4002, "37": 4003, "38": 4004, "39": 4005,
            "40": 4006, "41": 4007, "42": 4008, "43": 4009, "44": 4010,
            "45": 4011, "46": 4012,
            
            # Bebek bedenleri
            "0-3 ay": 5001, "0-3": 5001, "3 ay": 5001,
            "3-6 ay": 5002, "3-6": 5002, "6 ay": 5002,
            "6-9 ay": 5003, "6-9": 5003, "9 ay": 5003,
            "9-12 ay": 5004, "9-12": 5004, "12 ay": 5004,
            "12-18 ay": 5005, "12-18": 5005, "18 ay": 5005,
            "18-24 ay": 5006, "18-24": 5006, "24 ay": 5006,
        }
        
        # Yaş grubu
        self._age_group_map = {
            "yetişkin": 1, "adult": 1, "büyük": 1,
            "çocuk": 2, "child": 2, "kid": 2,
            "bebek": 3, "baby": 3, "infant": 3
        }
        
        # Menşei
        self._origin_map = {
            "türkiye": 1, "turkey": 1,
            "çin": 2, "china": 2,
            "hindistan": 3, "india": 3,
            "bangladeş": 4, "bangladesh": 4,
            "vietnam": 5, "vietnam": 5,
            "pakistan": 6, "pakistan": 6,
            "italya": 7, "italy": 7,
            "diğer": 8, "other": 8
        }
    
    @property
    def category_cache(self):
        """Get all categories with lazy loading"""
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self):
        """Fetch all categories from Trendyol API"""
        try:
            if self.api is None:
                logger.error("API client is None, cannot fetch categories")
                return []
                
            response = self.api.categories.get_categories()
            if isinstance(response, dict) and 'categories' in response:
                return response.get('categories', [])
            else:
                logger.error(f"Invalid response format from categories API: {response}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            return []
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id):
        """Get attributes for a specific category with caching"""
        if category_id in self._attribute_cache:
            return self._attribute_cache[category_id]
            
        try:
            if self.api is None:
                logger.error("API client is None, cannot fetch category attributes")
                return None
                
            response = self.api.categories.get_category_attributes(category_id)
            self._attribute_cache[category_id] = response
            return response
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            return None
    
    def extract_color_from_title(self, title):
        """Extract color from product title"""
        title_lower = title.lower()
        
        # Try direct matching with color names
        for color_name in self._color_map.keys():
            if color_name.lower() in title_lower:
                return color_name.lower()
                
        # Patterns for common color locations in titles
        color_patterns = [
            r'(?:renk|color)[:\s]*(\w+)',
            r'(\w+)[\s]*(?:renk|color)',
            r'-\s*(\w+)\s*(?:renk|color)',
        ]
        
        for pattern in color_patterns:
            match = re.search(pattern, title_lower)
            if match:
                color = match.group(1).strip()
                if color in self._color_map:
                    return color
        
        # Default to black if no color found
        return "siyah"
    
    def extract_gender_from_title(self, title):
        """Extract gender from product title"""
        title_lower = title.lower()
        
        # Check for gender keywords
        gender_keywords = {
            "kadın": "kadın", "bayan": "kadın", "woman": "kadın", "female": "kadın",
            "erkek": "erkek", "bay": "erkek", "man": "erkek", "male": "erkek",
            "uniseks": "unisex", "unisex": "unisex", 
            "kız çocuk": "kız çocuk", "kız": "kız çocuk", "girl": "kız çocuk",
            "erkek çocuk": "erkek çocuk", "boy": "erkek çocuk",
            "bebek": "bebek", "baby": "bebek"
        }
        
        for keyword, gender in gender_keywords.items():
            if keyword in title_lower:
                return gender
                
        # If no gender found, check word patterns
        if "çocuk" in title_lower:
            if "kız" in title_lower:
                return "kız çocuk"
            elif "erkek" in title_lower:
                return "erkek çocuk"
            else:
                return "unisex çocuk"
        
        # Default if nothing is found
        return "unisex"
    
    def extract_size_from_name(self, title, size_name=None):
        """Extract size from product title or size name"""
        if size_name:
            size_lower = size_name.lower()
            # Direct size match
            for size, code in self._size_map.items():
                if size.lower() == size_lower:
                    return size.lower()
            
            # Try with regex patterns
            size_patterns = [
                r'(\d+[-/]?\d*\s*(?:ay|yaş|yrs|years|mos|months|month)?)',
                r'(xs|s|m|l|xl|xxl|xxxl|\d+xl)',
            ]
            
            for pattern in size_patterns:
                match = re.search(pattern, size_lower)
                if match:
                    extracted = match.group(1).strip().lower()
                    # Check if this is a valid size
                    for size_key in self._size_map.keys():
                        if extracted in size_key or size_key in extracted:
                            return size_key
            
            # Return the original if no match
            return size_name.lower()
        
        # Extract from title if no specific size name
        title_lower = title.lower()
        for size in self._size_map.keys():
            if size.lower() in title_lower:
                return size.lower()
                
        # Default to medium if nothing found
        return "m"
    
    def extract_age_group_from_title(self, title):
        """Extract age group from product title"""
        title_lower = title.lower()
        
        if any(term in title_lower for term in ["bebek", "baby", "infant", "0-3", "3-6", "6-9", "9-12", "12-18", "18-24"]):
            return "bebek"
        elif any(term in title_lower for term in ["çocuk", "kid", "child", "yaş", "yrs", "years", "boy", "girl", "kız", "erkek çocuk"]):
            return "çocuk"
        else:
            return "yetişkin"
    
    def prepare_required_attributes(self, product, category_id):
        """
        Prepare the required attributes for a given product and category.
        
        Args:
            product: The TrendyolProduct object
            category_id: The Trendyol category ID
            
        Returns:
            List of attribute dictionaries with attributeId and attributeValueId
        """
        attributes = []
        
        # Get category attributes to determine required fields
        category_attrs = self.get_category_attributes(category_id)
        required_attrs = []
        
        if category_attrs:
            # Check for categoryAttributes or just attributes in the response
            if 'categoryAttributes' in category_attrs:
                required_attrs = category_attrs.get('categoryAttributes', [])
            else:
                required_attrs = category_attrs.get('attributes', [])
        
        # Mapping for common required attributes
        # Default values if extraction fails
        color = self.extract_color_from_title(product.title)
        gender = self.extract_gender_from_title(product.title)
        size = self.extract_size_from_name(product.title, product.size)
        age_group = self.extract_age_group_from_title(product.title)
        
        # Map standard required attributes
        attribute_mapping = {
            # Gender - Usually attribute ID 338
            "cinsiyet": {"id": 338, "value_id": self._gender_map.get(gender, 1000)},
            
            # Color - Usually attribute ID 348
            "renk": {"id": 348, "value_id": self._color_map.get(color, 1002)},
            
            # Size - Usually attribute ID 349 or 350
            "beden": {"id": 349, "value_id": self._size_map.get(size, 2003)},
            
            # Age Group - Usually attribute ID 352
            "yaş grubu": {"id": 352, "value_id": self._age_group_map.get(age_group, 1)},
            
            # Origin - Usually attribute ID 359
            "menşei": {"id": 359, "value_id": self._origin_map.get("türkiye", 1)}
        }
        
        # Check which attributes are required and add them
        if required_attrs:
            for attr in required_attrs:
                attr_name = attr.get('name', '').lower()
                attr_id = attr.get('id')
                
                if attr_name in attribute_mapping:
                    # Use our mapping for known attributes
                    attributes.append({
                        "attributeId": attr_id,
                        "attributeValueId": attribute_mapping[attr_name]["value_id"]
                    })
                else:
                    # For other attributes, use a default if available
                    if attr.get('allowCustom', False) and attr.get('required', False):
                        attributes.append({
                            "attributeId": attr_id,
                            "customAttributeValue": "Standart"
                        })
        else:
            # If we couldn't get category attributes, add standard ones
            attributes = [
                {"attributeId": 338, "attributeValueId": self._gender_map.get(gender, 1000)},
                {"attributeId": 348, "attributeValueId": self._color_map.get(color, 1002)},
                {"attributeId": 349, "attributeValueId": self._size_map.get(size, 2003)},
                {"attributeId": 352, "attributeValueId": self._age_group_map.get(age_group, 1)},
                {"attributeId": 359, "attributeValueId": 1}  # Türkiye as default origin
            ]
        
        logger.info(f"Prepared attributes for product {product.id} in category {category_id}: {attributes}")
        return attributes
    
    def find_best_category_match(self, product_title, product_description=None):
        """
        Find the best category match for a product based on its title and description.
        
        Args:
            product_title: The product title
            product_description: Optional product description
            
        Returns:
            The best matching category ID, or 1007 (default clothing category) if no match found
        """
        if not self.category_cache:
            logger.warning("Category cache is empty, using default category")
            return 1007  # Default clothing category
        
        # Keywords for common categories
        category_keywords = {
            "gömlek": [60, 385],  # Erkek Gömlek, Kadın Gömlek
            "elbise": [503],  # Kadın Elbise
            "tişört": [378, 53],  # Kadın Tişört, Erkek Tişört
            "t-shirt": [378, 53],  # Kadın Tişört, Erkek Tişört
            "pantolon": [386, 61],  # Kadın Pantolon, Erkek Pantolon
            "jean": [386, 61],  # Kadın Pantolon, Erkek Pantolon
            "sweatshirt": [381, 56],  # Kadın Sweatshirt, Erkek Sweatshirt
            "kazak": [379, 54],  # Kadın Kazak, Erkek Kazak
            "hırka": [380, 55],  # Kadın Hırka, Erkek Hırka
            "ceket": [382, 57],  # Kadın Ceket, Erkek Ceket
            "mont": [383, 58],  # Kadın Mont, Erkek Mont
            "şort": [388, 63],  # Kadın Şort, Erkek Şort
            "pijama": [391, 66],  # Kadın Pijama, Erkek Pijama
            "çorap": [396, 71],  # Kadın Çorap, Erkek Çorap
            "ayakkabı": [253, 159, 261],  # Kadın Ayakkabı, Erkek Ayakkabı
            "çanta": [411],  # Kadın Çanta
            "takı": [2209],  # Takı
            "aksesuar": [1172, 2209, 411]  # Aksesuar genel (takı, çanta, vb)
        }
        
        # Check gender in title to refine category selection
        gender = self.extract_gender_from_title(product_title)
        is_woman = gender in ["kadın", "bayan"]
        is_man = gender in ["erkek", "bay"] and "çocuk" not in gender
        is_child = "çocuk" in gender or gender in ["kız çocuk", "erkek çocuk"]
        is_baby = gender == "bebek"
        
        title_lower = product_title.lower()
        
        # Match by gender and product type
        for keyword, categories in category_keywords.items():
            if keyword in title_lower:
                # Select category based on gender
                if len(categories) > 1:
                    if is_woman and categories[0]:
                        return categories[0]
                    elif is_man and categories[1]:
                        return categories[1]
                    elif is_child and len(categories) > 2 and categories[2]:
                        return categories[2]
                return categories[0]  # Return first category if no gender match or only one category
        
        # Fallback to broader categories
        if is_woman:
            return 41  # Kadın Giyim
        elif is_man:
            return 37  # Erkek Giyim
        elif is_child:
            if "kız" in gender:
                return 342  # Kız Çocuk Giyim
            else:
                return 338  # Erkek Çocuk Giyim
        elif is_baby:
            return 462  # Bebek Giyim
        
        # Ultimate fallback
        return 1007  # Genel giyim kategorisi

# Helper function to get a singleton instance of the category finder
_category_finder_instance = None

def get_category_finder():
    """Get or create a TrendyolCategoryFinder instance"""
    global _category_finder_instance
    if _category_finder_instance is None:
        api_client = get_api_client()
        if api_client:
            _category_finder_instance = TrendyolCategoryFinder(api_client)
    return _category_finder_instance