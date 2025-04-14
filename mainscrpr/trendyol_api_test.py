"""
Trendyol API için kategori özelliklerini ve zorunlu alanları test eder.

Bu betik, belirli bir kategori ID için tüm özellikleri getirir ve zorunlu olanları
gösterir. Bu bilgi, veri gönderirken zorunlu alanları doğru formatta sağlamak için kullanılır.

python manage.py shell < trendyol_api_test.py
"""

import os
import sys
import django
import json
import requests
import base64

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolAPIConfig, TrendyolCategory
from django.db import connection

def get_api_auth():
    """Trendyol API için kimlik doğrulama başlıklarını alır"""
    config = TrendyolAPIConfig.objects.first()
    if not config:
        print("API yapılandırması bulunamadı!")
        return None, None
    
    auth_token = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_token}",
        "User-Agent": f"{config.supplier_id} - SelfIntegration",
        "Content-Type": "application/json"
    }
    
    return config.base_url, headers

def get_category_attributes(category_id):
    """Belirli bir kategori için tüm özellikleri alır"""
    base_url, headers = get_api_auth()
    if not base_url or not headers:
        return None
    
    # Kategori özelliklerini al
    url = f"{base_url.rstrip('/')}/product/product-categories/{category_id}/attributes"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    except Exception as e:
        print(f"Kategori özellikleri alınırken hata oluştu: {str(e)}")
        return None

def find_color_attribute(attributes):
    """Özellikler arasından renk özniteliğini bulur"""
    color_attribute = None
    
    for attr in attributes.get('categoryAttributes', []):
        if attr.get('name', '').lower() == 'renk':
            color_attribute = attr
            break
    
    return color_attribute

def fix_product_color(product_id, category_id, color_value):
    """Belirli bir ürün için renk özniteliğini düzeltir"""
    attributes = get_category_attributes(category_id)
    if not attributes:
        print(f"ID {category_id} için kategori özellikleri alınamadı")
        return False
    
    color_attribute = find_color_attribute(attributes)
    if not color_attribute:
        print(f"ID {category_id} kategorisinde renk özniteliği bulunamadı")
        return False
    
    # Renk değerini seçin
    color_value_id = None
    attribute_id = color_attribute.get('id')
    
    for value in color_attribute.get('attributeValues', []):
        if value.get('name', '').lower() == color_value.lower():
            color_value_id = value.get('id')
            break
    
    if not color_value_id:
        print(f"'{color_value}' için geçerli bir renk değeri bulunamadı")
        # İlk renk değerini kullan
        if color_attribute.get('attributeValues'):
            color_value_id = color_attribute['attributeValues'][0]['id']
            print(f"Varsayılan renk kullanılıyor: {color_attribute['attributeValues'][0]['name']} (ID: {color_value_id})")
        else:
            return False
    
    # SQL ile ürünü güncelle
    with connection.cursor() as cursor:
        # Önce attributes alanını kontrol et ve güncelle
        cursor.execute("""
        UPDATE trendyol_trendyolproduct
        SET attributes = 
            CASE 
                WHEN attributes IS NULL THEN '[{"attributeId": %s, "attributeValueId": %s}]'
                WHEN attributes = '' THEN '[{"attributeId": %s, "attributeValueId": %s}]'
                ELSE (
                    SELECT jsonb_agg(
                        CASE 
                            WHEN elem->>'attributeId' = %s THEN jsonb_set(elem, '{attributeValueId}', %s::jsonb)
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(
                        CASE 
                            WHEN jsonb_typeof(attributes::jsonb) = 'array' THEN attributes::jsonb
                            ELSE '[]'::jsonb
                        END
                    ) AS elem
                )::text
            END,
        batch_status = 'pending',
        status_message = 'Renk düzeltildi'
        WHERE id = %s
        """, [attribute_id, color_value_id, attribute_id, color_value_id, str(attribute_id), str(color_value_id), product_id])
        
        # Kontrol et, eğer renk eklenemedi ise yeni ekle
        cursor.execute("""
        SELECT 
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM jsonb_array_elements(attributes::jsonb) obj
                    WHERE obj->>'attributeId' = %s
                ) THEN 1
                ELSE 0
            END
        FROM trendyol_trendyolproduct
        WHERE id = %s
        """, [str(attribute_id), product_id])
        
        has_color = cursor.fetchone()[0]
        
        if not has_color:
            cursor.execute("""
            UPDATE trendyol_trendyolproduct
            SET attributes = attributes::jsonb || '[{"attributeId": %s, "attributeValueId": %s}]'::jsonb
            WHERE id = %s
            """, [attribute_id, color_value_id, product_id])
            
    print(f"Ürün {product_id} için renk başarıyla güncellendi: Attribute ID {attribute_id}, Value ID {color_value_id}")
    return True

def get_categories():
    """Tüm kategorileri listeler"""
    categories = TrendyolCategory.objects.all()
    print(f"Toplam {categories.count()} kategori bulundu")
    
    for category in categories[:10]:  # İlk 10 kategoriyi göster
        print(f"ID: {category.category_id}, Ad: {category.name}")
    
    return categories

def test_category_attributes(category_id=2356):
    """Belirli bir kategori için tüm özellikleri listeler"""
    attributes = get_category_attributes(category_id)
    
    if not attributes:
        print("Kategori özellikleri alınamadı")
        return
    
    print(f"Kategori {category_id} için toplam {len(attributes.get('categoryAttributes', []))} özellik var\n")
    
    for attribute in attributes.get('categoryAttributes', []):
        required = attribute.get('required', False)
        allowCustom = attribute.get('allowCustom', False)
        
        # Sadece zorunlu özellikleri göster
        if required:
            print(f"Özellik: {attribute.get('name')} (ID: {attribute.get('id')})")
            print(f"  Zorunlu: {'Evet' if required else 'Hayır'}")
            print(f"  Özel değer: {'İzinli' if allowCustom else 'İzinli değil'}")
            
            # Değerleri göster (varsa)
            values = attribute.get('attributeValues', [])
            if values:
                print("  Değerler:")
                for value in values[:5]:  # İlk 5 değeri göster
                    print(f"    - {value.get('name')} (ID: {value.get('id')})")
                
                if len(values) > 5:
                    print(f"    ... ve {len(values) - 5} daha")
            
            print()

def examine_failed_products():
    """Başarısız ürünleri ve hatalarını listeler"""
    failed_products = []
    
    with connection.cursor() as cursor:
        cursor.execute("""
        SELECT id, title, category_id, batch_status, status_message, attributes
        FROM trendyol_trendyolproduct
        WHERE batch_status = 'failed' AND status_message LIKE '%Renk%'
        """)
        
        columns = [col[0] for col in cursor.description]
        failed_products = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    print(f"Renk hatası olan {len(failed_products)} ürün bulundu\n")
    
    for product in failed_products:
        print(f"Ürün ID: {product['id']}")
        print(f"Başlık: {product['title']}")
        print(f"Kategori ID: {product['category_id']}")
        print(f"Durum: {product['batch_status']}")
        print(f"Hata: {product['status_message']}")
        print(f"Öznitelikler: {product['attributes']}")
        print()
        
        # Bu ürün için rengi düzelt
        if product['category_id']:
            fix_product_color(product['id'], product['category_id'], "Siyah")

def main():
    """Ana test fonksiyonu"""
    print("Trendyol API Kategori ve Öznitelik Testi")
    print("="*50)
    
    # Önce başarısız ürünleri ve hatalarını incele
    examine_failed_products()
    
    # Kullanıcıdan kategori ID'si iste
    category_id = input("Başka bir kategori ID'si girmek ister misiniz? (Varsayılan: 2356): ") or "2356"
    category_id = int(category_id)
    
    # Kategori özelliklerini göster
    test_category_attributes(category_id)

# Betiği başlat
if __name__ == "__main__":
    main()
else:
    # Django shell ile çalıştırılırken
    main()