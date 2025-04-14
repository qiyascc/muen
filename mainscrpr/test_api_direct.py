"""
Trendyol API bağlantısını direkt test eden script.

Bu betik, requests kütüphanesini kullanarak doğrudan Trendyol API'sine bağlanır
ve temel kimlik doğrulama ile çeşitli endpoint formatlarını test eder.

python manage.py shell < test_api_direct.py
"""

import os
import sys
import base64
import requests
import json
import logging
from urllib.parse import quote

# Basit loglama ayarları
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trendyol_api_test')

# API kimlik bilgileri ve yapılandırması
API_KEY = "qSohKkLKPWwDeSKjwz8R"
API_SECRET = "yYF3Ycl9B6Vjs77q3MhE"
SELLER_ID = "535623"
BASE_URLS = [
    "https://apigw.trendyol.com",
    "https://api.trendyol.com"
]

def test_endpoint(base_url, endpoint, params=None):
    """Belirli bir endpoint'i test et"""
    url = f"{base_url}/{endpoint.lstrip('/')}"
    
    # Basic Authentication için base64 token oluştur
    auth_token = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_token}",
        "User-Agent": f"{SELLER_ID} - SelfIntegration",
        "Content-Type": "application/json"
    }
    
    logger.info(f"Testing endpoint: {url}")
    logger.info(f"Headers: {headers}")
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        logger.info(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"Success! Response length: {len(response.text)} chars")
            return True, response.text
        else:
            logger.error(f"Error: {response.status_code} - {response.text}")
            return False, response.text
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        return False, str(e)

def main():
    """Test various Trendyol API endpoints with different URL formats"""
    # Tüm base URL'leri test et
    for base_url in BASE_URLS:
        logger.info(f"\n===== Testing with base URL: {base_url} =====")
        
        # Test 1: Basit brands endpoint
        logger.info("\n----- Test 1: Brands API -----")
        endpoints = [
            f"brands",
            f"suppliers/{SELLER_ID}/brands",
            f"sapigw/suppliers/{SELLER_ID}/brands",
            f"integration/suppliers/{SELLER_ID}/brands",
            f"integration/product/sellers/{SELLER_ID}/brands",
        ]
        
        for endpoint in endpoints:
            success, response = test_endpoint(base_url, endpoint)
            if success:
                logger.info(f"✓ Successful endpoint: {endpoint}")
                break
                
        # Test 2: Belirli bir marka arama
        logger.info("\n----- Test 2: Brand Search -----")
        brand_name = "LCWaikiki"
        encoded_brand = quote(brand_name)
        
        endpoints = [
            f"brands/by-name?name={encoded_brand}",
            f"suppliers/{SELLER_ID}/brands/by-name?name={encoded_brand}",
            f"sapigw/suppliers/{SELLER_ID}/brands/by-name?name={encoded_brand}",
            f"integration/suppliers/{SELLER_ID}/brands/by-name?name={encoded_brand}",
        ]
        
        for endpoint in endpoints:
            success, response = test_endpoint(base_url, endpoint)
            if success:
                logger.info(f"✓ Successful endpoint: {endpoint}")
                break
                
        # Test 3: Kategoriler
        logger.info("\n----- Test 3: Categories API -----")
        endpoints = [
            f"product-categories",
            f"suppliers/{SELLER_ID}/product-categories",
            f"sapigw/suppliers/{SELLER_ID}/product-categories",
            f"integration/product/sellers/{SELLER_ID}/product-categories",
            f"integration/suppliers/{SELLER_ID}/product-categories",
        ]
        
        for endpoint in endpoints:
            success, response = test_endpoint(base_url, endpoint)
            if success:
                logger.info(f"✓ Successful endpoint: {endpoint}")
                break
                
        # Test 4: Bir kategorinin özellikleri
        logger.info("\n----- Test 4: Category Attributes -----")
        category_id = 2356  # Erkek giyim
        
        endpoints = [
            f"product-categories/{category_id}/attributes",
            f"suppliers/{SELLER_ID}/product-categories/{category_id}/attributes",
            f"sapigw/suppliers/{SELLER_ID}/product-categories/{category_id}/attributes",
            f"integration/product/sellers/{SELLER_ID}/product-categories/{category_id}/attributes",
        ]
        
        for endpoint in endpoints:
            success, response = test_endpoint(base_url, endpoint)
            if success:
                logger.info(f"✓ Successful endpoint: {endpoint}")
                break

if __name__ == "__main__":
    # Loglama sonuçlarını ekrana yazdır
    main()
    print("API testi tamamlandı.")