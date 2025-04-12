"""
Test ürün gönderimi için script.

Bu script, test amaçlı olarak rastgele veri ile Trendyol API'sine ürün gönderimini test eder.
Çalıştırmak için: python manage.py shell < test_product_submission.py
"""

import os
import sys
import logging
import random
import uuid
import datetime
from decimal import Decimal

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

from trendyol.trendyol_api_working import TrendyolAPI
from trendyol.models import TrendyolProduct, TrendyolBrand, TrendyolCategory

# Logging ayarları
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_random_barcode():
    """Benzersiz bir barkod üretir."""
    return f"TST-{str(uuid.uuid4())[:8]}"

def get_random_brand():
    """Rasgele bir marka seçer."""
    brands = list(TrendyolBrand.objects.filter(is_active=True))
    if not brands:
        logger.error("Veritabanında aktif marka bulunamadı!")
        return None, None
    
    brand = random.choice(brands)
    return brand.name, brand.brand_id

def get_random_category():
    """Rasgele bir kategori seçer."""
    categories = list(TrendyolCategory.objects.filter(is_active=True))
    if not categories:
        logger.error("Veritabanında aktif kategori bulunamadı!")
        return None, None
    
    category = random.choice(categories)
    return category.name, category.category_id

def create_test_product():
    """Test için rastgele bir ürün oluşturur ve kaydeder."""
    brand_name, brand_id = get_random_brand()
    category_name, category_id = get_random_category()
    
    if not brand_id or not category_id:
        logger.error("Marka veya kategori bilgisi alınamadı.")
        return None
    
    # Ürün için rasgele isim oluştur
    product_types = ["Tişört", "Pantolon", "Gömlek", "Elbise", "Ayakkabı", "Ceket", "Şort"]
    colors = ["Kırmızı", "Mavi", "Yeşil", "Siyah", "Beyaz", "Gri", "Lacivert"]
    
    product_type = random.choice(product_types)
    color = random.choice(colors)
    
    title = f"{brand_name} {color} {product_type} - Test Ürün"
    description = f"Bu bir test ürünüdür. {title}. Kategori: {category_name}"
    
    barcode = generate_random_barcode()
    
    # Rastgele fiyat (50-500 TL arası)
    price = Decimal(random.randint(5000, 50000)) / Decimal(100)
    
    # Stok miktarı (1-100 arası)
    quantity = random.randint(1, 100)
    
    # Örnek ürün görseli (test amaçlı)
    image_url = "https://img-lcwaikiki.mncdn.com/mnresize/1024/-/pim/productimages/20232/5968312/l_20232-w3ce59z8-ct5_a.jpg"
    
    # Trendyol ürün nesnesi oluştur
    product = TrendyolProduct(
        title=title,
        description=description,
        barcode=barcode,
        product_main_id=barcode,
        stock_code=barcode,
        brand_name=brand_name,
        brand_id=brand_id,
        category_name=category_name,
        category_id=category_id,
        price=price,
        quantity=quantity,
        vat_rate=18,
        currency_type='TRY',
        image_url=image_url,
        attributes=[] # Basit test için boş bırakıyoruz
    )
    
    # Veritabanına kaydet
    product.save()
    logger.info(f"Test ürünü oluşturuldu: {product.title} (Barkod: {product.barcode})")
    
    return product

def submit_product_to_trendyol(product):
    """Ürünü Trendyol API'sine gönderir."""
    if not product:
        logger.error("Gönderilebilecek ürün yok!")
        return None
    
    # API istemcisini başlat
    api = TrendyolAPI()
    
    # Ürünü gönder
    logger.info(f"Ürün Trendyol'a gönderiliyor: {product.title}")
    
    try:
        response = api.submit_product(product)
        
        if 'batchRequestId' in response:
            batch_id = response['batchRequestId']
            logger.info(f"Ürün başarıyla gönderildi! Batch ID: {batch_id}")
            
            # Ürünü güncelle
            product.batch_id = batch_id
            product.batch_status = 'processing'
            product.status_message = f"İşleniyor. Batch ID: {batch_id}"
            product.last_check_time = datetime.datetime.now()
            product.save()
            
            return batch_id
        else:
            logger.error(f"Ürün gönderiminde hata: {response}")
            return None
    except Exception as e:
        logger.error(f"Ürün gönderimi sırasında hata oluştu: {str(e)}")
        return None

def check_batch_status(batch_id):
    """Batch durumunu kontrol eder."""
    if not batch_id:
        logger.error("Kontrol edilecek batch ID yok!")
        return
    
    api = TrendyolAPI()
    
    try:
        logger.info(f"Batch durumu kontrol ediliyor: {batch_id}")
        response = api.get_batch_status(batch_id)
        
        logger.info(f"Batch durum cevabı: {response}")
        return response
    except Exception as e:
        logger.error(f"Batch durum kontrolünde hata: {str(e)}")
        return None

def main():
    """Ana fonksiyon."""
    logger.info("Trendyol ürün gönderimi testi başlatılıyor...")
    
    # Test ürünü oluştur
    product = create_test_product()
    
    # Ürünü Trendyol'a gönder
    batch_id = submit_product_to_trendyol(product)
    
    if batch_id:
        # Batch durumunu kontrol et
        status = check_batch_status(batch_id)
        
        if status:
            logger.info(f"Test tamamlandı. Batch durumu: {status}")
        else:
            logger.error("Batch durumu kontrol edilemedi.")
    else:
        logger.error("Ürün gönderilemedi.")
    
    logger.info("Test tamamlandı.")

if __name__ == "__main__":
    main()
else:
    # Django shell'den çağrıldığında çalıştır
    main()