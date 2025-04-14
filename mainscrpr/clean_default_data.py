"""
Veritabanındaki default/yerel kategori ve öznitelikleri temizleyen script.

Bu script, tüm kategori ve öznitelik bilgilerini veritabanından temizler
böylece herşey API'den gerçek zamanlı olarak alınacaktır.

python manage.py shell < clean_default_data.py
"""

import os
import django
from django.db import connection

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

from trendyol.models import TrendyolCategory, TrendyolBrand
from trendyol.models import TrendyolAPIConfig

def clean_all_default_data():
    """Tüm default/önceden kaydedilmiş verileri temizle"""
    
    # Kategorileri sil
    categories_count = TrendyolCategory.objects.count()
    TrendyolCategory.objects.all().delete()
    print(f"✓ {categories_count} kategori silindi.")
    
    # Markaları sil
    brands_count = TrendyolBrand.objects.count()
    TrendyolBrand.objects.all().delete()
    print(f"✓ {brands_count} marka silindi.")
    
    # Başarısız ürünleri bekliyor durumuna getir
    with connection.cursor() as cursor:
        cursor.execute("""
        UPDATE trendyol_trendyolproduct
        SET batch_status = 'pending',
            status_message = 'API yenileme sonrası yeniden işlenecek'
        WHERE batch_status = 'failed'
        """)
        
        updated_rows = cursor.rowcount
    
    print(f"✓ {updated_rows} başarısız ürün bekliyor durumuna getirildi.")
    
    # API yapılandırmasını kontrol et
    configs = TrendyolAPIConfig.objects.all()
    if configs.exists():
        print("\nMevcut API yapılandırması:")
        for config in configs:
            print(f"- Tedarikçi ID: {config.supplier_id}")
            print(f"- API Temel URL: {config.base_url}")
            
            # API URL'sini güncelle
            if config.base_url != "https://api.trendyol.com/sapigw":
                config.base_url = "https://api.trendyol.com/sapigw"
                config.save()
                print("✓ API URL güncellendi: https://api.trendyol.com/sapigw")
    else:
        print("! API yapılandırması bulunamadı. Lütfen yeni bir yapılandırma ekleyin.")
        
    print("\nTüm default veriler temizlendi. Şimdi sistem API'den gerçek zamanlı veri alacak.")

if __name__ == "__main__":
    print("Default veri temizleme işlemi başlatılıyor...")
    clean_all_default_data()
    print("İşlem tamamlandı.")
else:
    # Django shell içerisinden çalıştırıldığında
    print("Default veri temizleme işlemi başlatılıyor...")
    clean_all_default_data()
    print("İşlem tamamlandı.")