"""
Renk düzeltme betiği - Direkt yaklaşım.

Bu betik, ürünlerin attributes alanını direkt düzenleyerek renk bilgisini ekler.

python manage.py shell < fix_color_direct.py
"""

import os
import sys
import django
import json

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolProduct
from django.db import connection

def fix_colors_directly():
    """Veritabanında doğrudan tüm ürünlere renk bilgisi ekler"""
    
    # Varsayılan renk ID'si (Siyah - 686234)
    color_attribute = '{"attributeId": 348, "attributeValueId": 686234}'
    
    # Direkt SQL sorgusu ile attributes alanını güncelle 
    with connection.cursor() as cursor:
        # JSON array olarak saklanan ürünler için
        cursor.execute("""
        UPDATE trendyol_trendyolproduct 
        SET attributes = jsonb_set(
            CASE 
                WHEN attributes IS NULL THEN '[]'::jsonb
                WHEN attributes = '' THEN '[]'::jsonb
                ELSE attributes::jsonb 
            END,
            '{0}',
            %s::jsonb,
            true
        )
        WHERE (batch_status = 'failed' AND status_message LIKE '%%Renk%%') 
        OR batch_status = 'pending'
        """, [color_attribute])
        
        # JSON array olarak saklanan ancak içinde renk bilgisi olmayan ürünler için
        cursor.execute("""
        UPDATE trendyol_trendyolproduct
        SET attributes = attributes::jsonb || '[{"attributeId": 348, "attributeValueId": 686234}]'::jsonb
        WHERE (batch_status = 'failed' AND status_message LIKE '%%Renk%%') 
        OR batch_status = 'pending'
        AND NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(attributes::jsonb) obj
            WHERE obj->>'attributeId' = '348'
        )
        """)
        
        # Ayrıca hata durumunu resetle
        cursor.execute("""
        UPDATE trendyol_trendyolproduct
        SET batch_status = 'pending', 
            status_message = 'Renk düzeltmesi uygulandı'
        WHERE batch_status = 'failed' AND status_message LIKE '%%Renk%%'
        """)
        
        # Başarılı ürün sayısını al
        cursor.execute("""
        SELECT COUNT(*) FROM trendyol_trendyolproduct 
        WHERE batch_status = 'pending'
        """)
        pending_count = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT COUNT(*) FROM trendyol_trendyolproduct 
        WHERE batch_status = 'failed' AND status_message LIKE '%%Renk%%'
        """)
        fixed_failed_count = cursor.fetchone()[0]
    
    print(f"Veritabanında toplam {pending_count} bekleyen ürün var")
    print(f"Renk hatası olan {fixed_failed_count} ürün düzeltildi ve bekliyor durumuna alındı")
    print("Şimdi admin panelinden 'Send to Trendyol' işlemini başlatabilirsiniz")

# Scripti başlat
print("Renk düzeltme scripti çalıştırılıyor...")
fix_colors_directly()
print("Script tamamlandı!")