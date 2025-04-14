"""
Trendyol API'den kategori, marka ve öznitelik bilgilerini çeken modül.

Bu modül, ürün oluşturma ve güncelleme işlemleri sırasında gerekli kategori, marka 
ve öznitelik bilgilerini direkt olarak Trendyol API'den çeker.
"""

import logging
import requests
import json
import base64
from django.core.cache import cache

from trendyol.models import TrendyolAPIConfig
from trendyol.models import TrendyolCategory, TrendyolBrand

logger = logging.getLogger(__name__)

def get_api_auth():
    """Trendyol API için kimlik doğrulama başlıklarını alır"""
    config = TrendyolAPIConfig.objects.first()
    if not config:
        logger.error("API yapılandırması bulunamadı!")
        return None, None
    
    auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_token}",
        "User-Agent": f"{config.supplier_id} - SelfIntegration",
        "Content-Type": "application/json"
    }
    
    return config.base_url, headers

def fetch_all_categories(force_refresh=False):
    """Tüm kategorileri API'den çeker ve veritabanına kaydeder"""
    # Önce cache'i kontrol et
    if not force_refresh:
        cached_categories = cache.get("trendyol_categories")
        if cached_categories:
            return cached_categories
    
    base_url, headers = get_api_auth()
    if not base_url or not headers:
        logger.error("API kimlik bilgileri alınamadı!")
        return []
    
    url = f"{base_url.rstrip('/')}/product/categories"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        categories_data = response.json()
        categories = []
        
        # Kategorileri veritabanına kaydet
        TrendyolCategory.objects.all().delete()  # Önce hepsini sil
        
        for category in categories_data.get('categories', []):
            categories.append({
                'id': category['id'],
                'name': category['name'],
                'parent_id': category.get('parentId'),
                'has_children': len(category.get('subCategories', [])) > 0
            })
            
            # Veritabanına kaydet
            TrendyolCategory.objects.create(
                category_id=category['id'],
                name=category['name'],
                parent_id=category.get('parentId', None),
                path_names=[]  # Boş bırak, ihtiyaç olursa doldurulabilir
            )
            
            # Alt kategorileri de kontrol et
            for subcategory in category.get('subCategories', []):
                categories.append({
                    'id': subcategory['id'],
                    'name': subcategory['name'],
                    'parent_id': category['id'],
                    'has_children': len(subcategory.get('subCategories', [])) > 0
                })
                
                # Veritabanına kaydet
                TrendyolCategory.objects.create(
                    category_id=subcategory['id'],
                    name=subcategory['name'],
                    parent_id=category['id'],
                    path_names=[]
                )
        
        # Cache'e kaydet
        cache.set("trendyol_categories", categories, 3600)  # 1 saat cache
        
        return categories
    except Exception as e:
        logger.error(f"Kategoriler alınırken hata oluştu: {str(e)}")
        return []

def fetch_all_brands(force_refresh=False):
    """Tüm markaları API'den çeker ve veritabanına kaydeder"""
    # Önce cache'i kontrol et
    if not force_refresh:
        cached_brands = cache.get("trendyol_brands")
        if cached_brands:
            return cached_brands
    
    base_url, headers = get_api_auth()
    if not base_url or not headers:
        logger.error("API kimlik bilgileri alınamadı!")
        return []
    
    url = f"{base_url.rstrip('/')}/brands"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        brands_data = response.json()
        brands = []
        
        # Markaları veritabanına kaydet
        TrendyolBrand.objects.all().delete()  # Önce hepsini sil
        
        for brand in brands_data.get('brands', []):
            brands.append({
                'id': brand['id'],
                'name': brand['name']
            })
            
            # Veritabanına kaydet
            TrendyolBrand.objects.create(
                brand_id=brand['id'],
                name=brand['name']
            )
        
        # Cache'e kaydet
        cache.set("trendyol_brands", brands, 3600)  # 1 saat cache
        
        return brands
    except Exception as e:
        logger.error(f"Markalar alınırken hata oluştu: {str(e)}")
        return []

def get_brand_id_by_name(brand_name):
    """Marka adına göre Trendyol marka ID'sini bulur"""
    # Önce veritabanını kontrol et
    try:
        brand = TrendyolBrand.objects.filter(name__icontains=brand_name).first()
        if brand:
            return brand.brand_id
    except:
        pass
    
    # Veritabanında yoksa API'den çek
    brands = fetch_all_brands()
    
    for brand in brands:
        if brand_name.lower() in brand['name'].lower():
            return brand['id']
    
    # Hala bulunamadıysa, mevcut tüm markalar içinde en benzerini bulalım
    if brands:
        # Varsayılan olarak ilk markayı döndür
        logger.warning(f"'{brand_name}' markası bulunamadı, ilk marka döndürülüyor: {brands[0]['name']}")
        return brands[0]['id']
    
    # Hiçbir marka bulunamadıysa
    logger.error(f"'{brand_name}' markası bulunamadı ve hiç marka verisi alınamadı")
    return None

def get_category_attributes(category_id):
    """Belirli bir kategori için öznitelikleri alır"""
    # Önce cache'i kontrol et
    cache_key = f"trendyol_category_attrs_{category_id}"
    cached_attrs = cache.get(cache_key)
    if cached_attrs:
        return cached_attrs
    
    base_url, headers = get_api_auth()
    if not base_url or not headers:
        logger.error("API kimlik bilgileri alınamadı!")
        return None
    
    url = f"{base_url.rstrip('/')}/product/product-categories/{category_id}/attributes"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        attrs_data = response.json()
        
        # Cache'e kaydet
        cache.set(cache_key, attrs_data, 3600)  # 1 saat cache
        
        return attrs_data
    except Exception as e:
        logger.error(f"Kategori {category_id} özellikleri alınırken hata oluştu: {str(e)}")
        return None

def get_required_attributes(category_id):
    """Belirli bir kategori için zorunlu öznitelikleri alır"""
    attributes = get_category_attributes(category_id)
    if not attributes:
        return []
    
    required_attrs = []
    
    for attr in attributes.get('categoryAttributes', []):
        if attr.get('required', False):
            required_attrs.append({
                'id': attr.get('id'),
                'name': attr.get('name'),
                'allowCustom': attr.get('allowCustom', False),
                'values': [
                    {'id': val.get('id'), 'name': val.get('name')}
                    for val in attr.get('attributeValues', [])
                ]
            })
    
    return required_attrs

def get_color_attribute_id(category_id):
    """Belirli bir kategori için renk özniteliğini alır"""
    attributes = get_category_attributes(category_id)
    if not attributes:
        return 348  # Varsayılan renk ID'si
    
    for attr in attributes.get('categoryAttributes', []):
        if attr.get('name', '').lower() == 'renk':
            return attr.get('id')
    
    return 348  # Varsayılan renk ID'si

def get_color_value_id(category_id, color_name):
    """Belirli bir kategori için renk değeri ID'sini alır"""
    attributes = get_category_attributes(category_id)
    if not attributes:
        return 686234  # Varsayılan Siyah renk değeri ID'si
    
    for attr in attributes.get('categoryAttributes', []):
        if attr.get('name', '').lower() == 'renk':
            for value in attr.get('attributeValues', []):
                if value.get('name', '').lower() == color_name.lower():
                    return value.get('id')
            
            # Renk bulunamadıysa, ilk rengi kullan
            if attr.get('attributeValues'):
                logger.warning(f"'{color_name}' rengi bulunamadı, ilk renk döndürülüyor: {attr['attributeValues'][0]['name']}")
                return attr['attributeValues'][0]['id']
    
    return 686234  # Varsayılan Siyah renk değeri ID'si

def ensure_product_has_required_attributes(product, category_id):
    """Ürünün tüm zorunlu öznitelikleri içerdiğinden emin olur"""
    required_attrs = get_required_attributes(category_id)
    
    if not required_attrs:
        logger.warning(f"Kategori {category_id} için zorunlu öznitelikler alınamadı")
        return product
    
    # Ürünün mevcut özniteliklerini kontrol et
    if not product.get('attributes'):
        product['attributes'] = []
    
    # Öznitelikler string ise JSON'a çevir
    if isinstance(product['attributes'], str):
        try:
            product['attributes'] = json.loads(product['attributes'])
        except:
            product['attributes'] = []
    
    # Her zorunlu öznitelik için kontrol et
    for req_attr in required_attrs:
        attr_exists = False
        
        # Mevcut öznitelikler içinde ara
        for i, attr in enumerate(product['attributes']):
            if attr.get('attributeId') == req_attr['id']:
                attr_exists = True
                break
        
        # Eğer öznitelik yoksa, ekle
        if not attr_exists and req_attr['values']:
            product['attributes'].append({
                'attributeId': req_attr['id'],
                'attributeValueId': req_attr['values'][0]['id']
            })
            logger.info(f"Ürüne zorunlu öznitelik eklendi: {req_attr['name']} (ID: {req_attr['id']})")
    
    return product