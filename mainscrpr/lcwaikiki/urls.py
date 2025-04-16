"""
LC Waikiki API URL Configuration

Bu modül, LC Waikiki ürünleri ve mağazaları için XML API endpoints'in URL yapılandırmasını içerir.
Tüm URL'ler XML formatında yanıt verir.
"""

from django.urls import path
from .api import (
    ProductListXMLView, 
    ProductDetailXMLView,
    StoreListXMLView,
    StoreDetailXMLView,
    ProductInventoryXMLView,
    ProductSearchXMLView,
    CityListXMLView,
    ProductStatisticsXMLView
)

app_name = 'lcwaikiki'

urlpatterns = [
    # Ürün API Endpoints
    path('xml/products/', ProductListXMLView.as_view(), name='product_list_xml'),
    path('xml/products/<int:product_id>/', ProductDetailXMLView.as_view(), name='product_detail_xml'),
    path('xml/products/<int:product_id>/inventory/', ProductInventoryXMLView.as_view(), name='product_inventory_xml'),
    path('xml/products/search/', ProductSearchXMLView.as_view(), name='product_search_xml'),
    path('xml/products/statistics/', ProductStatisticsXMLView.as_view(), name='product_statistics_xml'),
    
    # Mağaza API Endpoints
    path('xml/stores/', StoreListXMLView.as_view(), name='store_list_xml'),
    path('xml/stores/<str:store_id>/', StoreDetailXMLView.as_view(), name='store_detail_xml'),
    
    # Şehir API Endpoints
    path('xml/cities/', CityListXMLView.as_view(), name='city_list_xml'),
]

# API endpoint dokümantasyonu
api_doc = {
    "api_version": "1.0",
    "base_url": "/lcwaikiki/xml/",
    "endpoints": {
        "products": {
            "description": "Ürün listesi (XML)",
            "parameters": {
                "limit": "Maksimum döndürülecek ürün sayısı (varsayılan: 50)",
                "offset": "Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)",
                "category": "Kategori filtresi (opsiyonel)",
                "in_stock": "Sadece stokta olanlar için '1' (opsiyonel)",
                "min_price": "Minimum fiyat filtresi (opsiyonel)",
                "max_price": "Maksimum fiyat filtresi (opsiyonel)",
                "city_id": "Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)"
            }
        },
        "products/{product_id}": {
            "description": "Ürün detayı (XML)",
            "parameters": {
                "city_id": "Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)",
                "include_stores": "Mağaza stok bilgilerini dahil etmek için '1' (opsiyonel)",
                "include_description": "HTML açıklamayı dahil etmek için '1' (opsiyonel, varsayılan: 1)"
            }
        },
        "products/{product_id}/inventory": {
            "description": "Ürün stok durumu (XML)",
            "parameters": {
                "city_id": "Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)",
                "size_id": "Beden ID filtresi (opsiyonel)",
                "min_stock": "Minimum stok filtresi (opsiyonel)"
            }
        },
        "products/search": {
            "description": "Ürün arama (XML)",
            "methods": ["GET", "POST"],
            "parameters": {
                "q": "Arama sorgusu (başlık, kategori, renk içerisinde arama yapar)",
                "category": "Kategori filtresi (opsiyonel)",
                "color": "Renk filtresi (opsiyonel)",
                "min_price": "Minimum fiyat filtresi (opsiyonel)",
                "max_price": "Maksimum fiyat filtresi (opsiyonel)",
                "in_stock": "Sadece stokta olanlar için '1' (opsiyonel)",
                "city_id": "Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)",
                "limit": "Maksimum döndürülecek ürün sayısı (varsayılan: 20)",
                "offset": "Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)",
                "size": "Beden filtresi (opsiyonel)"
            },
            "post_body_example": {
                "query": "arama terimi",
                "filters": {
                    "category": "kategori",
                    "color": "renk",
                    "price": {
                        "min": 100,
                        "max": 500
                    },
                    "sizes": ["M", "L"],
                    "in_stock": True
                },
                "city_id": "870",
                "pagination": {
                    "limit": 20,
                    "offset": 0
                },
                "sort": "price_asc"  # price_asc, price_desc, newest, popularity
            }
        },
        "products/statistics": {
            "description": "Ürün istatistikleri (XML)",
            "parameters": {
                "city_id": "Şehir ID filtresi (opsiyonel, varsayılan: Sakarya=870)"
            }
        },
        "stores": {
            "description": "Mağaza listesi (XML)",
            "parameters": {
                "city_id": "Şehir ID filtresi (opsiyonel, varsayılan: Sakarya=870)",
                "has_stock": "Belirli stok ID'si için stok bulunan mağazaları filtrele (opsiyonel)",
                "limit": "Maksimum döndürülecek mağaza sayısı (varsayılan: 100)",
                "offset": "Kaç mağaza atlanacak (sayfalama için) (varsayılan: 0)"
            }
        },
        "stores/{store_id}": {
            "description": "Mağaza detayı (XML)",
            "parameters": {
                "include_products": "Stokta bulunan ürünleri dahil etmek için '1' (opsiyonel)",
                "limit": "Maksimum döndürülecek ürün sayısı (varsayılan: 20)",
                "offset": "Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)",
                "min_stock": "Minimum stok filtresi (opsiyonel, varsayılan: 1)"
            }
        },
        "cities": {
            "description": "Şehir listesi (XML)",
            "parameters": {}
        }
    }
}