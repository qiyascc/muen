"""
Basit ürün gönderme testi.

Bu script doğrudan API çağrısı yaparak test ürünü gönderir.
"""

import os
import sys
import base64
import logging
import json
import requests
import uuid
import random

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.models import TrendyolAPIConfig

# Loglama ayarları
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_api_config():
    """Aktif API yapılandırmasını alır."""
    try:
        return TrendyolAPIConfig.objects.filter(is_active=True).first()
    except Exception as e:
        logger.error(f"API yapılandırması alınamadı: {str(e)}")
        return None

def get_headers(config):
    """API istekleri için headers oluşturur."""
    if not config:
        return None
    
    auth_token = config.auth_token
    if not auth_token:
        # Yoksa oluştur
        auth_string = f"{config.api_key}:{config.api_secret}"
        auth_token = base64.b64encode(auth_string.encode()).decode('utf-8')
        
    return {
        'Authorization': f'Basic {auth_token}',
        'Content-Type': 'application/json',
        'User-Agent': config.user_agent or f"{config.seller_id} - SelfIntegration",
        'Accept': '*/*'
    }

def create_simple_product():
    """Basit bir test ürünü oluşturur."""
    barcode = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    
    # Rasgele değerler
    colors = ["Kırmızı", "Siyah", "Mavi", "Yeşil", "Beyaz"]
    product_types = ["Tişört", "Pantolon", "Elbise", "Gömlek", "Ceket"]
    
    color = random.choice(colors)
    product_type = random.choice(product_types)
    
    return {
        "barcode": barcode,
        "title": f"TEST API {color} {product_type}",
        "productMainId": barcode,
        "brandId": 3813, # LC Waikiki brand ID
        "categoryId": 384, # T-shirt category
        "quantity": 100,
        "stockCode": barcode,
        "dimensionalWeight": 1,
        "description": f"Bu bir test ürünüdür. TEST API {color} {product_type}",
        "currencyType": "TRY",
        "listPrice": 150.0,
        "salePrice": 120.0,
        "vatRate": 18,
        "cargoCompanyId": 17,
        "shipmentAddressId": 0,
        "deliveryDuration": 3,
        "images": [
            {
                "url": "https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20232/5968312/l_20232-w3ce59z8-ct5_a.jpg"
            }
        ],
        "attributes": []
    }

def send_test_product():
    """Test ürününü gönderir."""
    config = get_api_config()
    if not config:
        logger.error("API yapılandırması bulunamadı!")
        return
    
    headers = get_headers(config)
    base_url = config.base_url
    seller_id = config.seller_id
    
    # URL oluştur
    url = f"{base_url}/product/sellers/{seller_id}/products"
    logger.info(f"API URL: {url}")
    
    # Ürün oluştur
    product = create_simple_product()
    payload = {"items": [product]}
    
    logger.info(f"Test ürünü hazırlandı: {product['title']} (Barkod: {product['barcode']})")
    
    # isteği gönder
    try:
        logger.info(f"Headers: {headers}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        logger.info(f"HTTP Status: {response.status_code}")
        logger.info(f"Response Body: {response.text}")
        
        if response.status_code < 400:
            logger.info("Ürün başarıyla gönderildi!")
            return response.json()
        else:
            logger.error(f"Ürün gönderiminde hata: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"İstek gönderilirken hata: {str(e)}")
        return None

def test_alternative_url():
    """Alternatif URL test et."""
    config = get_api_config()
    if not config:
        logger.error("API yapılandırması bulunamadı!")
        return
    
    headers = get_headers(config)
    seller_id = config.seller_id
    
    # Alternatif API URL'lerini dene
    base_urls = [
        "https://api.trendyol.com/sapigw",
        "https://apigw.trendyol.com/integration",
        "https://api.trendyol.com/integration"
    ]
    
    product = create_simple_product()
    payload = {"items": [product]}
    
    for base_url in base_urls:
        url = f"{base_url}/product/sellers/{seller_id}/products"
        logger.info(f"Alternatif API URL deneniyor: {url}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            logger.info(f"HTTP Status: {response.status_code}")
            logger.info(f"Response Body: {response.text}")
            
            if response.status_code < 400:
                logger.info(f"Başarılı! Bu URL çalışıyor: {base_url}")
                return response.json()
        except Exception as e:
            logger.error(f"İstek gönderilirken hata: {str(e)}")
            
    return None

def main():
    """Ana fonksiyon."""
    logger.info("Basit API ürün gönderimi testi başlatılıyor...")
    
    result = send_test_product()
    
    if not result:
        logger.info("Alternatif URL'ler deneniyor...")
        result = test_alternative_url()
    
    if result:
        logger.info(f"Test başarılı! Sonuç: {result}")
    else:
        logger.error("Tüm alternatifler başarısız.")
    
    logger.info("Test tamamlandı.")

if __name__ == "__main__":
    main()
else:
    # Django shell'den çağrıldığında çalıştır
    main()