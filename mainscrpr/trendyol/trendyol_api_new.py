import requests
import json
import uuid
import logging
from urllib.parse import quote
from django.utils import timezone
from collections import defaultdict
from functools import lru_cache
import time

from .models import TrendyolAPIConfig, TrendyolProduct

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

class TrendyolAPI:
    """Base class for Trendyol API operations with retry mechanism"""
    
    def __init__(self, config: TrendyolAPIConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {self.config.api_key}",
            "User-Agent": f"{self.config.seller_id} - SelfIntegration",
            "Content-Type": "application/json"
        })
    
    def _make_request(self, method, endpoint, **kwargs):
        """Generic request method with retry logic"""
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                time.sleep(RETRY_DELAY * (attempt + 1))
    
    def get(self, endpoint, params=None):
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint, data):
        return self._make_request('POST', endpoint, json=data)


class TrendyolCategoryFinder:
    """Handles category discovery and attribute management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
        
        # Try to import sentence-transformers for advanced semantic similarity
        try:
            from sentence_transformers import SentenceTransformer, util
            from PyMultiDictionary import MultiDictionary
            self.model = SentenceTransformer('emrecan/bert-base-turkish-cased-mean-nli-stsb-tr')
            self.dictionary = MultiDictionary()
            self.advanced_search_available = True
            logger.info("Advanced semantic search enabled with sentence-transformers")
        except ImportError:
            self.model = None
            self.dictionary = None
            self.advanced_search_available = False
            logger.warning("sentence-transformers not available, using basic search")
            import difflib  # Fallback to difflib for basic string matching
    
    @property
    def category_cache(self):
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self):
        """Fetch all categories from Trendyol API"""
        try:
            data = self.api.get("product/product-categories")
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise Exception("Failed to load categories. Please check your API credentials and try again.")
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id):
        """Get attributes for a specific category with caching"""
        try:
            data = self.api.get(f"product/product-categories/{category_id}/attributes")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch attributes for category {category_id}: {str(e)}")
            raise Exception(f"Failed to load attributes for category {category_id}")
    
    def find_best_category(self, search_term):
        """Find the most relevant category for a given search term"""
        try:
            categories = self.category_cache
            if not categories:
                raise ValueError("Empty category list received from API")
            
            if self.advanced_search_available and self.model is not None:
                return self._find_best_category_semantic(search_term, categories)
            else:
                # Fallback to basic string matching
                all_matches = self._find_all_possible_matches(search_term, categories)
                
                if exact_match := self._find_exact_match(search_term, all_matches):
                    return exact_match
                
                if all_matches:
                    return self._select_best_match_basic(search_term, all_matches)['id']
                
                leaf_categories = self._get_all_leaf_categories(categories)
                if leaf_categories:
                    return self._select_best_match_basic(search_term, leaf_categories)['id']
                
                suggestions = self._get_category_suggestions_basic(search_term, categories)
                raise ValueError(f"No exact match found. Closest categories:\n{suggestions}")
            
        except Exception as e:
            logger.error(f"Category search failed for '{search_term}': {str(e)}")
            raise
    
    def _find_best_category_semantic(self, search_term, categories):
        """Find best category using semantic similarity with sentence-transformers"""
        try:
            from sentence_transformers import util
            
            # Get expanded search terms with synonyms if possible
            search_terms = {search_term.lower()}
            try:
                if self.dictionary:
                    synonyms = self.dictionary.synonym('tr', search_term.lower())
                    search_terms.update(synonyms[:5])  # Limit to 5 synonyms to avoid noise
            except Exception as e:
                logger.debug(f"Could not expand search terms: {str(e)}")
            
            # Collect all leaf categories
            leaf_categories = []
            self._collect_leaf_categories(categories, leaf_categories)
            
            # Find matches using all search terms
            matches = []
            for term in search_terms:
                for cat in leaf_categories:
                    # Compute semantic similarity
                    search_embedding = self.model.encode(term, convert_to_tensor=True)
                    cat_embedding = self.model.encode(cat['name'], convert_to_tensor=True)
                    similarity = util.cos_sim(search_embedding, cat_embedding).item()
                    cat['similarity'] = similarity
                    matches.append(cat.copy())
            
            # Sort by similarity and select best match
            if matches:
                matches_sorted = sorted(matches, key=lambda x: x['similarity'], reverse=True)
                
                # Log top matches for debugging
                logger.info(f"Top matches for '{search_term}':")
                for i, m in enumerate(matches_sorted[:3], 1):
                    logger.info(f"{i}. {m['name']} (Score: {m['similarity']:.4f}, ID: {m['id']})")
                
                return matches_sorted[0]['id']
            else:
                # If semantic search fails, fall back to basic search
                logger.warning("Semantic search found no matches, falling back to basic search")
                all_matches = self._find_all_possible_matches(search_term, categories)
                if not all_matches:
                    raise ValueError(f"No matches found for: {search_term}")
                return self._select_best_match_basic(search_term, all_matches)['id']
                
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            # Fall back to basic search
            all_matches = self._find_all_possible_matches(search_term, categories)
            if not all_matches:
                raise ValueError(f"No matches found for: {search_term}")
            return self._select_best_match_basic(search_term, all_matches)['id']
    
    def _find_all_possible_matches(self, search_term, categories):
        """Find all possible matches using basic string matching"""
        matches = []
        self._find_matches_for_term(search_term.lower(), categories, matches)
        
        # Deduplicate while preserving order
        seen_ids = set()
        return [m for m in matches if not (m['id'] in seen_ids or seen_ids.add(m['id']))]
    
    def _find_matches_for_term(self, term, categories, matches):
        """Recursively find matches in category tree"""
        term_lower = term.lower()
        
        for cat in categories:
            cat_name_lower = cat['name'].lower()
            
            if term_lower == cat_name_lower or term_lower in cat_name_lower:
                if not cat.get('subCategories'):
                    matches.append(cat)
            
            if cat.get('subCategories'):
                self._find_matches_for_term(term, cat['subCategories'], matches)
    
    def _find_exact_match(self, search_term, matches):
        """Check for exact name matches"""
        search_term_lower = search_term.lower()
        for match in matches:
            if search_term_lower == match['name'].lower():
                return match['id']
        return None
    
    def _select_best_match_basic(self, search_term, candidates):
        """Select best match using basic string similarity"""
        import difflib
        
        for candidate in candidates:
            candidate['similarity'] = difflib.SequenceMatcher(
                None, search_term.lower(), candidate['name'].lower()
            ).ratio()
        
        candidates_sorted = sorted(candidates, key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Top 3 matches for '{search_term}':")
        for i, candidate in enumerate(candidates_sorted[:3], 1):
            logger.info(f"{i}. {candidate['name']} (Similarity: {candidate['similarity']:.2f})")
        
        return candidates_sorted[0]
    
    def _get_all_leaf_categories(self, categories):
        """Get all leaf categories (categories without children)"""
        leaf_categories = []
        self._collect_leaf_categories(categories, leaf_categories)
        return leaf_categories
    
    def _collect_leaf_categories(self, categories, result):
        """Recursively collect leaf categories"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def _get_category_suggestions_basic(self, search_term, categories, top_n=3):
        """Generate user-friendly suggestions using basic string matching"""
        import difflib
        
        leaf_categories = self._get_all_leaf_categories(categories)
        
        for cat in leaf_categories:
            cat['similarity'] = difflib.SequenceMatcher(
                None, search_term.lower(), cat['name'].lower()
            ).ratio()
        
        sorted_cats = sorted(leaf_categories, key=lambda x: x['similarity'], reverse=True)
        
        suggestions = []
        for i, cat in enumerate(sorted_cats[:top_n], 1):
            suggestions.append(f"{i}. {cat['name']} (Similarity: {cat['similarity']:.2f}, ID: {cat['id']})")
        
        return "\n".join(suggestions)
        
    def get_required_attributes(self, category_id):
        """Get required attributes for a specific category"""
        try:
            attributes = []
            category_attrs = self.get_category_attributes(category_id)
            
            # Process all category attributes
            for attr in category_attrs.get('categoryAttributes', []):
                # Skip attributes with missing IDs
                if not attr['attribute'].get('id'):
                    continue
                    
                # Skip attributes with empty values when custom values are not allowed
                if not attr.get('attributeValues') and not attr.get('allowCustom'):
                    continue
                    
                attribute_id = attr['attribute']['id']
                
                # Get a suitable value ID if available
                attribute_value_id = None
                
                # If there are attribute values, use the first one
                if attr.get('attributeValues') and len(attr['attributeValues']) > 0:
                    attribute_value_id = attr['attributeValues'][0]['id']
                
                # If we have a valid attribute ID and value ID, add to the list
                if attribute_id and attribute_value_id:
                    attributes.append({
                        "attributeId": attribute_id,
                        "attributeValueId": attribute_value_id
                    })
            
            return attributes
                
        except Exception as e:
            logger.error(f"Error getting required attributes: {str(e)}")
            return []


class TrendyolProductManager:
    """Handles product creation and management"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.category_finder = TrendyolCategoryFinder(api_client)
    
    def get_brand_id(self, brand_name):
        """Find brand ID by name"""
        encoded_name = quote(brand_name)
        try:
            brands = self.api.get(f"product/brands/by-name?name={encoded_name}")
            if isinstance(brands, list) and brands:
                return brands[0]['id']
            raise ValueError(f"Brand not found: {brand_name}")
        except Exception as e:
            logger.error(f"Brand search failed for '{brand_name}': {str(e)}")
            raise
    
    def create_product(self, product_data):
        """Create a new product on Trendyol"""
        try:
            # Find category ID using our enhanced category finder
            category_id = self.category_finder.find_best_category(product_data.category_name)
            
            # Get brand ID
            brand_id = self.get_brand_id(product_data.brand_name)
            
            # Get attributes from the API for this category
            attributes = self.category_finder.get_required_attributes(category_id)
            
            # Build the complete payload
            payload = self._build_product_payload(product_data, category_id, brand_id, attributes)
            
            logger.info(f"Submitting product creation request for {product_data.title}")
            response = self.api.post(f"product/sellers/{self.api.config.seller_id}/products", payload)
            
            return response.get('batchRequestId')
        except Exception as e:
            logger.error(f"Product creation failed: {str(e)}")
            raise
    
    def check_batch_status(self, batch_id):
        """Check the status of a batch operation"""
        try:
            return self.api.get(f"product/sellers/{self.api.config.seller_id}/products/batch-requests/{batch_id}")
        except Exception as e:
            logger.error(f"Failed to check batch status: {str(e)}")
            raise
    
    def _build_product_payload(self, product, category_id, brand_id, attributes):
        """Construct the complete product payload"""
        # Normalize title and truncate if too long
        normalized_title = " ".join(product.title.split()) if product.title else ""
        title = normalized_title[:100] if normalized_title and len(normalized_title) > 100 else normalized_title
        
        # Set up image URLs
        image_urls = []
        if product.image_url:
            image_urls.append({"url": product.image_url})
        
        if product.additional_images:
            if isinstance(product.additional_images, list):
                for img in product.additional_images:
                    if img:
                        image_urls.append({"url": img})
            elif isinstance(product.additional_images, str):
                try:
                    additional = json.loads(product.additional_images)
                    if isinstance(additional, list):
                        for img in additional:
                            if img:
                                image_urls.append({"url": img})
                except json.JSONDecodeError:
                    pass
        
        return {
            "items": [{
                "barcode": product.barcode,
                "title": title,
                "productMainId": product.product_main_id or product.barcode,
                "brandId": brand_id,
                "categoryId": category_id,
                "quantity": product.quantity or 10,
                "stockCode": product.stock_code or product.barcode,
                "description": product.description or product.title,
                "currencyType": product.currency_type or "TRY",
                "listPrice": float(product.price or 0),
                "salePrice": float(product.price or 0),
                "vatRate": 10,  # Fixed to 10% VAT
                "cargoCompanyId": 17,  # Fixed cargo company ID
                "images": image_urls if image_urls else [{"url": ""}],
                "attributes": attributes,
                "gender": {"id": 1}  # Default to Unisex
            }]
        }


def get_api_client_from_config():
    """Get a TrendyolAPI client instance from the active configuration"""
    try:
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            logger.error("No active Trendyol API configuration found")
            return None
        
        return TrendyolAPI(config)
    except Exception as e:
        logger.error(f"Failed to initialize Trendyol API client: {str(e)}")
        return None


def get_product_manager():
    """Get a TrendyolProductManager instance"""
    api_client = get_api_client_from_config()
    if not api_client:
        return None
    
    return TrendyolProductManager(api_client)


def find_best_category_match(product: TrendyolProduct) -> int:
    """Find the best matching category for a product"""
    try:
        product_manager = get_product_manager()
        if not product_manager:
            logger.error("Failed to initialize product manager")
            return None
        
        category_name = product.category_name
        if not category_name:
            logger.error(f"No category name provided for product {product.id}")
            return None
        
        logger.info(f"Finding category for '{category_name}'")
        category_id = product_manager.category_finder.find_best_category(category_name)
        
        logger.info(f"Found category ID {category_id} for '{category_name}'")
        return category_id
    except Exception as e:
        logger.error(f"Category matching failed: {str(e)}")
        return None


def find_best_brand_match(product: TrendyolProduct) -> int:
    """Find the best matching brand for a product"""
    try:
        product_manager = get_product_manager()
        if not product_manager:
            logger.error("Failed to initialize product manager")
            return None
        
        brand_name = product.brand_name
        if not brand_name:
            logger.error(f"No brand name provided for product {product.id}")
            return None
        
        logger.info(f"Finding brand ID for '{brand_name}'")
        brand_id = product_manager.get_brand_id(brand_name)
        
        logger.info(f"Found brand ID {brand_id} for '{brand_name}'")
        return brand_id
    except Exception as e:
        logger.error(f"Brand matching failed: {str(e)}")
        return None


def create_trendyol_product(product: TrendyolProduct) -> str:
    """Create a product on Trendyol"""
    try:
        product_manager = get_product_manager()
        if not product_manager:
            error_message = "No active Trendyol API configuration found"
            logger.error(error_message)
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None
        
        # Validate required fields
        if not product.title or not product.barcode or not product.price:
            error_message = "Missing required fields: title, barcode, or price"
            logger.error(f"{error_message} for product {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None
        
        logger.info(f"Creating product '{product.title}' on Trendyol")
        batch_id = product_manager.create_product(product)
        
        if not batch_id:
            error_message = "Failed to get batch ID from Trendyol API"
            logger.error(f"{error_message} for product {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None
        
        # Update product with batch ID and status
        logger.info(f"Product submitted with batch ID: {batch_id}")
        product.batch_id = batch_id
        product.batch_status = 'processing'
        product.status_message = "Product creation initiated"
        product.last_check_time = timezone.now()
        product.save()
        
        return batch_id
    except Exception as e:
        error_message = f"Error creating product: {str(e)}"
        logger.error(f"{error_message} for product {product.id}")
        product.batch_status = 'failed'
        product.status_message = error_message
        product.save()
        return None


def check_product_batch_status(product: TrendyolProduct) -> str:
    """Check the status of a product batch on Trendyol"""
    if not product.batch_id:
        logger.error(f"No batch ID available for product {product.id}")
        product.batch_status = 'failed'
        product.status_message = "No batch ID available to check status"
        product.save()
        return 'failed'
    
    try:
        product_manager = get_product_manager()
        if not product_manager:
            error_message = "No active Trendyol API configuration found"
            logger.error(error_message)
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return 'failed'
        
        logger.info(f"Checking batch status for ID: {product.batch_id}")
        response = product_manager.check_batch_status(product.batch_id)
        
        if not response:
            error_message = "No response from Trendyol API for batch status"
            logger.error(f"{error_message} for product {product.id}")
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return 'failed'
        
        # Process the response to determine status
        status = 'processing'  # Default status
        status_message = "Processing in progress"
        
        # Check if response is a dictionary with status information
        if isinstance(response, dict):
            # First check if the response has a status field
            if 'status' in response:
                status = response['status'].lower()
                status_message = f"Status: {response['status']}"
            
            # If we have a batchRequestId but no explicit status field
            elif 'batchRequestId' in response:
                # Check item counts to determine status
                total_items = response.get('itemCount', 0)
                failed_items = response.get('failedItemCount', 0)
                success_items = response.get('successItemCount', 0)
                
                if total_items == 0:
                    status = 'processing'
                    status_message = "Batch is being processed, no items reported yet"
                elif failed_items == total_items:
                    status = 'failed'
                    status_message = f"All {failed_items} items failed"
                elif success_items == total_items:
                    status = 'success'
                    status_message = f"All {success_items} items processed successfully"
                elif success_items > 0 and failed_items > 0:
                    status = 'partial'
                    status_message = f"{success_items} items succeeded, {failed_items} items failed"
                else:
                    status = 'processing'
                    status_message = f"Processing: {success_items} successful, {failed_items} failed out of {total_items}"
            
            # Check for specific error information in the items array
            if 'items' in response and isinstance(response['items'], list) and response['items']:
                for item in response['items']:
                    if 'status' in item and item['status'] == 'FAILED':
                        status = 'failed'
                        if 'errorMessage' in item:
                            status_message = f"Error: {item['errorMessage']}"
                            break
        
        # Update product with status information
        product.batch_status = status
        product.status_message = status_message
        product.last_check_time = timezone.now()
        
        # If the product has been successfully created on Trendyol, update the Trendyol ID and URL
        if status == 'success' and 'items' in response and isinstance(response['items'], list):
            for item in response['items']:
                if 'status' in item and item['status'] == 'SUCCESS' and 'productId' in item:
                    product.trendyol_id = item['productId']
                    product.trendyol_url = f"https://www.trendyol.com/brand/name-p-{item['productId']}"
                    break
        
        product.save()
        logger.info(f"Updated product {product.id} with status: {status}, message: {status_message}")
        
        return status
    except Exception as e:
        error_message = f"Error checking batch status: {str(e)}"
        logger.error(f"{error_message} for product {product.id}")
        product.batch_status = 'error'
        product.status_message = error_message
        product.save()
        return 'error'


def sync_product_to_trendyol(product: TrendyolProduct) -> bool:
    """Sync a product to Trendyol"""
    if not product:
        logger.error("Cannot sync null product")
        return False
    
    # If product already has a batch ID, check its status first
    if product.batch_id:
        status = check_product_batch_status(product)
        
        # If already successful or still processing, no need to resubmit
        if status in ['success', 'processing']:
            logger.info(f"Product {product.id} is already {status} on Trendyol")
            return True
    
    # Create the product on Trendyol
    batch_id = create_trendyol_product(product)
    
    if not batch_id:
        logger.error(f"Failed to create product {product.id} on Trendyol")
        return False
    
    logger.info(f"Successfully submitted product {product.id} with batch ID {batch_id}")
    return True


def batch_process_products(products, process_func, batch_size=10, delay=0.5):
    """Process a batch of products using the provided function"""
    success_count = 0
    error_count = 0
    batch_ids = []
    
    total = len(products)
    logger.info(f"Processing {total} products in batches of {batch_size}")
    
    for i, product in enumerate(products, 1):
        try:
            logger.info(f"Processing product {i}/{total}: {product.title}")
            result = process_func(product)
            
            if result:
                success_count += 1
                if isinstance(result, str):
                    batch_ids.append(result)
            else:
                error_count += 1
                
        except Exception as e:
            error_count += 1
            logger.error(f"Error processing product {product.id}: {str(e)}")
        
        # Apply delay between requests to avoid rate limiting
        if i % batch_size == 0 and i < total:
            logger.info(f"Processed {i}/{total} products, pausing for {delay} seconds")
            time.sleep(delay)
    
    logger.info(f"Batch processing complete: {success_count} succeeded, {error_count} failed")
    return success_count, error_count, batch_ids