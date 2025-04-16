"""
Sopyo API entegrasyonu

Bu modül LC Waikiki ürünlerini Sopyo platformuna göndermek için gerekli API fonksiyonlarını içerir.
"""

import requests
import json
import logging
from django.conf import settings
from .product_models import Product

logger = logging.getLogger(__name__)

# Sopyo API Base URL
SOPYO_API_BASE_URL = "https://api.sopyo.dev"

class SopyoAPI:
    """Sopyo API ile etkileşim için yardımcı sınıf"""
    
    def __init__(self, api_token=None):
        """
        Sopyo API istemcisini başlat.
        
        Args:
            api_token: Sopyo API token, varsayılan olarak settings.py'den alınır
        """
        self.api_token = api_token or getattr(settings, 'SOPYO_API_TOKEN', '')
        self.access_token = None
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
    def login(self):
        """
        Sopyo API'ye giriş yapıp access token al
        
        Returns:
            bool: Login başarılı ise True, değilse False
        """
        try:
            url = f"{SOPYO_API_BASE_URL}/api/v2/auth/login"
            payload = {
                "api_token": [self.api_token]
            }
            
            response = requests.post(
                url, 
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') and data.get('access_token'):
                    self.access_token = data['access_token']['token']
                    self.headers['Authorization'] = f"Bearer {self.access_token}"
                    logger.info("Sopyo API login başarılı")
                    return True
                else:
                    logger.error(f"Sopyo API login başarısız: {data.get('message', 'Bilinmeyen hata')}")
            else:
                logger.error(f"Sopyo API login başarısız. Status code: {response.status_code}")
            
            return False
        
        except Exception as e:
            logger.error(f"Sopyo API login hatası: {str(e)}")
            return False
    
    def send_product(self, product):
        """
        Ürünü Sopyo API'ye gönder
        
        Args:
            product: Gönderilecek Product model nesnesi
            
        Returns:
            dict: API yanıtı
        """
        if not self.access_token:
            if not self.login():
                return {"status": False, "message": "API login hatası"}
        
        # Stok ve resim kontrolü
        if product.get_total_stock() <= 0:
            logger.warning(f"Ürün '{product.title}' (ID: {product.id}) stokta yok, gönderilmiyor.")
            return {"status": False, "message": "Ürün stokta değil. Stok bilgisi olmayan ürünler gönderilemez."}
            
        if not product.images:
            logger.warning(f"Ürün '{product.title}' (ID: {product.id}) için resim yok, gönderilmiyor.")
            return {"status": False, "message": "Ürün resmi bulunamadı. Resim olmadan ürün gönderilemez."}
        
        try:
            url = f"{SOPYO_API_BASE_URL}/api/v2/products"
            
            # Ürün boyutlarını (stockları) al
            product_sizes = list(product.sizes.all())
            total_stock = product.get_total_stock()
            
            # Başlık düzenleme: Fazla boşlukları temizle ve 150 karaktere sınırla
            cleaned_title = ' '.join(product.title.split())  # Fazla boşlukları kaldır
            if len(cleaned_title) > 149:
                cleaned_title = cleaned_title[:149]  # Uzunsa 149 karaktere kısalt
            
            # Ürün verilerini hazırla
            product_data = {
                "title": cleaned_title,
                "stock_code": product.product_code or f"LCW-{product.id}",
                "stock": total_stock,
                "category_id": 25,  # Varsayılan kategori ID
                "desi": 5,  # Varsayılan desi değeri
                "tax_rate": 10,  # Varsayılan vergi oranı
                "sub_title": f"LC Waikiki {product.color or 'Ürün'}",
                "barcode": product_sizes[0].barcode_list[0] if product_sizes and product_sizes[0].barcode_list else "",
                "barcode_2": product_sizes[1].barcode_list[0] if len(product_sizes) > 1 and product_sizes[1].barcode_list else "",
                "brand": "LC WAIKIKI",
                "description": product.description or f"LC Waikiki {product.title} ürünü",
                "images": product.images[:3] if product.images else [],
                "price1": [
                    {
                        "sale_price": "{:.2f}".format(float(product.price)),
                        "list_price": "{:.2f}".format(float(product.price) * 0.8)  # Liste fiyatını %20 düşük göster
                    }
                ]
            }
            
            # API isteği gönder
            try:
                # Gönderilen veriyi logla (debug için)
                if product.id:  # Ürün ID'sini loglarda göster
                    logger.info(f"Sopyo API'ye gönderilen ürün - ID: {product.id}, Başlık: {product.title}")
                
                # Debug modunda tüm veriyi logla
                logger.debug(f"Sopyo API'ye gönderilen veri detayı: {json.dumps(product_data, indent=4)}")
                
                response = requests.post(
                    url, 
                    headers=self.headers,
                    data=json.dumps(product_data)
                )
                
                if response.status_code == 200 or response.status_code == 201:
                    result = response.json()
                    logger.info(f"Ürün başarıyla Sopyo'ya gönderildi: {product.title}")
                    return result
                else:
                    logger.error(f"[Ürün ID: {product.id}] Sopyo API ürün gönderme hatası. Status code: {response.status_code}")
                    logger.error(f"[Ürün ID: {product.id}] Hata detayı: {response.text}")
                    
                    # Hata mesajını ayrıştır
                    try:
                        error_data = response.json()
                        # Hata mesajını daha okunaklı hale getir
                        hata_mesaji = error_data.get('message', 'Bilinmeyen hata')
                        hata_detay = error_data.get('errors', {})
                        
                        logger.error(f"[Ürün ID: {product.id}] Sopyo hata mesajı: {hata_mesaji}")
                        if hata_detay:
                            logger.error(f"[Ürün ID: {product.id}] Hata detayları: {json.dumps(hata_detay, indent=4)}")
                    except:
                        logger.error(f"[Ürün ID: {product.id}] Hata yanıtı JSON formatında değil")
                    
                    # Token süresi dolmuş olabilir, yeniden login dene
                    if response.status_code == 401:
                        logger.info("Token süresi dolmuş, yeniden login deneniyor...")
                        if self.login():
                            return self.send_product(product)  # Recursive olarak tekrar dene
            except requests.exceptions.RequestException as e:
                logger.error(f"API isteği gönderilirken hata oluştu: {str(e)}")
                
                return {
                    "status": False, 
                    "message": f"API isteği hatası: {str(e)}"
                }
        
        except Exception as e:
            logger.error(f"Sopyo API ürün gönderme hatası: {str(e)}")
            return {"status": False, "message": str(e)}


def send_product_to_sopyo(product_id):
    """
    Belirli bir LC Waikiki ürününü Sopyo'ya gönder
    
    Args:
        product_id: Gönderilecek ürünün ID'si
        
    Returns:
        dict: İşlem sonucu
    """
    try:
        product = Product.objects.get(id=product_id)
        
        if not product.in_stock:
            return {"status": False, "message": "Ürün stokta değil, gönderilmedi"}
        
        api = SopyoAPI()
        result = api.send_product(product)
        
        return result
    
    except Product.DoesNotExist:
        return {"status": False, "message": f"Ürün bulunamadı: {product_id}"}
    
    except Exception as e:
        logger.error(f"Sopyo'ya ürün gönderme hatası: {str(e)}")
        return {"status": False, "message": str(e)}


def send_multiple_products_to_sopyo(product_ids=None, limit=10):
    """
    Birden fazla LC Waikiki ürününü Sopyo'ya gönder
    
    Args:
        product_ids: Gönderilecek ürün ID'leri listesi, None ise stokta olan ürünlerden limit kadar gönderilir
        limit: Maksimum gönderilecek ürün sayısı
        
    Returns:
        dict: İşlem sonucu
    """
    try:
        results = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "details": []
        }
        
        # Ürünleri getir
        if product_ids:
            products = Product.objects.filter(id__in=product_ids, in_stock=True)[:limit]
        else:
            # Stokta olan ve en son eklenen ürünleri getir
            products = Product.objects.filter(in_stock=True).order_by('-timestamp')[:limit]
        
        api = SopyoAPI()
        
        # İlk önce login ol
        if not api.login():
            return {"status": False, "message": "Sopyo API login hatası"}
        
        # Ürünleri gönder
        results["total"] = len(products)
        
        for product in products:
            result = api.send_product(product)
            
            if result.get("status", False):
                results["success"] += 1
            else:
                results["failed"] += 1
            
            results["details"].append({
                "product_id": product.id,
                "title": product.title,
                "result": result
            })
        
        return {
            "status": True,
            "message": f"{results['success']}/{results['total']} ürün başarıyla gönderildi",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Sopyo'ya çoklu ürün gönderme hatası: {str(e)}")
        return {"status": False, "message": str(e)}