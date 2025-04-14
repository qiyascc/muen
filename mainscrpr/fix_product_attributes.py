"""
Script to fix all product attributes to use the correct numeric format.

This script will update all TrendyolProduct instances to ensure their attributes
are using the correct format with numeric IDs, especially for color attributes.

Run this script with: python manage.py shell < fix_product_attributes.py
"""

import os
import django
import json

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

def main():
    """Fix attributes format to use numeric IDs for all products"""
    
    # Tüm TrendyolProduct nesnelerini al
    products = TrendyolProduct.objects.all()
    print(f"Toplam {products.count()} ürün işlenecek")
    
    fixed_count = 0
    for product in products:
        should_update = False
        
        # attributes formatı düzeltilmedi mi?
        if product.attributes is None:
            product.attributes = []
            should_update = True
        
        # String olarak saklanmış attributes var mı?
        if isinstance(product.attributes, str) and product.attributes.strip():
            try:
                product.attributes = json.loads(product.attributes)
                should_update = True
            except json.JSONDecodeError:
                product.attributes = []
                should_update = True
        
        # Dictionary olarak saklanmış attributes var mı? (Örn: {'color': 'Mavi'})
        if isinstance(product.attributes, dict):
            old_attributes = product.attributes.copy()
            new_attributes = []
            
            # Renk bilgisi varsa, doğru formata dönüştür
            if 'color' in old_attributes:
                color_name = old_attributes['color']
                color_id = COLOR_ID_MAP.get(color_name, 686234)  # Bulunamazsa Siyah kullan
                new_attributes.append({
                    'attributeId': 348,
                    'attributeValueId': color_id
                })
            
            # Diğer öznitelikler varsa ekle
            for key, value in old_attributes.items():
                if key != 'color':
                    new_attributes.append({
                        'attributeId': key,
                        'attributeValueId': value
                    })
            
            product.attributes = new_attributes
            should_update = True
        
        # Attributes bir liste mi?
        if isinstance(product.attributes, list):
            # Renk özniteliği var mı?
            has_color = False
            for attr in product.attributes:
                if isinstance(attr, dict) and attr.get('attributeId') == 348:
                    has_color = True
                    break
            
            # Renk yoksa ve başlıkta renk bilgisi varsa ekle
            if not has_color:
                color_name = None
                
                # Başlıktan renk tahmini yap
                title = product.title.lower() if product.title else ""
                for color in COLOR_ID_MAP.keys():
                    if color.lower() in title:
                        color_name = color
                        break
                
                # Renk bulunamadıysa varsayılan olarak Siyah ekle
                if not color_name:
                    color_name = "Siyah"
                
                color_id = COLOR_ID_MAP.get(color_name, 686234)
                product.attributes.append({
                    'attributeId': 348,
                    'attributeValueId': color_id
                })
                should_update = True
        
        # Eğer değişiklik yapıldıysa kaydet
        if should_update:
            # API tarafından reddedildiyse sıfırla
            if product.batch_status == 'failed' and 'Renk' in product.status_message:
                product.batch_status = 'pending'
                product.status_message = 'Attributes format fixed'
            
            product.save()
            fixed_count += 1
            print(f"Ürün {product.id} düzeltildi: {product.attributes}")
    
    print(f"Toplam {fixed_count} ürün güncellendi.")

if __name__ == "__main__":
    print("TrendyolProduct attributes düzeltme işlemi başlatılıyor...")
    main()
    print("İşlem tamamlandı!")
else:
    # Django shell ile çalıştırılırken
    print("TrendyolProduct attributes düzeltme işlemi başlatılıyor...")
    main()
    print("İşlem tamamlandı!")