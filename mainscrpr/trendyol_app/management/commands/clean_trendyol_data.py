"""
Django yönetim komutu: Trendyol önbellek verilerini temizleme

Bu komut, tüm Trendyol kategorileri ve öznitelikleri için veritabanı önbelleğini temizler,
böylece tüm veriler gerçek zamanlı olarak API'den alınır.
"""

from django.core.management.base import BaseCommand
from django.db import connection
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Tüm kategori ve öznitelik önbelleğini temizleyerek gerçek zamanlı API sorgusu yapmaya zorlar'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Trendyol kategori ve öznitelik verilerini temizleme işlemi başlıyor...'))
        
        try:
            with connection.cursor() as cursor:
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
                        self.stdout.write(self.style.SUCCESS(f"Tablo temizlendi: {table}"))
                    else:
                        self.stdout.write(self.style.NOTICE(f"Tablo bulunamadı: {table}"))
                
                # Diğer olası önbellek tablolarını da temizleyelim
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                all_tables = cursor.fetchall()
                
                for table in all_tables:
                    table_name = table[0]
                    if ('category' in table_name.lower() and 'trendyol' in table_name.lower()) or \
                       ('attribute' in table_name.lower() and 'trendyol' in table_name.lower()):
                        cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")
                        self.stdout.write(self.style.SUCCESS(f"İlgili tablo temizlendi: {table_name}"))
                        
            self.stdout.write(self.style.SUCCESS('Tüm kategori ve öznitelik verileri başarıyla temizlendi'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Veri temizleme işlemi sırasında hata: {str(e)}'))
            logger.error(f"Veri temizleme işlemi sırasında hata: {str(e)}")