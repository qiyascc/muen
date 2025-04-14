"""
Gelişmiş Trendyol API İstemcisi.

Bu modül, kategori eşleştirme, öznitelik yönetimi ve ürün gönderimi için 
daha verimli ve gerçek zamanlı bir yaklaşım sunar.
"""

import requests
import json
from urllib.parse import quote
import uuid
import logging
import time
import base64
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from functools import lru_cache
from decimal import Decimal

from django.utils import timezone
from django.conf import settings

try:
    from sentence_transformers import SentenceTransformer, util
    from PyMultiDictionary import MultiDictionary
    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError:
    SEMANTIC_SEARCH_AVAILABLE = False
    
from trendyol.models import TrendyolAPIConfig, TrendyolProduct, TrendyolBrand, TrendyolCategory

logger = logging.getLogger('trendyol_api')

DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

@dataclass
class APIConfig:
    api_key: str
    api_secret: str
    seller_id: str
    base_url: str

class TrendyolAPI:
    """Temel Trendyol API operasyonları ve yeniden deneme mekanizması"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.session = requests.Session()
        
        # Basic auth için kimlik bilgilerini hazırla
        auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
        
        self.session.headers.update({
            "Authorization": f"Basic {auth_token}",
            "User-Agent": f"{self.config.seller_id} - SelfIntegration",
            "Content-Type": "application/json"
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Yeniden deneme mantığı ile genel istek metodu"""
        url = f"{self.config.base_url.rstrip('/')}/suppliers/{self.config.seller_id}/{endpoint.lstrip('/')}"
        
        # integration/ ile başlayan endpointler için özel düzenleme
        if endpoint.startswith('integration/'):
            url = f"{self.config.base_url.rstrip('/')}/{endpoint}"
        
        # Tam URL sağlanmışsa direkt kullan
        if endpoint.startswith(('http://', 'https://')):
            url = endpoint
            
        kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Making {method} request to: {url}")
                response = self.session.request(method, url, **kwargs)
                
                # Log the response for debugging
                logger.info(f"Response status: {response.status_code}")
                logger.debug(f"Response content: {response.text[:500]}...")
                
                response.raise_for_status()
                if not response.text.strip():
                    return {}
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {str(e)}")
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API request failed after {MAX_RETRIES} attempts: {str(e)}")
                    raise
                time.sleep(RETRY_DELAY * (attempt + 1))
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Dict) -> Dict:
        return self._make_request('POST', endpoint, json=data)

class TrendyolCategoryFinder:
    """Kategori keşfi ve öznitelik yönetimi"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self._category_cache = None
        self._attribute_cache = {}
        
        if SEMANTIC_SEARCH_AVAILABLE:
            try:
                self.model = SentenceTransformer('emrecan/bert-base-turkish-cased-mean-nli-stsb-tr')
                self.dictionary = MultiDictionary()
                logger.info("Semantik arama bileşenleri başarıyla yüklendi")
            except Exception as e:
                logger.warning(f"Semantik arama bileşenleri yüklenemedi: {str(e)}")
                self.model = None
                self.dictionary = None
        else:
            self.model = None
            self.dictionary = None
    
    @property
    def category_cache(self) -> List[Dict]:
        if self._category_cache is None:
            self._category_cache = self._fetch_all_categories()
        return self._category_cache
    
    def _fetch_all_categories(self) -> List[Dict]:
        """Trendyol API'sinden tüm kategorileri getir"""
        try:
            data = self.api.get("product/categories")
            return data.get('categories', [])
        except Exception as e:
            logger.error(f"Kategoriler alınamadı: {str(e)}")
            raise Exception("Kategoriler yüklenemedi. API kimlik bilgilerinizi kontrol edin ve tekrar deneyin.")
    
    @lru_cache(maxsize=128)
    def get_category_attributes(self, category_id: int) -> Dict:
        """Belirli bir kategori için öznitelikleri önbellekleme ile al"""
        try:
            data = self.api.get(f"product/categories/{category_id}/attributes")
            return data
        except Exception as e:
            logger.error(f"Kategori {category_id} için öznitelikler alınamadı: {str(e)}")
            raise Exception(f"Kategori {category_id} için öznitelikler yüklenemedi")
    
    def find_best_category(self, search_term: str) -> int:
        """Verilen arama terimi için en alakalı kategoriyi bul"""
        try:
            categories = self.category_cache
            if not categories:
                raise ValueError("API'den boş kategori listesi alındı")
            
            all_matches = self._find_all_possible_matches(search_term, categories)
            
            if exact_match := self._find_exact_match(search_term, all_matches):
                return exact_match
            
            if all_matches:
                return self._select_best_match(search_term, all_matches)['id']
            
            leaf_categories = self._get_all_leaf_categories(categories)
            if leaf_categories:
                return self._select_best_match(search_term, leaf_categories)['id']
            
            suggestions = self._get_category_suggestions(search_term, categories)
            raise ValueError(f"Tam eşleşme bulunamadı. En yakın kategoriler:\n{suggestions}")
            
        except Exception as e:
            logger.error(f"'{search_term}' için kategori araması başarısız oldu: {str(e)}")
            # Varsayılan olarak giyim kategorisini döndür (ID: 2356)
            return 2356
    
    def _find_all_possible_matches(self, search_term: str, categories: List[Dict]) -> List[Dict]:
        """Eşanlamlılar dahil tüm olası eşleşmeleri bul"""
        search_terms = {search_term.lower()}
        
        if self.dictionary:
            try:
                synonyms = self.dictionary.synonym('tr', search_term.lower())
                search_terms.update(synonyms[:5])
            except Exception as e:
                logger.debug(f"Eşanlamlılar alınamadı: {str(e)}")
        
        matches = []
        for term in search_terms:
            matches.extend(self._find_matches_for_term(term, categories))
        
        seen_ids = set()
        return [m for m in matches if not (m['id'] in seen_ids or seen_ids.add(m['id']))]
    
    def _find_matches_for_term(self, term: str, categories: List[Dict]) -> List[Dict]:
        """Kategori ağacında özyinelemeli olarak eşleşmeler bul"""
        matches = []
        term_lower = term.lower()
        
        for cat in categories:
            cat_name_lower = cat['name'].lower()
            
            if term_lower == cat_name_lower or term_lower in cat_name_lower:
                if not cat.get('subCategories'):
                    matches.append(cat)
            
            if cat.get('subCategories'):
                matches.extend(self._find_matches_for_term(term, cat['subCategories']))
        
        return matches
    
    def _find_exact_match(self, search_term: str, matches: List[Dict]) -> Optional[int]:
        """Tam ad eşleşmelerini kontrol et"""
        search_term_lower = search_term.lower()
        for match in matches:
            if search_term_lower == match['name'].lower():
                return match['id']
        return None
    
    def _select_best_match(self, search_term: str, candidates: List[Dict]) -> Dict:
        """Semantik benzerlik kullanarak en iyi eşleşmeyi seç"""
        if self.model:
            search_embedding = self.model.encode(search_term, convert_to_tensor=True)
            
            for candidate in candidates:
                candidate_embedding = self.model.encode(candidate['name'], convert_to_tensor=True)
                candidate['similarity'] = util.cos_sim(search_embedding, candidate_embedding).item()
            
            candidates_sorted = sorted(candidates, key=lambda x: x['similarity'], reverse=True)
            
            logger.info(f"'{search_term}' için en iyi 3 eşleşme:")
            for i, candidate in enumerate(candidates_sorted[:3], 1):
                logger.info(f"{i}. {candidate['name']} (Benzerlik: {candidate['similarity']:.2f})")
            
            return candidates_sorted[0]
        else:
            # Model yoksa basit kelime eşleşmesi kullan
            for candidate in candidates:
                candidate['similarity'] = 0
                if search_term.lower() in candidate['name'].lower():
                    candidate['similarity'] = 1
                    
            candidates_sorted = sorted(candidates, key=lambda x: x['similarity'], reverse=True)
            return candidates_sorted[0] if candidates_sorted else candidates[0]
    
    def _get_all_leaf_categories(self, categories: List[Dict]) -> List[Dict]:
        """Tüm yaprak kategorileri al (alt kategorileri olmayan kategoriler)"""
        leaf_categories = []
        self._collect_leaf_categories(categories, leaf_categories)
        return leaf_categories
    
    def _collect_leaf_categories(self, categories: List[Dict], result: List[Dict]) -> None:
        """Özyinelemeli olarak yaprak kategorileri topla"""
        for cat in categories:
            if not cat.get('subCategories'):
                result.append(cat)
            else:
                self._collect_leaf_categories(cat['subCategories'], result)
    
    def _get_category_suggestions(self, search_term: str, categories: List[Dict], top_n: int = 3) -> str:
        """Kullanıcı dostu öneriler oluştur"""
        leaf_categories = self._get_all_leaf_categories(categories)
        
        if self.model:
            search_embedding = self.model.encode(search_term, convert_to_tensor=True)
            for cat in leaf_categories:
                cat_embedding = self.model.encode(cat['name'], convert_to_tensor=True)
                cat['similarity'] = util.cos_sim(search_embedding, cat_embedding).item()
        else:
            # Model yoksa basit kelime eşleşmesi kullan
            for cat in leaf_categories:
                cat['similarity'] = 0
                if search_term.lower() in cat['name'].lower():
                    cat['similarity'] = 1
        
        sorted_cats = sorted(leaf_categories, key=lambda x: x['similarity'], reverse=True)
        
        suggestions = []
        for i, cat in enumerate(sorted_cats[:top_n], 1):
            suggestions.append(f"{i}. {cat['name']} (Benzerlik: {cat['similarity']:.2f}, ID: {cat['id']})")
        
        return "\n".join(suggestions)

class TrendyolProductManager:
    """Ürün oluşturma ve yönetimi"""
    
    def __init__(self, api_client: TrendyolAPI):
        self.api = api_client
        self.category_finder = TrendyolCategoryFinder(api_client)
    
    def get_brand_id(self, brand_name: str) -> int:
        """İsme göre marka ID'sini bul"""
        encoded_name = quote(brand_name)
        try:
            brands = self.api.get(f"brands/by-name?name={encoded_name}")
            if isinstance(brands, list) and brands:
                logger.info(f"Marka bulundu: {brand_name}, ID: {brands[0]['id']}")
                return brands[0]['id']
            
            # Marka bulunamadı, varsayılan LCWaikiki marka ID'sini kullan
            logger.warning(f"Marka bulunamadı: {brand_name}, varsayılan LCWaikiki ID'si (7651) kullanılıyor")
            return 7651
        except Exception as e:
            logger.error(f"'{brand_name}' markası için arama başarısız oldu: {str(e)}")
            # Varsayılan LCWaikiki marka ID'sini döndür
            return 7651
    
    def create_product(self, product: TrendyolProduct) -> str:
        """Trendyol'da yeni bir ürün oluştur"""
        try:
            # Kategori ve marka ID'lerini al
            category_id = self.category_finder.find_best_category(product.category_name)
            brand_id = product.brand_id if product.brand_id else self.get_brand_id(product.brand_name)
            
            # Kategori özniteliklerini al ve uygun şekilde hazırla
            raw_attributes = self.category_finder.get_category_attributes(category_id)
            attributes = self._prepare_product_attributes(raw_attributes, product)
            
            # Ürün yükünü oluştur
            batch_id = str(uuid.uuid4())
            
            payload = {
                "items": [{
                    "barcode": product.barcode,
                    "title": product.title,
                    "productMainId": product.product_main_id or product.barcode,
                    "brandId": brand_id,
                    "categoryId": category_id,
                    "quantity": product.quantity,
                    "stockCode": product.stock_code or product.barcode,
                    "dimensionalWeight": 1,
                    "description": product.description,
                    "currencyType": product.currency_type,
                    "listPrice": float(product.price),
                    "salePrice": float(product.price),  # Sale price aynı olarak ayarlandı
                    "vatRate": product.vat_rate,
                    "cargoCompanyId": 10,  # Varsayılan kargo şirketi ID'si
                    "images": [{"url": product.image_url}],
                    "attributes": attributes
                }],
                "batchRequestId": batch_id,
                "hasMultiSupplier": False,
                "supplierId": int(self.api.config.seller_id)
            }
            
            # Ek görüntüler varsa ekle
            if product.additional_images:
                for img_url in product.additional_images:
                    if isinstance(img_url, str) and img_url.startswith('http'):
                        payload["items"][0]["images"].append({"url": img_url})
            
            logger.info(f"Ürün oluşturma isteği gönderiliyor: {product.title}")
            logger.debug(f"Ürün yükü: {json.dumps(payload, ensure_ascii=False)}")
            
            # Ürün oluşturma isteğini gönder
            response = self.api.post("products", payload)
            
            # Batch ID'yi güncelle ve kaydet
            product.batch_id = batch_id
            product.batch_status = 'processing'
            product.status_message = f"Ürün oluşturma isteği gönderildi: {batch_id}"
            product.last_check_time = timezone.now()
            product.save()
            
            logger.info(f"Ürün oluşturma başlatıldı. Batch ID: {batch_id}")
            return batch_id
        except Exception as e:
            logger.error(f"Ürün oluşturma başarısız oldu: {str(e)}")
            product.batch_status = 'failed'
            product.status_message = f"Hata: {str(e)}"
            product.save()
            raise
    
    def check_batch_status(self, batch_id: str) -> Dict:
        """Toplu işlem durumunu kontrol et"""
        try:
            return self.api.get(f"products/batch-requests/{batch_id}")
        except Exception as e:
            logger.error(f"Toplu işlem durumu kontrol edilemedi: {str(e)}")
            raise
    
    def _prepare_product_attributes(self, raw_attributes: Dict, product: TrendyolProduct) -> List[Dict]:
        """Ürün özniteliklerini hazırla"""
        attributes = []
        
        # Ürünün kendi öznitelikleri varsa, onları kullan
        if product.attributes and isinstance(product.attributes, dict):
            # Öznitelikleri liste formatına dönüştür
            for attr_id, attr_value in product.attributes.items():
                if attr_id.isdigit():  # Geçerli bir öznitelik ID'si
                    if isinstance(attr_value, dict):
                        attributes.append({
                            "attributeId": int(attr_id),
                            "attributeValueId": attr_value.get("id"),
                            "attributeValue": attr_value.get("value", "")
                        })
                    else:  # Basit değer (muhtemelen ID)
                        attributes.append({
                            "attributeId": int(attr_id),
                            "attributeValueId": int(attr_value) if str(attr_value).isdigit() else None,
                            "attributeValue": str(attr_value)
                        })
        
        # Zorunlu renk özniteliğini ekle
        color_added = False
        for attr in attributes:
            if attr.get("attributeId") == 348:  # 348, renk öznitelik ID'si
                color_added = True
                break
        
        if not color_added:
            # Varsayılan olarak siyah renk ekle
            attributes.append({
                "attributeId": 348,
                "attributeValueId": 4294,  # 4294, siyah renk değeri ID'si
                "attributeValue": "Siyah"
            })
        
        return attributes
        
def create_api_client():
    """API istemcisi oluştur"""
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("Aktif Trendyol API yapılandırması bulunamadı")
        return None
    
    api_config = APIConfig(
        api_key=config.api_key,
        api_secret=config.api_secret,
        seller_id=config.seller_id,
        base_url=config.base_url
    )
    
    return TrendyolAPI(api_config)

def create_product_manager():
    """Ürün yöneticisi oluştur"""
    api_client = create_api_client()
    if not api_client:
        return None
    
    return TrendyolProductManager(api_client)