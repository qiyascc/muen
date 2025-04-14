import logging
import json
import requests
import base64
import time
from typing import Dict, List, Optional, Any, Tuple

from django.utils import timezone

from .models import TrendyolAPIConfig, TrendyolBrand, TrendyolCategory, TrendyolProduct

logger = logging.getLogger(__name__)


class TrendyolApi:
    """Basit Trendyol API istemcisi"""

    def __init__(self,
                api_key,
                api_secret,
                supplier_id,
                base_url='https://api.trendyol.com/sapigw',
                user_agent=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.supplier_id = supplier_id

        # URL formatını düzenle
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        self.base_url = base_url

        self.user_agent = user_agent or f"{supplier_id} - SelfIntegration"
        self.brands = BrandsAPI(self)
        self.categories = CategoriesAPI(self)
        self.products = ProductsAPI(self)
        self.inventory = InventoryAPI(self)

    def make_request(self, method, endpoint, data=None, params=None):
        """Trendyol API'sine istek gönder"""
        # Endpoint'in / ile başlamasını sağla
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'

        # URL oluştur
        url = f"{self.base_url}{endpoint}"

        # Kimlik doğrulama bilgilerini hazırla
        auth_string = f"{self.api_key}:{self.api_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()

        headers = {
            'Authorization': f"Basic {auth_encoded}",
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
        }

        logger.info(f"İstek gönderiliyor: {method} {url}")

        try:
            # İsteği gönder
            response = requests.request(method=method,
                                        url=url,
                                        headers=headers,
                                        params=params,
                                        json=data,
                                        timeout=30)

            # Yanıt durumunu logla
            logger.info(f"Yanıt durumu: {response.status_code}")
            logger.info(f"Yanıt başlıkları: {dict(response.headers)}")
            
            # Yanıt içeriğini logla (hatalar için)
            if response.status_code >= 400:
                logger.error(f"Hata yanıtı: {response.text}")

            # İstek başarılı mı kontrol et
            response.raise_for_status()

            # JSON yanıtı çözümle
            try:
                result = response.json()
                logger.info(f"Yanıt verisi: {json.dumps(result)}")
                return result
            except ValueError:
                # JSON değilse metin olarak döndür
                logger.info(f"Yanıt metni: {response.text}")
                return {"response": response.text}

        except requests.exceptions.RequestException as e:
            logger.error(f"Trendyol API isteği sırasında hata: {str(e)}")
            error_details = {}
            if hasattr(e, 'response') and e.response:
                error_details['status_code'] = e.response.status_code
                error_details['response_text'] = e.response.text

            # Hata yanıtını döndür
            return {"error": True, "message": str(e), "details": error_details}


class BrandsAPI:
    """Trendyol Marka API'si"""

    def __init__(self, client):
        self.client = client

    def get_brands(self, page=0, size=1000):
        """Tüm markaları getir"""
        endpoint = '/product/brands'
        params = {'page': page, 'size': size}
        return self.client.make_request('GET', endpoint, params=params)

    def get_brand_by_name(self, name):
        """İsme göre marka getir"""
        endpoint = '/product/brands/by-name'
        params = {'name': name}
        return self.client.make_request('GET', endpoint, params=params)


class CategoriesAPI:
    """Trendyol Kategori API'si"""

    def __init__(self, client):
        self.client = client

    def get_categories(self):
        """Tüm kategorileri getir"""
        endpoint = '/product-categories'
        return self.client.make_request('GET', endpoint)

    def get_category_attributes(self, category_id):
        """Belirli bir kategori için özellikleri getir"""
        endpoint = f'/product/product-categories/{category_id}/attributes'
        return self.client.make_request('GET', endpoint)


class ProductsAPI:
    """Trendyol Ürün API'si"""

    def __init__(self, client):
        self.client = client

    def create_products(self, products):
        """Trendyol'da ürün oluştur"""
        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products'
        return self.client.make_request('POST', endpoint, data={"items": products})

    def update_products(self, products):
        """Mevcut ürünleri güncelle"""
        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products'
        return self.client.make_request('PUT', endpoint, data={"items": products})

    def delete_products(self, barcodes):
        """Ürünleri sil"""
        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products'
        items = [{"barcode": barcode} for barcode in barcodes]
        return self.client.make_request('DELETE', endpoint, data={"items": items})

    def get_batch_request_status(self, batch_id):
        """Toplu istek durumunu kontrol et"""
        if not batch_id:
            logger.warning("Boş batch ID ile durum kontrolü denendi")
            return None

        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products/batch-requests/{batch_id}'
        return self.client.make_request('GET', endpoint)

    def get_products(self, barcode=None, approved=None, page=0, size=50):
        """Ürünleri getir"""
        endpoint = f'/integration/product/sellers/{self.client.supplier_id}/products'
        params = {'page': page, 'size': size}

        if barcode:
            params['barcode'] = barcode

        if approved is not None:
            params['approved'] = approved

        return self.client.make_request('GET', endpoint, params=params)

    def get_product_by_barcode(self, barcode):
        """Barkoda göre ürün getir"""
        return self.get_products(barcode=barcode, page=0, size=1)


class InventoryAPI:
    """Trendyol Envanter API'si (fiyat ve stok güncellemeleri için)"""

    def __init__(self, client):
        self.client = client

    def update_price_and_inventory(self, items):
        """
        Ürünlerin fiyat ve envanterini güncelle
        
        Args:
            items: Barkod, miktar, satış fiyatı ve liste fiyatı içeren sözlüklerin listesi
                  Örnek: [{"barcode": "123456", "quantity": 10, "salePrice": 100.0, "listPrice": 120.0}]
        
        Returns:
            Başarılı olursa batchRequestId içeren sözlük
        """
        endpoint = f'/integration/inventory/sellers/{self.client.supplier_id}/products/price-and-inventory'
        return self.client.make_request('POST', endpoint, data={"items": items})


def get_api_client() -> Optional[TrendyolApi]:
    """
    Yapılandırılmış bir Trendyol API istemcisi alır.
    Etkin API yapılandırması bulunamazsa None döndürür.
    """
    try:
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        if not config:
            logger.error("Etkin Trendyol API yapılandırması bulunamadı")
            return None

        # Kullanıcı ajanını al veya varsayılan oluştur
        user_agent = config.user_agent
        if not user_agent:
            user_agent = f"{config.seller_id} - SelfIntegration"

        # Trendyol API istemcisini başlat
        client = TrendyolApi(
            api_key=config.api_key,
            api_secret=config.api_secret,
            supplier_id=config.seller_id,
            base_url=config.base_url,
            user_agent=user_agent
        )

        return client
    except Exception as e:
        logger.error(f"Trendyol API istemcisi oluşturma hatası: {str(e)}")
        return None


def lcwaikiki_to_trendyol_product(lcw_product):
    """
    LCWaikiki ürününü Trendyol ürününe dönüştür
    """
    from .simple_category_finder import find_best_category
    from .models import TrendyolProduct
    
    if not lcw_product:
        return None, "Source product is None"
    
    # API istemcisini al
    api_client = get_api_client()
    if not api_client:
        return None, "Etkin Trendyol API yapılandırması bulunamadı"
    
    # Marka bulmaya çalış
    brand_name = "LCW"  # Varsayılan marka
    brand_response = api_client.brands.get_brand_by_name(brand_name)
    
    brand_id = None
    if not isinstance(brand_response, dict) or 'error' not in brand_response:
        if isinstance(brand_response, list) and len(brand_response) > 0:
            brand_id = brand_response[0]['id']
            logger.info(f"Mevcut marka ID kullanılıyor: {brand_id}")
    
    if not brand_id:
        logger.warning(f"Marka bulunamadı: {brand_name}")
        brand_id = 102  # Varsayılan marka ID (LCW)
        
    # En iyi kategori eşleşmesini bul
    category_id = find_best_category(lcw_product.category or lcw_product.title)
    if not category_id:
        return None, f"Kategori bulunamadı: {lcw_product.category}"
    
    # Ürün barkodunu oluştur
    barcode = f"LCW{lcw_product.id}"
    
    # Fiyatı düzgün bir şekilde ayarla
    try:
        price = float(lcw_product.price)
    except (ValueError, TypeError):
        price = 0.0
        logger.warning(f"Fiyat dönüştürülemedi: {lcw_product.price}")
    
    # Resim URL'lerini hazırla
    images = []
    if isinstance(lcw_product.images, list):
        for image in lcw_product.images:
            if isinstance(image, dict) and "image_url" in image:
                images.append({"url": image["image_url"]})
            elif isinstance(image, str):
                images.append({"url": image})
    
    # Öznitelikleri hazırla (Renk bilgisini içermeli)
    attributes = []
    
    # Renk özniteliğini ekle (Trendyol'un şart koştuğu)
    if hasattr(lcw_product, 'color') and lcw_product.color:
        attributes.append({
            "attributeId": 348,  # Renk öznitelik ID'si
            "attributeValueId": 6530  # Siyah renk için varsayılan ID (gerçekte doğru ID bulunmalı)
        })
    
    # Trendyol ürünü oluştur
    trendyol_product = TrendyolProduct(
        title=lcw_product.title,
        description=lcw_product.description or lcw_product.title,
        barcode=barcode,
        product_main_id=barcode,
        brand_name="LCW",
        brand_id=brand_id,
        category_name=lcw_product.category,
        category_id=category_id,
        price=price,
        quantity=lcw_product.in_stock or 0,
        vat_rate=18,  # Varsayılan KDV oranı
        stock_code=barcode,
        attributes=attributes,
        image_url=lcw_product.images[0]["image_url"] if isinstance(lcw_product.images, list) and len(lcw_product.images) > 0 and "image_url" in lcw_product.images[0] else "",
        additional_images=images,
        lcwaikiki_product=lcw_product,
        batch_status='pending'
    )
    
    # Veritabanına kaydet
    trendyol_product.save()
    
    # Model verilerini Trendyol API formatına dönüştür
    formatted_data = {
        "barcode": trendyol_product.barcode,
        "title": trendyol_product.title,
        "productMainId": trendyol_product.product_main_id,
        "brandId": trendyol_product.brand_id,
        "categoryId": trendyol_product.category_id,
        "listPrice": float(trendyol_product.price) * 1.5,  # liste fiyatı daha yüksek
        "salePrice": float(trendyol_product.price),
        "vatRate": trendyol_product.vat_rate,
        "stockCode": trendyol_product.stock_code,
        "dimensionalWeight": 1,  # Varsayılan değer
        "description": trendyol_product.description,
        "cargoCompanyId": 17,  # Varsayılan değer (genelde MNG)
        "images": [{"url": trendyol_product.image_url}] if trendyol_product.image_url else [],
        "attributes": trendyol_product.attributes
    }
    
    return trendyol_product, formatted_data


def send_product_to_trendyol(product):
    """
    Ürünü Trendyol'a gönder
    """
    api_client = get_api_client()
    if not api_client:
        return None, "Etkin Trendyol API yapılandırması bulunamadı"
    
    # LCWaikiki ürünü ise, önce Trendyol ürününe dönüştür
    if not hasattr(product, 'barcode'):
        from lcwaikiki.product_models import Product as LcwProduct
        if isinstance(product, LcwProduct):
            trendyol_product, product_data = lcwaikiki_to_trendyol_product(product)
            if not trendyol_product:
                return None, str(product_data) if isinstance(product_data, str) else "Ürün dönüştürme hatası"
    else:
        # Zaten bir TrendyolProduct nesnesi
        trendyol_product = product
        
        # Basit veri dönüşümü
        product_data = {
            "barcode": trendyol_product.barcode,
            "title": trendyol_product.title,
            "productMainId": trendyol_product.product_main_id or trendyol_product.barcode,
            "brandId": trendyol_product.brand_id,
            "categoryId": trendyol_product.category_id,
            "listPrice": float(trendyol_product.price) * 1.5,  # Liste fiyatı daha yüksek ayarla
            "salePrice": float(trendyol_product.price),
            "vatRate": trendyol_product.vat_rate,
            "stockCode": trendyol_product.stock_code or trendyol_product.barcode,
            "dimensionalWeight": 1.0,  # Varsayılan değer
            "description": trendyol_product.description,
            "cargoCompanyId": 17,  # Varsayılan değer
            "images": [{"url": trendyol_product.image_url}] if trendyol_product.image_url else [],
            "attributes": trendyol_product.attributes if trendyol_product.attributes else []
        }
    
    # Gerekli alanların mevcut olduğundan emin ol
    if not product_data.get("barcode"):
        return None, "Ürün barkodu tanımlanmamış"
    
    if not product_data.get("categoryId"):
        return None, "Ürün kategorisi tanımlanmamış"
    
    if not product_data.get("brandId"):
        return None, "Ürün markası tanımlanmamış"
    
    # Hata ayıklama bilgilerini yazdır
    print(f"[DEBUG-CREATE] Ürün gönderiliyor: {trendyol_product.title}")
    print(f"[DEBUG-CREATE] Gönderilen veri: {json.dumps(product_data, indent=2)}")
    
    # Ürünü Trendyol'a gönder
    response = api_client.products.create_products([product_data])
    
    # Hata ayıklama bilgilerini yazdır
    print(f"[DEBUG-CREATE] Trendyol'dan gelen yanıt: {json.dumps(response, indent=2)}")
    
    if 'error' in response:
        error_msg = f"Ürün Trendyol'a gönderilirken hata: {response.get('message', 'Bilinmeyen hata')}"
        trendyol_product.status_message = error_msg
        trendyol_product.batch_status = 'failed'
        trendyol_product.save()
        return None, error_msg
    
    if 'batchRequestId' in response:
        batch_id = response['batchRequestId']
        trendyol_product.batch_id = batch_id
        trendyol_product.batch_status = 'pending'
        trendyol_product.status_message = "Trendyol'a gönderildi, işleme alındı"
        trendyol_product.save()
        
        logger.info(f"Product '{trendyol_product.title}' (ID: {trendyol_product.id}) submitted with batch ID: {batch_id}")
        return batch_id, None
    
    error_msg = "Ürün Trendyol'a gönderilirken bilinmeyen hata"
    trendyol_product.status_message = error_msg
    trendyol_product.batch_status = 'failed'
    trendyol_product.save()
    return None, error_msg


def check_product_batch_status(batch_id):
    """
    Toplu istek durumunu kontrol et
    """
    api_client = get_api_client()
    if not api_client:
        return None
    
    return api_client.products.get_batch_request_status(batch_id)


def batch_process_products(products, max_count=None):
    """
    Birden çok ürünü toplu olarak işle
    """
    if not products:
        return 0, 0, []
    
    success_count = 0
    failed_count = 0
    batch_ids = []
    
    # Maksimum ürün sayısını sınırla
    products_to_process = products
    if max_count and max_count > 0:
        products_to_process = products[:max_count]
    
    # Her ürünü işle
    for product in products_to_process:
        batch_id, error = send_product_to_trendyol(product)
        if error:
            failed_count += 1
            logger.error(f"Ürün {product.id} senkronizasyon hatası: {error}")
        else:
            success_count += 1
            batch_ids.append(batch_id)
            # İstekler arasında 0.5 saniye bekle (hız sınırı önlemi)
            time.sleep(0.5)
    
    logger.info(f"Processed {len(products_to_process)}/{len(products)} products: {success_count} succeeded, {failed_count} failed")
    return success_count, failed_count, batch_ids