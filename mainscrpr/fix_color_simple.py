"""
Basit renk düzeltme betiği.

Bu betik, Trendyol API'sine gönderilen ürünlerde, zorunlu renk özelliğini ekler
veya günceller.

Run this script with: python manage.py shell < fix_color_simple.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct

# Trendyol renk ID'leri (attributeId: 348)
COLOR_ID_MAP = {
    'Beyaz': 686230,
    'Siyah': 686234,
    'Mavi': 686239,
    'Kırmızı': 686241,
    'Pembe': 686247,
    'Yeşil': 686238,
    'Sarı': 686245,
    'Mor': 686246,
    'Gri': 686233,
    'Kahverengi': 686231,
    'Ekru': 686236,
    'Bej': 686228,
    'Lacivert': 686232,
    'Turuncu': 686244,
    'Krem': 686251,
}

def fix_color_attributes_for_all_products():
    """Tüm ürünlere renk düzeltmesi uygula"""
    print("Başarısız ve bekleyen ürünleri kontrol ediyorum...")
    
    # Başarısız ve bekleyen ürünleri al
    failed_products = TrendyolProduct.objects.filter(batch_status='failed')
    pending_products = TrendyolProduct.objects.filter(batch_status='pending')
    
    print(f"{failed_products.count()} başarısız, {pending_products.count()} bekleyen ürün bulundu.")
    
    # Tüm başarısız ürünleri işle
    fixed_count = 0
    
    # Varsayılan renk (Siyah) ve renk ID'si
    default_color = "Siyah"
    default_color_id = COLOR_ID_MAP.get(default_color, 686234)
    
    # Önce başarısız ürünleri işle
    for product in failed_products:
        print(f"Ürün {product.id}: {product.title}")
        print(f"Mevcut durum: {product.batch_status}, Hata: {product.status_message}")
        
        # Attributes'ı düzenle
        if product.attributes is None:
            product.attributes = []
            
        # Renk attribute'u var mı diye kontrol et
        color_attribute_exists = False
        for i, attr in enumerate(product.attributes):
            if isinstance(attr, dict) and attr.get('attributeId') == 348:
                # Var olan renk özelliğini güncelle
                product.attributes[i]['attributeValueId'] = default_color_id
                color_attribute_exists = True
                print(f"Renk özelliği güncellendi: {default_color} (ID: {default_color_id})")
                break
        
        # Renk özelliği yoksa ekle
        if not color_attribute_exists:
            product.attributes.append({
                "attributeId": 348,
                "attributeValueId": default_color_id
            })
            print(f"Renk özelliği eklendi: {default_color} (ID: {default_color_id})")
        
        # Durumu bekliyor olarak ayarla ve kaydet
        product.batch_status = 'pending'
        product.status_message = 'Renk düzeltmesi uygulandı. Yeniden gönderilmeye hazır.'
        product.save()
        fixed_count += 1
    
    # Şimdi bekleyen ürünleri işle
    for product in pending_products:
        # Attributes'ı düzenle
        if product.attributes is None:
            product.attributes = []
            
        # Renk attribute'u var mı diye kontrol et
        color_attribute_exists = False
        for i, attr in enumerate(product.attributes):
            if isinstance(attr, dict) and attr.get('attributeId') == 348:
                color_attribute_exists = True
                break
        
        # Renk özelliği yoksa ekle
        if not color_attribute_exists:
            product.attributes.append({
                "attributeId": 348,
                "attributeValueId": default_color_id
            })
            product.save()
            fixed_count += 1
            print(f"Bekleyen ürün {product.id} için renk özelliği eklendi")
    
    print(f"Toplam {fixed_count} ürün düzeltildi.")

# Betik başlangıcı
print("Renk düzeltme betiği başlatılıyor...")
fix_color_attributes_for_all_products()
print("Betik tamamlandı. Şimdi admin panelinden ürünleri Trendyol'a gönderebilirsiniz.")