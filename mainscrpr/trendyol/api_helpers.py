"""
Trendyol API helper fonksiyonları.

Bu modül, Trendyol API client'ı ile entegre çalışan 
ve tüm ürün dönüştürme ve API işlemlerini gerçekleştiren
yardımcı fonksiyonları içerir.
"""

import logging
import json
import time
import re
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union

from django.utils import timezone
from django.core.cache import cache

from .models import TrendyolProduct
from .fetch_api_data import (
    get_brand_id_by_name,
    ensure_product_has_required_attributes,
    get_color_attribute_id,
    get_color_value_id,
    fetch_all_categories,
    fetch_all_brands
)

logger = logging.getLogger(__name__)

def submit_product_to_trendyol(product_id, api_client=None):
    """
    Ürünü Trendyol'a gönderir.
    
    Args:
        product_id: TrendyolProduct ID'si
        api_client: Trendyol API client nesnesi (isteğe bağlı)
        
    Returns:
        dict: API yanıtı
    """
    from .api_client import get_api_client
    
    try:
        # Ürünü veritabanından al
        product = TrendyolProduct.objects.get(id=product_id)
    except TrendyolProduct.DoesNotExist:
        logger.error(f"Product with ID {product_id} not found")
        return {"error": f"Product with ID {product_id} not found"}
    
    # API client alınmadıysa, otomatik al
    if not api_client:
        api_client = get_api_client()
        if not api_client:
            error_msg = "Could not get Trendyol API client"
            logger.error(error_msg)
            product.batch_status = "failed"
            product.status_message = error_msg
            product.save()
            return {"error": error_msg}
    
    # Ürünü hazırla
    try:
        prepared_product = prepare_product_for_submission(product)
        logger.info(f"Product '{product.title}' (ID: {product.id}) prepared for submission")
        
        # Tüm özniteliklere sahip olduğundan emin ol
        prepared_product = ensure_product_has_required_attributes(
            prepared_product, 
            product.category_id
        )
        
        print(f"[DEBUG-CREATE] Trendyol'a gönderilecek ürün: {json.dumps(prepared_product)}")
    except Exception as e:
        error_msg = f"Error preparing product: {str(e)}"
        logger.error(error_msg)
        product.batch_status = "failed"
        product.status_message = error_msg
        product.save()
        return {"error": error_msg}
    
    # Ürünü gönder
    try:
        logger.info(f"Submitting product '{product.title}' (ID: {product.id}) to Trendyol")
        response = api_client.products.create_products([prepared_product])
        print(f"[DEBUG-CREATE] Trendyol'dan gelen yanıt: {json.dumps(response)}")
        
        # Yanıtı kontrol et
        if "error" in response:
            error_msg = f"API error: {response.get('message', 'Unknown API error')}"
            logger.error(error_msg)
            product.batch_status = "failed"
            product.status_message = error_msg
            product.save()
            return response
        
        # Batch ID'yi kaydet
        if "batchRequestId" in response:
            batch_id = response["batchRequestId"]
            logger.info(f"Product '{product.title}' (ID: {product.id}) submitted with batch ID: {batch_id}")
            
            # Ürünü güncelle
            product.batch_request_id = batch_id
            product.batch_status = "processing"
            product.status_message = f"Batch request submitted with ID: {batch_id}"
            product.last_update = timezone.now()
            product.save()
            
            return {"success": True, "batch_id": batch_id}
        else:
            error_msg = "No batch ID in API response"
            logger.error(error_msg)
            product.batch_status = "failed"
            product.status_message = error_msg
            product.save()
            return {"error": error_msg}
    
    except Exception as e:
        error_msg = f"Error submitting product: {str(e)}"
        logger.error(error_msg)
        product.batch_status = "failed"
        product.status_message = error_msg
        product.save()
        return {"error": error_msg}

def prepare_product_for_submission(product):
    """
    TrendyolProduct nesnesini Trendyol API'ye göndermek için hazırlar.
    
    Args:
        product: TrendyolProduct nesnesi
        
    Returns:
        dict: Trendyol API gönderimi için hazırlanmış ürün verisi
    """
    # Markayı al
    brand_id = product.brand_id
    if not brand_id and product.brand_name:
        brand_id = get_brand_id_by_name(product.brand_name)
        # Brand ID'yi kaydet
        if brand_id:
            product.brand_id = brand_id
            product.save(update_fields=['brand_id'])
    
    if not brand_id:
        logger.warning(f"Could not determine brand ID for product {product.id} ({product.title})")
        # Varsayılan bir marka kullan (LC Waikiki için uygun bir ID)
        brand_id = 102  # LC Waikiki
        
    # Ürünü API formatına dönüştür
    api_product = {
        'barcode': product.barcode,
        'title': product.title,
        'productMainId': product.product_code,
        'brandId': brand_id,
        'categoryId': product.category_id,
        'listPrice': float(product.list_price),
        'salePrice': float(product.sale_price),
        'vatRate': int(product.vat_rate or 18),  # Varsayılan KDV oranı: %18
        'stockCode': product.stock_code or product.barcode,
        'stockQuantity': int(product.stock or 0),
        'shipmentAddressId': product.shipment_address_id,
        'returningAddressId': product.returning_address_id,
        'cargoCompanyId': product.cargo_company_id or 17,  # Varsayılan kargo şirketi: Aras Kargo
        'images': product.images or [],
        'description': product.description or '',
    }
    
    # Öznitelikleri kontrol et ve doğru formatla
    if product.attributes:
        # Eğer string ise JSON'a çevir
        if isinstance(product.attributes, str):
            try:
                attributes = json.loads(product.attributes)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in attributes for product {product.id}")
                attributes = []
        else:
            attributes = product.attributes
        
        # Özniteliklerin doğru formatta olduğundan emin ol (liste olmalı)
        if isinstance(attributes, list):
            api_product['attributes'] = attributes
        elif isinstance(attributes, dict):
            # Renk bilgisi var mı kontrol et
            # Dict'in attributeId ve value ikileri içerip içermediğini kontrol et
            attributes_list = []
            if 'color' in attributes:
                # Renk bilgisini doğru formata dönüştür
                color_attr_id = get_color_attribute_id(product.category_id)
                color_value_id = get_color_value_id(product.category_id, attributes['color'])
                
                attributes_list.append({
                    'attributeId': color_attr_id,
                    'attributeValueId': color_value_id
                })
            
            # Diğer öznitelikler varsa ekle
            for key, value in attributes.items():
                if key != 'color':
                    attributes_list.append({
                        'attributeId': int(key) if key.isdigit() else key,
                        'attributeValueId': value
                    })
            
            api_product['attributes'] = attributes_list
        else:
            # Boş liste kullan
            api_product['attributes'] = []
    else:
        # Boş liste kullan
        api_product['attributes'] = []
    
    # Diğer isteğe bağlı alanlar
    if product.gender:
        api_product['gender'] = product.gender
    if product.color_code:
        api_product['colorCode'] = product.color_code
    if product.dimension_unit:
        api_product['dimensionUnit'] = product.dimension_unit
    if product.weight:
        api_product['weight'] = float(product.weight)
    if product.weight_unit:
        api_product['weightUnit'] = product.weight_unit
    
    return api_product

def process_batch_status(product, batch_status_response):
    """
    Trendyol'dan gelen batch durum yanıtını işler ve TrendyolProduct nesnesini günceller.
    
    Args:
        product: TrendyolProduct nesnesi
        batch_status_response: Trendyol API'den gelen batch durum yanıtı
        
    Returns:
        bool: İşlem başarılı mı?
    """
    try:
        # Yanıtı kontrol et
        if "error" in batch_status_response:
            error_msg = f"API error: {batch_status_response.get('message', 'Unknown API error')}"
            logger.error(error_msg)
            product.batch_status = "failed"
            product.status_message = error_msg
            product.save()
            return False
        
        # Batch durumunu al
        status = batch_status_response.get('status', '')
        
        # İşleme durumunu güncelle
        if status == "COMPLETED":
            # Başarılı mı kontrol et
            items = batch_status_response.get('items', [])
            if items:
                # İlk öğeyi kontrol et (birden fazla öğe olabilir)
                item = items[0]
                item_status = item.get('status', '')
                
                if item_status == "SUCCESS":
                    product.batch_status = "success"
                    product.status_message = "Successfully submitted to Trendyol"
                else:
                    product.batch_status = "failed"
                    # Hata mesajlarını al
                    failure_reasons = item.get('failureReasons', [])
                    if failure_reasons:
                        product.status_message = ". ".join(failure_reasons)
                    else:
                        product.status_message = f"Failed with status: {item_status}"
            else:
                product.batch_status = "failed"
                product.status_message = "No items in batch response"
        elif status == "PROCESSING":
            product.batch_status = "processing"
            product.status_message = "Batch is still processing"
        else:
            product.batch_status = "failed"
            product.status_message = f"Unknown batch status: {status}"
        
        # Son güncelleme tarihini ayarla
        product.last_update = timezone.now()
        product.save()
        
        logger.info(f"Updated product {product.id} with batch status: {product.batch_status}")
        return product.batch_status == "success"
    
    except Exception as e:
        error_msg = f"Error processing batch status: {str(e)}"
        logger.error(error_msg)
        product.batch_status = "failed"
        product.status_message = error_msg
        product.save()
        return False