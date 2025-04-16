"""
URL configuration for mainscrpr project.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import HttpResponse

def xml_api_docs(request):
    """Simple XML API documentation view"""
    content = """
    <html>
    <head>
        <title>LC Waikiki XML API Dokümantasyonu</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #003366; }
            h2 { color: #006699; margin-top: 30px; }
            h3 { color: #0099cc; }
            .endpoint { background-color: #f0f0f0; padding: 10px; margin: 10px 0; border-left: 5px solid #006699; }
            .params { margin-left: 20px; }
            .param { margin: 5px 0; }
            .param-name { font-weight: bold; }
            .param-desc { margin-left: 10px; }
            pre { background-color: #f8f8f8; padding: 10px; border: 1px solid #ddd; overflow: auto; }
        </style>
    </head>
    <body>
        <h1>LC Waikiki XML API Dokümantasyonu</h1>
        <p>Bu dokümanda LC Waikiki ürünleri ve mağazaları için sağlanan XML API endpoints hakkında bilgiler bulunmaktadır.</p>
        
        <h2>Genel Bilgiler</h2>
        <p>Tüm endpoint'ler XML formatında veri döndürür. Varsayılan şehir ID'si 870 (Sakarya) olarak belirlenmiştir.</p>
        
        <h2>Ürün API Endpoints</h2>
        
        <div class="endpoint">
            <h3>Ürün Listesi</h3>
            <p><code>GET /lcwaikiki/xml/products/</code></p>
            <p>Ürün listesini XML formatında döndürür.</p>
            <div class="params">
                <div class="param">
                    <span class="param-name">limit</span>
                    <span class="param-desc">Maksimum döndürülecek ürün sayısı (varsayılan: 50)</span>
                </div>
                <div class="param">
                    <span class="param-name">offset</span>
                    <span class="param-desc">Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)</span>
                </div>
                <div class="param">
                    <span class="param-name">category</span>
                    <span class="param-desc">Kategori filtresi (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">in_stock</span>
                    <span class="param-desc">Sadece stokta olanlar için "1" (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">min_price</span>
                    <span class="param-desc">Minimum fiyat filtresi (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">max_price</span>
                    <span class="param-desc">Maksimum fiyat filtresi (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">city_id</span>
                    <span class="param-desc">Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)</span>
                </div>
            </div>
        </div>
        
        <div class="endpoint">
            <h3>Ürün Detayı</h3>
            <p><code>GET /lcwaikiki/xml/products/{product_id}/</code></p>
            <p>Belirli bir ürünün detayını XML formatında döndürür.</p>
            <div class="params">
                <div class="param">
                    <span class="param-name">city_id</span>
                    <span class="param-desc">Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)</span>
                </div>
                <div class="param">
                    <span class="param-name">include_stores</span>
                    <span class="param-desc">Mağaza stok bilgilerini dahil etmek için "1" (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">include_description</span>
                    <span class="param-desc">HTML açıklamayı dahil etmek için "1" (opsiyonel, varsayılan: 1)</span>
                </div>
            </div>
        </div>
        
        <div class="endpoint">
            <h3>Ürün Stok Durumu</h3>
            <p><code>GET /lcwaikiki/xml/products/{product_id}/inventory/</code></p>
            <p>Belirli bir ürünün stok durumunu XML formatında döndürür.</p>
            <div class="params">
                <div class="param">
                    <span class="param-name">city_id</span>
                    <span class="param-desc">Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)</span>
                </div>
                <div class="param">
                    <span class="param-name">size_id</span>
                    <span class="param-desc">Beden ID filtresi (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">min_stock</span>
                    <span class="param-desc">Minimum stok filtresi (opsiyonel)</span>
                </div>
            </div>
        </div>
        
        <div class="endpoint">
            <h3>Ürün Arama</h3>
            <p><code>GET /lcwaikiki/xml/products/search/</code></p>
            <p>Ürünleri arama ve XML formatında döndürür.</p>
            <div class="params">
                <div class="param">
                    <span class="param-name">q</span>
                    <span class="param-desc">Arama sorgusu (başlık, kategori, renk içerisinde arama yapar)</span>
                </div>
                <div class="param">
                    <span class="param-name">category</span>
                    <span class="param-desc">Kategori filtresi (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">color</span>
                    <span class="param-desc">Renk filtresi (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">min_price</span>
                    <span class="param-desc">Minimum fiyat filtresi (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">max_price</span>
                    <span class="param-desc">Maksimum fiyat filtresi (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">in_stock</span>
                    <span class="param-desc">Sadece stokta olanlar için "1" (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">city_id</span>
                    <span class="param-desc">Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)</span>
                </div>
                <div class="param">
                    <span class="param-name">limit</span>
                    <span class="param-desc">Maksimum döndürülecek ürün sayısı (varsayılan: 20)</span>
                </div>
                <div class="param">
                    <span class="param-name">offset</span>
                    <span class="param-desc">Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)</span>
                </div>
                <div class="param">
                    <span class="param-name">size</span>
                    <span class="param-desc">Beden filtresi (opsiyonel)</span>
                </div>
            </div>
            
            <h4>POST ile Gelişmiş Arama</h4>
            <p><code>POST /lcwaikiki/xml/products/search/</code></p>
            <p>JSON gövdesi ile gelişmiş arama parametreleri gönderilir.</p>
            <pre>
{
    "query": "arama terimi",
    "filters": {
        "category": "kategori",
        "color": "renk",
        "price": {
            "min": 100,
            "max": 500
        },
        "sizes": ["M", "L"],
        "in_stock": true
    },
    "city_id": "870",
    "pagination": {
        "limit": 20,
        "offset": 0
    },
    "sort": "price_asc"  // price_asc, price_desc, newest, popularity
}
            </pre>
        </div>
        
        <div class="endpoint">
            <h3>Ürün İstatistikleri</h3>
            <p><code>GET /lcwaikiki/xml/products/statistics/</code></p>
            <p>Ürün istatistiklerini XML formatında döndürür.</p>
            <div class="params">
                <div class="param">
                    <span class="param-name">city_id</span>
                    <span class="param-desc">Şehir ID filtresi (opsiyonel, varsayılan: Sakarya=870)</span>
                </div>
            </div>
        </div>
        
        <h2>Mağaza API Endpoints</h2>
        
        <div class="endpoint">
            <h3>Mağaza Listesi</h3>
            <p><code>GET /lcwaikiki/xml/stores/</code></p>
            <p>Mağaza listesini XML formatında döndürür.</p>
            <div class="params">
                <div class="param">
                    <span class="param-name">city_id</span>
                    <span class="param-desc">Şehir ID filtresi (opsiyonel, varsayılan: Sakarya=870)</span>
                </div>
                <div class="param">
                    <span class="param-name">has_stock</span>
                    <span class="param-desc">Belirli stok ID'si için stok bulunan mağazaları filtrele (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">limit</span>
                    <span class="param-desc">Maksimum döndürülecek mağaza sayısı (varsayılan: 100)</span>
                </div>
                <div class="param">
                    <span class="param-name">offset</span>
                    <span class="param-desc">Kaç mağaza atlanacak (sayfalama için) (varsayılan: 0)</span>
                </div>
            </div>
        </div>
        
        <div class="endpoint">
            <h3>Mağaza Detayı</h3>
            <p><code>GET /lcwaikiki/xml/stores/{store_id}/</code></p>
            <p>Belirli bir mağazanın detayını XML formatında döndürür.</p>
            <div class="params">
                <div class="param">
                    <span class="param-name">include_products</span>
                    <span class="param-desc">Stokta bulunan ürünleri dahil etmek için "1" (opsiyonel)</span>
                </div>
                <div class="param">
                    <span class="param-name">limit</span>
                    <span class="param-desc">Maksimum döndürülecek ürün sayısı (varsayılan: 20)</span>
                </div>
                <div class="param">
                    <span class="param-name">offset</span>
                    <span class="param-desc">Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)</span>
                </div>
                <div class="param">
                    <span class="param-name">min_stock</span>
                    <span class="param-desc">Minimum stok filtresi (opsiyonel, varsayılan: 1)</span>
                </div>
            </div>
        </div>
        
        <h2>Şehir API Endpoints</h2>
        
        <div class="endpoint">
            <h3>Şehir Listesi</h3>
            <p><code>GET /lcwaikiki/xml/cities/</code></p>
            <p>Şehir listesini XML formatında döndürür.</p>
        </div>
        
        <h2>Örnek XML Yanıtı</h2>
        <pre>
&lt;?xml version="1.0" encoding="UTF-8" standalone="yes"?&gt;
&lt;products timestamp="2025-04-16T11:50:00.000000" version="1.0" total_count="120" limit="10" offset="0" city_id="870"&gt;
  &lt;product id="1" code="ABC123" in_stock="true"&gt;
    &lt;url&gt;https://www.lcw.com/product1&lt;/url&gt;
    &lt;title&gt;Erkek Slim Fit Jean Pantolon&lt;/title&gt;
    &lt;category&gt;Erkek / Jean / Slim Fit&lt;/category&gt;
    &lt;color&gt;Mavi&lt;/color&gt;
    &lt;price&gt;299.99&lt;/price&gt;
    &lt;discount_ratio&gt;0.2&lt;/discount_ratio&gt;
    &lt;total_stock city_id="870"&gt;45&lt;/total_stock&gt;
    &lt;images&gt;
      &lt;image&gt;https://www.lcw.com/images/product1-1.jpg&lt;/image&gt;
      &lt;image&gt;https://www.lcw.com/images/product1-2.jpg&lt;/image&gt;
    &lt;/images&gt;
    &lt;short_description&gt;Rahat ve şık slim fit jean pantolon...&lt;/short_description&gt;
    &lt;sizes&gt;
      &lt;size id="101" name="29/32" stock="15"&gt;
        &lt;barcodes&gt;
          &lt;barcode&gt;8681234567890&lt;/barcode&gt;
        &lt;/barcodes&gt;
      &lt;/size&gt;
      &lt;size id="102" name="30/32" stock="20"&gt;
        &lt;barcodes&gt;
          &lt;barcode&gt;8681234567891&lt;/barcode&gt;
        &lt;/barcodes&gt;
      &lt;/size&gt;
      &lt;size id="103" name="32/32" stock="10"&gt;
        &lt;barcodes&gt;
          &lt;barcode&gt;8681234567892&lt;/barcode&gt;
        &lt;/barcodes&gt;
      &lt;/size&gt;
    &lt;/sizes&gt;
  &lt;/product&gt;
  <!-- Daha fazla ürün... -->
&lt;/products&gt;
        </pre>
    </body>
    </html>
    """
    return HttpResponse(content, content_type='text/html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('lcwaikiki/', include('lcwaikiki.urls')),  # Include all lcwaikiki URLs with lcwaikiki/ prefix
    path('trendyol/', include('trendyol.urls')),  # Include all trendyol URLs with trendyol/ prefix
    path('api/docs/xml/', xml_api_docs, name='xml_api_docs'),  # XML API dokümantasyonu
    path('', RedirectView.as_view(url='/admin/', permanent=False)),  # Redirect root URL to admin
]
