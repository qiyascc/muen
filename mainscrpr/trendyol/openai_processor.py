"""
OpenAI işlemcisi modülü

Bu modül, Trendyol kategori özniteliklerini işlemek ve ürün bilgilerini OpenAI API
kullanarak zenginleştirmek için fonksiyonlar içerir.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

from loguru import logger
from openai import OpenAI
from django.utils import timezone

from trendyol.models import TrendyolAPIConfig, TrendyolProduct, TrendyolBrand
from trendyol.api_client import get_api_client

# OpenAI istemcisini yapılandır
def get_openai_client():
    """OpenAI istemcisini oluştur ve döndür"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY bulunamadı")
        return None
    
    return OpenAI(api_key=api_key)

def get_category_details(category_id: int) -> Dict:
    """
    Belirli bir kategori için tüm detayları ve öznitelikleri getir
    """
    client = get_api_client()
    if not client:
        logger.error("Trendyol API istemcisi alınamadı")
        return {"error": "API client not available"}
    
    try:
        # Kategori bilgilerini al
        category_info = client.categories.get_categories()
        
        # Kategori özniteliklerini al
        category_attributes = client.categories.get_category_attributes(category_id)
        
        # Sonuçları birleştir
        result = {
            "category_id": category_id,
            "category_info": category_info,
            "category_attributes": category_attributes
        }
        
        logger.info(f"Kategori {category_id} detayları alındı")
        return result
    
    except Exception as e:
        logger.error(f"Kategori detayları alınırken hata: {str(e)}")
        return {"error": str(e)}

def analyze_product_with_openai(product: TrendyolProduct, category_attrs: Dict) -> Dict:
    """
    OpenAI API kullanarak ürün bilgilerini analiz et ve 
    kategori için gerekli öznitelikleri belirle
    """
    client = get_openai_client()
    if not client:
        logger.error("OpenAI istemcisi oluşturulamadı")
        return {"error": "OpenAI client not available"}
    
    try:
        # Ürün bilgilerini hazırla
        product_info = {
            "title": product.title,
            "description": product.description,
            "brand": product.brand_name,
            "price": float(product.price) if product.price else 0,
            "color": product.color,
            "images": [product.image_url] if product.image_url else []
        }
        
        if product.additional_images:
            if isinstance(product.additional_images, list):
                product_info["images"].extend(product.additional_images)
            elif isinstance(product.additional_images, str):
                try:
                    additional = json.loads(product.additional_images)
                    if isinstance(additional, list):
                        product_info["images"].extend(additional)
                except json.JSONDecodeError:
                    pass
        
        # Kategori özniteliklerini hazırla
        attributes_info = []
        if category_attrs and "categoryAttributes" in category_attrs:
            for attr in category_attrs.get("categoryAttributes", []):
                if "attribute" in attr and "name" in attr["attribute"]:
                    attr_info = {
                        "id": attr["attribute"]["id"],
                        "name": attr["attribute"]["name"],
                    }
                    
                    # Olası değerleri ekle
                    if "attributeValues" in attr and attr["attributeValues"]:
                        attr_info["values"] = [
                            {"id": val["id"], "name": val["name"]} 
                            for val in attr["attributeValues"]
                        ]
                    
                    attributes_info.append(attr_info)
        
        # OpenAI'ya gönderilecek prompt hazırla
        system_message = """
        Sen bir e-ticaret ürün uzmanısın. Verilen ürün bilgilerine göre Trendyol pazaryeri için 
        ürünün özelliklerini değerlendireceksin ve gerekli öznitelikleri belirleyeceksin.
        
        Ürün başlığını marka adı olmadan düzenleyeceksin.
        Ürün tanımını daha detaylı ve SEO odaklı hale getireceksin.
        Kategori için gerekli öznitelikleri, verilen ürün bilgilerine göre belirleyeceksin.
        
        Yanıtını JSON formatında, aşağıdaki şekilde ver:
        {
            "processed_title": "Düzenlenmiş ürün başlığı",
            "processed_description": "Geliştirilmiş ürün açıklaması",
            "attributes": [
                {
                    "attributeId": 123,
                    "attributeValueId": 456
                }
            ]
        }
        """
        
        # OpenAI API'sine gönder
        prompt = f"""
        Ürün Bilgileri:
        {json.dumps(product_info, ensure_ascii=False, indent=2)}
        
        Kategori Öznitelikleri:
        {json.dumps(attributes_info, ensure_ascii=False, indent=2)}
        
        Lütfen bu ürün için Trendyol pazaryerine uygun başlık, açıklama ve öznitelikleri belirle.
        Ürünün rengini, boyutunu ve diğer özelliklerini doğru şekilde eşleştir.
        Öznitelik ID'lerini ve değer ID'lerini yukarıdaki listeden seç.
        """
        
        logger.info("OpenAI API'sine istek gönderiliyor")
        response = client.chat.completions.create(
            model="gpt-4o",  # gpt-4o en yeni model
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Yanıtı işle
        try:
            result = json.loads(response.choices[0].message.content)
            logger.info("OpenAI işlemesi başarılı")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"OpenAI yanıtı JSON formatında değil: {e}")
            return {"error": "Invalid JSON response from OpenAI"}
    
    except Exception as e:
        logger.error(f"OpenAI analizi sırasında hata: {str(e)}")
        return {"error": str(e)}

def prepare_product_with_ai(product: TrendyolProduct) -> Tuple[Dict, Dict]:
    """
    OpenAI kullanarak ürünü hazırla ve API'ye göndermek için gerekli verileri döndür
    """
    # Kategori ID'sini al veya belirle
    from trendyol.api_client import find_best_category_match
    category_id = product.category_id or find_best_category_match(product)
    
    if not category_id:
        logger.error(f"Ürün {product.id} için kategori belirlenemedi")
        return {"error": "Category not found"}, {}
    
    # Kategori detaylarını al
    category_attrs = get_category_details(category_id).get("category_attributes", {})
    
    # OpenAI ile ürünü analiz et
    ai_result = analyze_product_with_openai(product, category_attrs)
    
    if "error" in ai_result:
        logger.error(f"OpenAI analizi başarısız: {ai_result['error']}")
        return ai_result, {}
    
    # Marka ID'sini bul
    from trendyol.api_client import find_best_brand_match
    brand_id = product.brand_id or find_best_brand_match(product)
    
    if not brand_id:
        logger.error(f"Ürün {product.id} için marka belirlenemedi")
        return {"error": "Brand not found"}, {}
    
    # Ürün verilerini hazırla
    # Normalize whitespace - replace multiple spaces with single space
    normalized_title = " ".join(ai_result.get("processed_title", product.title).split())
    
    # Limit title to 100 characters
    title = normalized_title[:100] if normalized_title and len(normalized_title) > 100 else normalized_title
    
    # Görüntüleri hazırla
    image_urls = []
    if product.image_url:
        image_urls.append(product.image_url)

    if product.additional_images:
        if isinstance(product.additional_images, list):
            image_urls.extend(product.additional_images)
        elif isinstance(product.additional_images, str):
            try:
                additional = json.loads(product.additional_images)
                if isinstance(additional, list):
                    image_urls.extend(additional)
            except json.JSONDecodeError:
                pass
    
    # Ürün verilerini hazırla
    product_data = {
        "barcode": product.barcode,
        "title": title,
        "productMainId": product.product_main_id or product.barcode,
        "brandId": brand_id,
        "categoryId": category_id,
        "stockCode": product.stock_code or product.barcode,
        "quantity": product.quantity or 10,
        "description": ai_result.get("processed_description", product.description or product.title),
        "currencyType": product.currency_type or "TRY",
        "listPrice": float(product.price or 0),
        "salePrice": float(product.price or 0),
        "vatRate": 10,
        "cargoCompanyId": 17,
        "attributes": ai_result.get("attributes", []),
    }
    
    # Görüntüleri ekle
    if image_urls:
        product_data["images"] = [{"url": url} for url in image_urls if url]
    
    # Sayısal değerleri düzelt
    for key in ["quantity", "listPrice", "salePrice", "vatRate"]:
        if key in product_data and product_data[key] is not None:
            try:
                if key in ["listPrice", "salePrice"]:
                    product_data[key] = float(product_data[key])
                else:
                    product_data[key] = int(product_data[key])
            except (ValueError, TypeError):
                if key in ["listPrice", "salePrice"]:
                    product_data[key] = 0.0
                else:
                    product_data[key] = 0
    
    # Brand ve Category ID'lerini integer yap
    for key in ["brandId", "categoryId"]:
        if key in product_data and product_data[key] is not None:
            try:
                product_data[key] = int(product_data[key])
            except (ValueError, TypeError):
                logger.error(f"Invalid {key}: {product_data[key]}")
                return {"error": f"Invalid {key}: must be an integer"}, {}
    
    return ai_result, product_data

def create_trendyol_product_with_ai(product: TrendyolProduct) -> Optional[str]:
    """
    OpenAI ile zenginleştirilmiş ürünü Trendyol'a gönder
    Returns the batch ID if successful, None otherwise.
    """
    logger.info(f"OpenAI ile ürün oluşturma başlatılıyor: ID={product.id}, Başlık={product.title}")
    
    # API istemcisini al
    client = get_api_client()
    if not client:
        error_message = "No active Trendyol API configuration found"
        logger.error(error_message)
        product.batch_status = 'failed'
        product.status_message = error_message
        product.save()
        return None
    
    try:
        # OpenAI ile ürünü işle
        ai_result, product_data = prepare_product_with_ai(product)
        
        if "error" in ai_result:
            error_message = f"Error preparing product with AI: {ai_result['error']}"
            logger.error(error_message)
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None
        
        # Zorunlu alanları kontrol et
        required_fields = [
            'barcode', 'title', 'productMainId', 'brandId', 'categoryId',
            'quantity'
        ]
        missing_fields = [
            field for field in required_fields
            if field not in product_data or product_data[field] is None
        ]
        
        if missing_fields:
            error_message = f"Product data missing required fields: {', '.join(missing_fields)}"
            logger.error(error_message)
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None
        
        # Ürünü Trendyol'a gönder
        logger.info(f"OpenAI ile işlenmiş ürün Trendyol'a gönderiliyor: {product.title}")
        response = client.products.create_products([product_data])
        
        # Yanıt kontrolü
        if not response:
            error_message = "No response from Trendyol API"
            logger.error(error_message)
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None

        # API hata kontrolü
        if isinstance(response, dict) and response.get('error') is True:
            error_message = response.get('message', 'Unknown API error')
            error_details = response.get('details', '')
            
            # Detaylı hata bilgilerini logla
            logger.error(f"API error for product ID {product.id}: {error_message}")
            if error_details:
                logger.error(f"Error details: {error_details}")
            
            # Hata bilgilerini ürüne kaydet
            full_error = error_message
            if error_details:
                full_error += f" - {error_details}"
            
            product.batch_status = 'failed'
            product.status_message = full_error[:500]  # Çok uzunsa kısalt
            product.save()
            return None
        
        # Standart yanıt formatındaki hataları kontrol et
        if isinstance(response, dict) and 'errors' in response and response['errors']:
            errors = response['errors']
            if isinstance(errors, list):
                error_message = f"Failed to create product: {errors[0].get('message', 'Unknown error')}"
            else:
                error_message = f"Failed to create product: {errors}"
            
            logger.error(error_message)
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None
        
        # Batch ID kontrolü
        if 'batchRequestId' not in response:
            error_message = "Failed to create product on Trendyol: No batch request ID returned"
            logger.error(error_message)
            product.batch_status = 'failed'
            product.status_message = error_message
            product.save()
            return None
        
        # Başarı durumunda
        batch_id = response.get('batchRequestId')
        logger.info(f"OpenAI ile işlenmiş ürün gönderildi. Batch ID: {batch_id}")
        
        # Ürünü güncelle
        product.batch_id = batch_id
        product.batch_status = 'processing'
        product.status_message = "Product creation with AI initiated"
        product.last_check_time = timezone.now()
        product.save()
        
        return batch_id
    
    except Exception as e:
        error_message = f"Error creating product with AI: {str(e)}"
        logger.error(error_message)
        product.batch_status = 'failed'
        product.status_message = error_message
        product.save()
        return None