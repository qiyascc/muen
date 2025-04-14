"""
Trendyol ürünlerini yönetmek için admin eylemleri modülü.

Bu modül, tüm Trendyol admin eylemlerini içerir. TrendyolProductAdmin sınıfının
kod karmaşasını azaltmak için ayrı bir dosyada saklanır.
"""

import logging
from django.utils import timezone
from .api_helpers import submit_product_to_trendyol, prepare_product_for_submission
from .api_client import get_api_client
from .fetch_api_data import fetch_all_categories, fetch_all_brands

logger = logging.getLogger(__name__)

def send_to_trendyol(modeladmin, request, queryset):
    """
    Seçilen ürünleri Trendyol'a gönderir (API odaklı veri işleme).
    Yerel kategorilere ve markalara bağlılığı kaldırır, tüm veriyi API'den gerçek zamanlı alır.
    """
    # API client'ını al
    api_client = get_api_client()
    if not api_client:
        modeladmin.message_user(
            request, 
            "API yapılandırması bulunamadı. Lütfen önce Trendyol API yapılandırmasını oluşturun.", 
            level='error'
        )
        return
    
    # Kategori ve marka verilerini API'den yenile
    try:
        categories = fetch_all_categories(force_refresh=True)
        brands = fetch_all_brands(force_refresh=True)
        
        modeladmin.message_user(
            request, 
            f"API'den {len(categories)} kategori ve {len(brands)} marka alındı.",
            level='info'
        )
    except Exception as e:
        logger.error(f"Error fetching categories and brands: {str(e)}")
        modeladmin.message_user(
            request, 
            f"Kategori ve marka verisi alınırken hata oluştu: {str(e)}", 
            level='error'
        )
    
    # Seçilen ürünleri gönder
    success_count = 0
    error_count = 0
    
    for product in queryset:
        try:
            # Ürünü Trendyol'a gönder
            result = submit_product_to_trendyol(product.id, api_client)
            
            if "success" in result and result["success"]:
                success_count += 1
                modeladmin.message_user(
                    request, 
                    f"'{product.title}' başarıyla gönderildi. Batch ID: {result['batch_id']}", 
                    level='success'
                )
            else:
                error_count += 1
                error_message = result.get("error", "Bilinmeyen hata")
                modeladmin.message_user(
                    request, 
                    f"'{product.title}' gönderilemedi: {error_message}", 
                    level='error'
                )
        except Exception as e:
            error_count += 1
            logger.error(f"Error submitting product {product.id}: {str(e)}")
            modeladmin.message_user(
                request, 
                f"'{product.title}' gönderilemedi: {str(e)}", 
                level='error'
            )
    
    # Sonuçları bildir
    if success_count > 0:
        modeladmin.message_user(
            request, 
            f"{success_count} ürün başarıyla Trendyol'a gönderildi. Durumlarını birkaç dakika içinde kontrol edin.",
            level='success'
        )
    if error_count > 0:
        modeladmin.message_user(
            request, 
            f"{error_count} ürün gönderilemedi. Detaylar için yukarıdaki hata mesajlarına bakın.",
            level='warning'
        )
send_to_trendyol.short_description = "Seçili ürünleri Trendyol'a gönder"

def check_sync_status(modeladmin, request, queryset):
    """
    Seçilen ürünlerin Trendyol senkronizasyon durumunu kontrol eder.
    """
    from . import api_client
    
    count = 0
    for product in queryset:
        if product.batch_id:
            try:
                api_client.check_product_batch_status(product)
                count += 1
            except Exception as e:
                modeladmin.message_user(
                    request, 
                    f"'{product.title}' durumu kontrol edilemedi: {str(e)}", 
                    level='error'
                )
    
    if count:
        modeladmin.message_user(request, f"{count} ürünün durumu başarıyla kontrol edildi.")
    else:
        modeladmin.message_user(
            request, 
            "Batch ID'si olan ürün bulunamadı.", 
            level='warning'
        )
check_sync_status.short_description = "Seçili ürünlerin senkronizasyon durumunu kontrol et"

def retry_failed_products(modeladmin, request, queryset):
    """
    Başarısız ürünleri yeniden dener ve öznitelik sorunlarını düzeltir.
    """
    fixed_count = 0
    success_count = 0
    already_pending_count = 0
    
    for product in queryset:
        try:
            # Zaten bekleyen veya işlenen ürünleri atla
            if product.batch_status in ['pending', 'processing']:
                already_pending_count += 1
                continue
                
            # Mevcut öznitelikleri temizle ve API'nin doğru olanları sağlamasına izin ver
            product.attributes = []
            fixed_count += 1
            
            # Durumu güncelle
            product.batch_status = 'pending'
            product.status_message = 'Düzeltme sonrası yeniden deneme bekliyor'
            product.save()
            
            # API aracılığıyla Trendyol'a gönder
            try:
                result = submit_product_to_trendyol(product.id)
                if "success" in result and result["success"]:
                    success_count += 1
            except Exception as e:
                modeladmin.message_user(
                    request, 
                    f"'{product.title}' için API hatası: {str(e)}", 
                    level='error'
                )
        except Exception as e:
            modeladmin.message_user(
                request, 
                f"'{product.title}' yeniden denenirken hata: {str(e)}", 
                level='error'
            )
    
    # Sonuçları bildir
    message_parts = []
    if fixed_count:
        message_parts.append(f"{fixed_count} ürünün öznitelikleri düzeltildi")
    if success_count:
        message_parts.append(f"{success_count} ürün başarıyla Trendyol'a gönderildi")
    if already_pending_count:
        message_parts.append(f"{already_pending_count} ürün zaten bekleyen/işlenen durumundaydı, atlandı")
        
    if message_parts:
        modeladmin.message_user(request, ". ".join(message_parts) + ".")
    else:
        modeladmin.message_user(
            request, 
            "Yeniden denemeye uygun ürün bulunamadı.", 
            level='warning'
        )
retry_failed_products.short_description = "Başarısız ürünleri yeniden dene (öznitelikleri düzelt)"

def refresh_from_api(modeladmin, request, queryset):
    """
    Seçilen ürünlerin kategori ve marka bilgilerini Trendyol API'den yeniler.
    """
    updated_count = 0
    
    # Kategori ve marka verilerini al
    try:
        categories = fetch_all_categories(force_refresh=True)
        brands = fetch_all_brands(force_refresh=True)
        
        modeladmin.message_user(
            request, 
            f"API'den {len(categories)} kategori ve {len(brands)} marka alındı.",
            level='info'
        )
    except Exception as e:
        modeladmin.message_user(
            request, 
            f"Kategori ve marka verisi alınırken hata oluştu: {str(e)}", 
            level='error'
        )
        return
    
    # Seçilen ürünleri güncelle
    for product in queryset:
        try:
            # Öznitelikleri temizle
            product.attributes = []
            
            # Durumu güncelle
            product.batch_status = 'pending'
            product.status_message = 'API bilgileriyle yenilendi'
            product.updated_at = timezone.now()
            product.save()
            
            updated_count += 1
        except Exception as e:
            modeladmin.message_user(
                request, 
                f"'{product.title}' yenilenirken hata: {str(e)}", 
                level='error'
            )
    
    if updated_count:
        modeladmin.message_user(
            request, 
            f"{updated_count} ürün API bilgileriyle yenilendi. Şimdi 'Seçili ürünleri Trendyol'a gönder' işlemini kullanabilirsiniz.",
            level='success'
        )
    else:
        modeladmin.message_user(
            request, 
            "Hiçbir ürün yenilenemedi.", 
            level='warning'
        )
refresh_from_api.short_description = "Trendyol API'den ürün bilgilerini yenile"

def refresh_product_data(modeladmin, request, queryset):
    """
    Ürün verilerini LC Waikiki kaynağından yeniler (varsa).
    """
    from lcwaikiki.product_models import Product as LCWaikikiProduct
    
    updated_count = 0
    not_linked_count = 0
    attribute_fixed_count = 0
    
    for product in queryset:
        try:
            # Ürünün LC Waikiki ile bağlantısını kontrol et
            if not product.lcwaikiki_product_id:
                # Barcode veya stock code ile eşleşen LC Waikiki ürünü bulmaya çalış
                matching_product = None
                if product.barcode:
                    matching_product = LCWaikikiProduct.objects.filter(
                        product_code=product.barcode
                    ).first()
                
                if not matching_product and product.stock_code:
                    matching_product = LCWaikikiProduct.objects.filter(
                        product_code=product.stock_code
                    ).first()
                
                if matching_product:
                    # Ürünleri bağla
                    product.lcwaikiki_product = matching_product
                    modeladmin.message_user(
                        request, 
                        f"'{product.title}' ürünü LC Waikiki ürünü '{matching_product.title}' ile bağlandı", 
                        level='success'
                    )
                else:
                    not_linked_count += 1
                    continue
            
            # Bağlı LC Waikiki ürününü al
            lcw_product = product.lcwaikiki_product
            if lcw_product:
                # Ürün verilerini güncelle
                product.title = lcw_product.title or product.title
                product.description = lcw_product.description or product.description
                product.price = lcw_product.price or product.price
                product.image_url = lcw_product.images[0] if lcw_product.images else product.image_url
                
                # Öznitelikler API tarafından otomatik olarak ayarlanıyor
                # Mevcut öznitelikleri temizle
                product.attributes = []
                attribute_fixed_count += 1
                
                # Zaman damgasını güncelle
                product.updated_at = timezone.now()
                product.save()
                updated_count += 1
            
        except Exception as e:
            modeladmin.message_user(
                request, 
                f"'{product.title}' yenilenirken hata: {str(e)}", 
                level='error'
            )
    
    # Sonuçları bildir
    if updated_count:
        modeladmin.message_user(
            request, 
            f"{updated_count} ürün başarıyla yenilendi. {attribute_fixed_count} ürünün öznitelikleri düzeltildi.",
            level='success'
        )
    if not_linked_count:
        modeladmin.message_user(
            request, 
            f"{not_linked_count} ürün için LC Waikiki verisi bulunamadı.", 
            level='warning'
        )
refresh_product_data.short_description = "LC Waikiki'den ürün verilerini yenile"