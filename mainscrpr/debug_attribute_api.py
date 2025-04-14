"""
Trendyol API'den öznitelik çekme işlemini debug eden betik.

Bu betik, belirli kategori ID'leri için Trendyol API'sinden öznitelik isteklerini yapar
ve tüm detayları loglar, böylece API yanıtlarını analiz edebiliriz.

python debug_attribute_api.py
"""

import os
import sys
import json
import logging
import base64
import requests
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolAPIConfig, TrendyolProduct

# Loglama ayarları
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test edilecek kategori ID'leri listesi
TEST_CATEGORIES = [
    524,  # Kadın Üst Giyim
    523,  # Erkek Üst Giyim
    675,  # Çocuk Üst Giyim
    677,  # Bebek Giyim
]

def get_api_auth():
    """API kimlik doğrulama başlıklarını oluştur"""
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not config:
        logger.error("Aktif API yapılandırması bulunamadı")
        return None, None
    
    # Basic Auth için token oluştur
    auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
    
    # Farklı başlık kombinasyonları deneyelim
    headers = {
        "Authorization": f"Basic {auth_token}",
        "User-Agent": f"{config.supplier_id} - SelfIntegration",
        "supplier-id": config.supplier_id,
        "Content-Type": "application/json"
    }
    
    return config.base_url, headers

def test_category_attributes(category_id):
    """Belirli bir kategori için öznitelik bilgisini çek ve logla"""
    base_url, headers = get_api_auth()
    if not base_url or not headers:
        logger.error("API kimlik bilgileri alınamadı")
        return
    
    # Öznitelik endpoint'i
    url = f"{base_url.rstrip('/')}/product/product-categories/{category_id}/attributes"
    
    logger.info(f"Kategori {category_id} için öznitelik isteği yapılıyor: {url}")
    logger.info(f"Kullanılan başlıklar: {headers}")
    
    try:
        response = requests.get(url, headers=headers)
        logger.info(f"API yanıt kodu: {response.status_code}")
        
        # Yanıtı detaylı logla
        if response.status_code == 200:
            data = response.json()
            
            # Toplam öznitelik sayısı
            attr_count = len(data.get('categoryAttributes', []))
            logger.info(f"Kategori {category_id}: {attr_count} adet öznitelik bulundu")
            
            # İlk 5 özniteliği logla
            for i, attr in enumerate(data.get('categoryAttributes', [])[:5]):
                attr_name = attr.get('attribute', {}).get('name', 'Bilinmeyen')
                attr_id = attr.get('attribute', {}).get('id')
                required = attr.get('required', False)
                allow_custom = attr.get('allowCustom', False)
                value_count = len(attr.get('attributeValues', []))
                
                logger.info(f"  {i+1}. Öznitelik: {attr_name} (ID: {attr_id})")
                logger.info(f"     Zorunlu: {required}, Özel değer: {allow_custom}, Değer sayısı: {value_count}")
                
                # Renk özniteliğini özellikle daha detaylı göster
                if attr_name.lower() == 'renk' or attr_id == 348:
                    logger.info(f"     ==== RENK ÖZNİTELİĞİ DETAYI ====")
                    logger.info(f"     Öznitelik ID: {attr_id}")
                    logger.info(f"     Öznitelik Adı: {attr_name}")
                    logger.info(f"     Zorunlu: {required}")
                    logger.info(f"     Değer sayısı: {value_count}")
                    
                    # İlk 10 renk değerini detaylı göster
                    for j, val in enumerate(attr.get('attributeValues', [])[:10]):
                        val_id = val.get('id')
                        val_name = val.get('name')
                        logger.info(f"       {j+1}. Renk: {val_name} (ID: {val_id})")
        
        else:
            logger.error(f"API hatası: {response.status_code} - {response.text}")
            
            # Debug için tam istek/yanıt detaylarını göster
            logger.info(f"İstek URL: {url}")
            logger.info(f"İstek Headers: {headers}")
            logger.info(f"Yanıt Body: {response.text}")
            
    except Exception as e:
        logger.error(f"İstek hatası: {str(e)}")

def check_product_attributes():
    """Veritabanındaki ürünlerin özniteliklerini kontrol et"""
    products = TrendyolProduct.objects.all()[:5]  # Sadece ilk 5 ürünü kontrol et
    
    logger.info(f"=== ÜRÜN ÖZNİTELİKLERİ KONTROLÜ ({products.count()} ürün) ===")
    
    for product in products:
        logger.info(f"Ürün ID: {product.id}, Başlık: {product.title}")
        logger.info(f"Kategori ID: {product.category_id}")
        
        # Öznitelikleri göster
        attributes = product.attributes
        if isinstance(attributes, str):
            try:
                attributes = json.loads(attributes)
            except:
                attributes = []
        
        if not attributes:
            logger.warning(f"  Öznitelik bulunamadı!")
        else:
            logger.info(f"  {len(attributes)} adet öznitelik bulundu:")
            for i, attr in enumerate(attributes):
                # Attribute formatını kontrol et
                if isinstance(attr, str):
                    logger.info(f"  {i+1}. String öznitelik: {attr}")
                    continue
                    
                if isinstance(attr, dict):
                    attr_id = attr.get('attributeId')
                    attr_val_id = attr.get('attributeValueId')
                    logger.info(f"  {i+1}. attributeId: {attr_id}, attributeValueId: {attr_val_id}")
                    
                    # Renk özniteliği mi kontrol et
                    if attr_id == 348 or attr_id == 'color':
                        logger.info(f"    ** Bu bir renk özniteliği **")
                else:
                    logger.info(f"  {i+1}. Bilinmeyen format: {type(attr)}, Değer: {attr}")

def main():
    """Ana işlev"""
    logger.info("=== TRENDYOL API ÖZNİTELİK DEBUG BAŞLIYOR ===")
    
    # API yapılandırmasını kontrol et
    config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if config:
        logger.info(f"API URL: {config.base_url}")
        logger.info(f"API Key: {config.api_key[:4]}...{config.api_key[-4:]}")
        logger.info(f"Supplier ID: {config.supplier_id}")
    else:
        logger.error("API yapılandırması bulunamadı!")
        return
    
    # Önce ürünlerin özniteliklerini kontrol et
    logger.info("\n")
    check_product_attributes()
    
    # Tüm test kategorileri için öznitelikleri çek
    logger.info("\n")
    logger.info("=== KATEGORİ ÖZNİTELİK TESTLERİ ===")
    for category_id in TEST_CATEGORIES:
        logger.info("\n")
        logger.info(f"=== KATEGORİ {category_id} TESTİ ===")
        test_category_attributes(category_id)
    
    logger.info("\n")
    logger.info("=== DEBUG İŞLEMİ TAMAMLANDI ===")

if __name__ == "__main__":
    main()