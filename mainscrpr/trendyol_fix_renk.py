"""
Trendyol ürünleri için renk hatası düzeltme betiği.

Bu betik, "Renk" özelliği eksik diye başarısız olmuş Trendyol ürünlerini
düzeltmek için tasarlanmıştır. Erkek-Kadın giyim ürünleri için uygun Siyah renk ID'sini ekler.

python manage.py shell < trendyol_fix_renk.py
"""

import os
import django
import json
from django.db import connection

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

def fix_color_for_failed_products():
    """Renk hatası vermiş tüm ürünlere Siyah renk değerini ekler"""
    
    # Erkek giyim için Siyah renk ID'si: 686234
    # Çocuk ürünleri için Siyah renk ID'si: 686234
    # Kadın giyim için Siyah renk ID'si: 686234
    # Renk attribute ID'si her zaman 348
    
    with connection.cursor() as cursor:
        # String/text olarak tanımlı ise jsonb array'e çevir
        cursor.execute("""
        UPDATE trendyol_trendyolproduct
        SET attributes = 
            CASE 
                WHEN attributes IS NULL THEN '[]'::jsonb
                WHEN attributes = '' THEN '[]'::jsonb
                WHEN jsonb_typeof(attributes::jsonb) <> 'array' THEN '[]'::jsonb
                ELSE attributes::jsonb
            END
        WHERE batch_status = 'failed' AND status_message LIKE '%Renk%'
        """)
        
        # Renk ekle / güncelle
        cursor.execute("""
        WITH failed_products AS (
            SELECT id FROM trendyol_trendyolproduct
            WHERE batch_status = 'failed' AND status_message LIKE '%Renk%'
        )
        UPDATE trendyol_trendyolproduct p
        SET attributes = COALESCE(
                (
                    SELECT jsonb_agg(
                        CASE 
                            WHEN elem->>'attributeId' = '348' THEN jsonb_set(elem, '{attributeValueId}', '686234')
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(attributes::jsonb) AS elem
                ),
                jsonb_build_array(jsonb_build_object('attributeId', 348, 'attributeValueId', 686234))
            ),
            batch_status = 'pending',
            status_message = 'Renk düzeltildi (Siyah-686234)'
        FROM failed_products
        WHERE p.id = failed_products.id
        """)
        
        # Renk eklenmiş mi kontrol et, eğer yoksa ekle
        cursor.execute("""
        UPDATE trendyol_trendyolproduct
        SET attributes = attributes::jsonb || jsonb_build_array(jsonb_build_object('attributeId', 348, 'attributeValueId', 686234))
        WHERE batch_status = 'failed' 
          AND status_message LIKE '%Renk%'
          AND NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements(attributes::jsonb) elem
            WHERE elem->>'attributeId' = '348'
          )
        """)
        
        # Etkilenen toplam ürün sayısını al
        cursor.execute("""
        SELECT COUNT(*) 
        FROM trendyol_trendyolproduct
        WHERE batch_status = 'pending' 
          AND status_message = 'Renk düzeltildi (Siyah-686234)'
        """)
        
        fixed_count = cursor.fetchone()[0]
    
    print(f"Toplam {fixed_count} ürün düzeltildi.")
    print("Şimdi admin panelinden ürünleri Trendyol'a gönderebilirsiniz.")

# Betiği başlat
if __name__ == "__main__":
    print("Renk düzeltme betiği başlatılıyor...")
    fix_color_for_failed_products()
    print("Betik tamamlandı.")
else:
    # Django shell ile çalıştırılırken
    print("Renk düzeltme betiği başlatılıyor...")
    fix_color_for_failed_products()
    print("Betik tamamlandı.")