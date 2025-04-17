"""
Manuel ürün senkronizasyon testi

Bu betik, LCWaikiki'den bir ürünü alıp Trendyol'a aktarmayı test eder.
Token limiti sorununu gidermek için optimize edilmiş GPT-4o sorguları kullanır.

Çalıştırma:
python manage.py shell < manual_sync_test.py
"""

import os
import sys
import django
import logging
import time
from django.utils import timezone

# Django ortamını yükle
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mainscrpr.settings')
django.setup()

# Modelleri içe aktar
from lcwaikiki.product_models import Product
from trendyol_app.models import TrendyolProduct, TrendyolAPIConfig
from trendyol_app.services import TrendyolAPI, TrendyolProductManager

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_single_product():
    """Tek bir ürünü LCWaikiki'den Trendyol'a aktar"""
    # Aktif API yapılandırmasını kontrol et
    api_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not api_config:
        logger.error("Aktif Trendyol API yapılandırması bulunamadı")
        return
    
    # Stok sayısı 1'den büyük olan ilk ürünü al
    product = Product.objects.filter(stock_count__gt=1).first()
    if not product:
        logger.error("Aktarılacak ürün bulunamadı")
        return
    
    logger.info(f"Ürün seçildi: {product.title} (ID: {product.id}, URL: {product.url})")
    
    # Ürünün zaten Trendyol'a aktarılıp aktarılmadığını kontrol et
    existing = TrendyolProduct.objects.filter(
        product_main_id=str(product.id)
    ).first()
    
    if existing:
        logger.warning(f"Bu ürün zaten Trendyol'a aktarılmış (Batch ID: {existing.batch_id})")
        return existing
    
    # Trendyol ürünü oluştur
    try:
        trendyol_product = TrendyolProduct()
        trendyol_product.title = product.title[:150]  # Max 150 karakter
        trendyol_product.description = product.description or f"{product.title} - LCWaikiki"
        trendyol_product.barcode = f"LCW{product.id}"
        trendyol_product.product_main_id = str(product.id)
        trendyol_product.stock_code = f"LC{product.id}"
        trendyol_product.brand_name = "LC Waikiki"
        trendyol_product.category_name = product.category or "Giyim"
        trendyol_product.quantity = product.stock_count
        trendyol_product.price = float(product.price)
        trendyol_product.sale_price = float(product.sale_price or product.price)
        trendyol_product.vat_rate = 18
        trendyol_product.currency_type = "TRY"
        trendyol_product.image_url = product.image_url
        trendyol_product.batch_status = "pending"
        trendyol_product.save()
        
        logger.info(f"Trendyol ürünü oluşturuldu: {trendyol_product.title} (ID: {trendyol_product.id})")
        
        # Trendyol API'ye gönder
        api = TrendyolAPI(api_config)
        product_manager = TrendyolProductManager(api)
        
        logger.info("Ürün Trendyol'a gönderiliyor...")
        batch_id = product_manager.create_product(trendyol_product)
        
        if batch_id:
            trendyol_product.batch_id = batch_id
            trendyol_product.batch_status = "processing"
            trendyol_product.status_message = "Product creation initiated"
            trendyol_product.last_check_time = timezone.now()
            trendyol_product.save()
            
            logger.info(f"Ürün başarıyla Trendyol'a gönderildi (Batch ID: {batch_id})")
            return trendyol_product
        else:
            logger.error("Ürün gönderimi başarısız: Batch ID alınamadı")
            return None
        
    except Exception as e:
        logger.error(f"Ürün aktarımı sırasında hata: {str(e)}")
        return None

def check_batch_status(product):
    """Ürünün batch durumunu kontrol et"""
    if not product or not product.batch_id:
        logger.error("Geçerli bir ürün veya batch ID yok")
        return
    
    api_config = TrendyolAPIConfig.objects.filter(is_active=True).first()
    if not api_config:
        logger.error("Aktif Trendyol API yapılandırması bulunamadı")
        return
    
    api = TrendyolAPI(api_config)
    product_manager = TrendyolProductManager(api)
    
    try:
        logger.info(f"Batch durumu kontrol ediliyor (Batch ID: {product.batch_id})...")
        batch_status = product_manager.check_batch_status(product.batch_id)
        
        if batch_status:
            status = batch_status.get('status', 'processing').lower()
            logger.info(f"Batch durumu: {status}")
            
            if status == 'failed':
                message = batch_status.get('failureReasons', 'Unknown error')
                if isinstance(message, list):
                    message = '; '.join([reason.get('message', 'Unknown') for reason in message])
                logger.error(f"Hata mesajı: {message}")
            
            # Ürünün durumunu güncelle
            product.batch_status = status
            product.status_message = message if status == 'failed' else None
            product.last_check_time = timezone.now()
            product.save()
            
            return batch_status
    except Exception as e:
        logger.error(f"Batch durumu kontrolü sırasında hata: {str(e)}")
        return None

def main():
    """Ana test fonksiyonu"""
    logger.info("LCWaikiki -> Trendyol manuel senkronizasyon testi başlatılıyor...")
    
    # Ürünü senkronize et
    product = sync_single_product()
    
    if product and product.batch_id:
        # Batch durumunu kontrol et (birkaç kez dene)
        for i in range(3):
            logger.info(f"Batch durumu kontrol ediliyor (Deneme {i+1}/3)...")
            status = check_batch_status(product)
            
            # Eğer başarılı veya başarısız ise döngüden çık
            if product.batch_status in ['success', 'failed']:
                break
                
            # 5 saniye bekle ve tekrar dene
            time.sleep(5)
    
    # Son durumu göster
    if product:
        logger.info(f"Final durum: {product.batch_status}")
        if product.status_message:
            logger.info(f"Mesaj: {product.status_message}")
    
    logger.info("Test tamamlandı!")

if __name__ == "__main__":
    main()