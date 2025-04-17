"""
Trendyol kategorileri ve öznitelikleri temizleme betiği.

Bu betik, tüm kategori ve öznitelik bilgilerini veritabanından temizler
böylece herşey API'den gerçek zamanlı olarak alınacaktır.

Çalıştırma şekli:
```
python manage.py shell < trendyol_app/clean_default_data.py
```
"""

import os
import sys
import logging
from django.db import connection

logger = logging.getLogger(__name__)

def clean_cached_categories_and_attributes():
    """Tüm önbelleğe alınmış kategori ve öznitelikleri temizle"""
    with connection.cursor() as cursor:
        try:
            # Varsa, eski uygulama için kategori ve öznitelik tablolarını temizle
            tables_to_clean = [
                'trendyol_trendyolcategory',
                'trendyol_trendyolattribute',
                'trendyol_trendyolattributevalue',
                'trendyol_trendyolcategoryattribute',
            ]
            
            # Tabloları kontrol et ve mevcutsa temizle
            for table in tables_to_clean:
                cursor.execute(f"SELECT to_regclass('{table}')")
                exists = cursor.fetchone()[0]
                if exists:
                    cursor.execute(f"TRUNCATE TABLE {table} CASCADE")
                    logger.info(f"Tablo temizlendi: {table}")
                else:
                    logger.info(f"Tablo bulunamadı: {table}")
            
            # Diğer olası önbellek tablolarını da temizleyelim
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            all_tables = cursor.fetchall()
            
            for table in all_tables:
                table_name = table[0]
                if ('category' in table_name.lower() and 'trendyol' in table_name.lower()) or \
                   ('attribute' in table_name.lower() and 'trendyol' in table_name.lower()):
                    cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")
                    logger.info(f"İlgili tablo temizlendi: {table_name}")
                
            logger.info("Tüm kategori ve öznitelik verileri başarıyla temizlendi")
            print("Tüm kategori ve öznitelik verileri başarıyla temizlendi")
            
        except Exception as e:
            logger.error(f"Veri temizleme işlemi sırasında hata: {str(e)}")
            print(f"HATA: {str(e)}")


def clean_all_default_data():
    """Tüm default/önceden kaydedilmiş verileri temizle"""
    print("Trendyol kategori ve öznitelik verilerini temizleme işlemi başlıyor...")
    clean_cached_categories_and_attributes()
    print("Trendyol kategori ve öznitelik temizleme işlemi tamamlandı.")


if __name__ == "__main__":
    clean_all_default_data()