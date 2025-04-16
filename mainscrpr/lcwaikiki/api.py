"""
LC Waikiki XML API - Ürün ve Mağaza Bilgileri

Bu modül LC Waikiki ürünleri ve mağazaları için XML formatında kapsamlı API endpoints sağlar.
Tüm bilgiler seniorik (senior/uzman) seviyesinde detaylı ve iyi tasarlanmış bir yapıda sunulur.
"""

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Q
from django.utils import timezone
import xml.etree.ElementTree as ET
import datetime
import json

from .models import Config
from .product_models import Product, ProductSize, City, Store, SizeStoreStock

# Sabit default şehir ID'si: Sakarya
DEFAULT_CITY_ID = "870"


def get_default_city_id():
    """Varsayılan şehir ID'sini döndürür (Sakarya=870)"""
    try:
        active_config = Config.objects.filter(is_active=True).first()
        if active_config:
            return active_config.default_city_id
        return DEFAULT_CITY_ID
    except Exception:
        return DEFAULT_CITY_ID


class XMLResponse(HttpResponse):
    """XML formatında HTTP yanıtı sağlayan yardımcı sınıf"""
    def __init__(self, xml_root, *args, **kwargs):
        """
        XML root elementini alıp HTTP yanıtı oluşturur
        
        Args:
            xml_root: ET.Element tipinde XML root element
        """
        ET.indent(xml_root, space="  ", level=0)  # XML formatı düzgün göstermek için girinti ekler
        xml_declaration = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        xml_str = ET.tostring(xml_root, encoding='utf-8').decode('utf-8')
        super(XMLResponse, self).__init__(
            content=xml_declaration + xml_str,
            content_type='application/xml',
            *args, **kwargs
        )


class BaseXMLView(View):
    """Tüm XML API view'ları için temel sınıf"""
    
    def create_root_element(self, root_tag="response", **attributes):
        """
        Yeni bir XML root element oluşturur
        
        Args:
            root_tag: Root elementin tag adı (varsayılan: "response")
            attributes: Root elemente eklenecek özellikler (key-value pairs)
            
        Returns:
            ET.Element: Root element
        """
        root = ET.Element(root_tag)
        root.set("timestamp", datetime.datetime.now().isoformat())
        root.set("version", "1.0")
        
        # Attributes ekle
        for key, value in attributes.items():
            if value is not None:
                root.set(key, str(value))
                
        return root
    
    def add_element(self, parent, tag, text=None, **attributes):
        """
        Parent elemente yeni bir child element ekler
        
        Args:
            parent: ET.Element tipinde parent element
            tag: Eklenecek elementin tag adı
            text: Element için metin (varsa)
            attributes: Element için özellikler (key-value pairs)
            
        Returns:
            ET.Element: Eklenen yeni element
        """
        element = ET.SubElement(parent, tag)
        
        if text is not None:
            element.text = str(text)
            
        for key, value in attributes.items():
            if value is not None:
                element.set(key, str(value))
                
        return element
    
    def json_to_xml(self, parent, json_data, tag_name="item"):
        """
        JSON veriyi XML elemente dönüştürür (recursive)
        
        Args:
            parent: Parent XML element
            json_data: JSON formatında veri (dict, list, str, int, vs.)
            tag_name: Kullanılacak tag ismi (liste elemanları için)
        
        Returns:
            ET.Element: Dönüştürülen XML element
        """
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if value is None:
                    sub_element = self.add_element(parent, key)
                elif isinstance(value, (dict, list)):
                    sub_element = self.add_element(parent, key)
                    self.json_to_xml(sub_element, value)
                else:
                    self.add_element(parent, key, text=value)
        elif isinstance(json_data, list):
            for item in json_data:
                if isinstance(item, (dict, list)):
                    sub_element = self.add_element(parent, tag_name)
                    self.json_to_xml(sub_element, item)
                else:
                    self.add_element(parent, tag_name, text=item)
        else:
            parent.text = str(json_data)
        
        return parent


class ProductListXMLView(BaseXMLView):
    """Ürün listesi için XML API view"""
    
    def get(self, request):
        """
        Ürün listesini XML formatında döndürür
        
        Query params:
            limit: Maksimum döndürülecek ürün sayısı (varsayılan: 50)
            offset: Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)
            category: Kategori filtresi (opsiyonel)
            in_stock: Sadece stokta olanlar için "1" (opsiyonel)
            min_price: Minimum fiyat filtresi (opsiyonel)
            max_price: Maksimum fiyat filtresi (opsiyonel)
            city_id: Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)
        """
        # Query parametrelerini al
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        category = request.GET.get('category')
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        in_stock = request.GET.get('in_stock') == '1'
        city_id = request.GET.get('city_id', get_default_city_id())
        
        # Ürünleri filtrele
        products = Product.objects.all()
        
        if category:
            products = products.filter(category__icontains=category)
        
        if in_stock:
            products = products.filter(in_stock=True)
        
        if min_price:
            products = products.filter(price__gte=float(min_price))
        
        if max_price:
            products = products.filter(price__lte=float(max_price))
        
        # Sayfalama
        products = products.order_by('-timestamp')[offset:offset+limit]
        
        # XML response oluştur
        root = self.create_root_element(
            "products", 
            total_count=str(products.count()),
            limit=str(limit),
            offset=str(offset),
            city_id=city_id
        )
        
        # Ürünleri ekle
        for product in products:
            product_elem = self.add_element(
                root, 
                "product",
                id=str(product.id),
                code=product.product_code,
                in_stock=str(product.in_stock).lower()
            )
            
            self.add_element(product_elem, "url", text=product.url)
            self.add_element(product_elem, "title", text=product.title)
            self.add_element(product_elem, "category", text=product.category)
            self.add_element(product_elem, "color", text=product.color)
            self.add_element(product_elem, "price", text=product.price)
            
            if product.discount_ratio:
                self.add_element(product_elem, "discount_ratio", text=product.discount_ratio)
            
            # Toplam stok bilgisi
            self.add_element(
                product_elem, 
                "total_stock", 
                text=product.get_total_stock(),
                city_id=city_id
            )
            
            # Resimler
            images_elem = self.add_element(product_elem, "images")
            for image_url in product.images:
                self.add_element(images_elem, "image", text=image_url)
            
            # Kısa açıklama (HTML içerikten temizlenmiş)
            if product.description:
                # HTML içeriğini kısalt ve temizle
                import re
                desc_text = re.sub(r'<[^>]+>', ' ', product.description)
                desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                if len(desc_text) > 200:
                    desc_text = desc_text[:197] + "..."
                self.add_element(product_elem, "short_description", text=desc_text)
            
            # Bedenler
            sizes_elem = self.add_element(product_elem, "sizes")
            for size in product.sizes.all():
                size_elem = self.add_element(
                    sizes_elem, 
                    "size",
                    id=str(size.id),
                    name=size.size_name,
                    stock=str(size.size_general_stock)
                )
                
                # Barkodlar
                if size.barcode_list:
                    barcodes_elem = self.add_element(size_elem, "barcodes")
                    for barcode in size.barcode_list:
                        self.add_element(barcodes_elem, "barcode", text=barcode)
        
        return XMLResponse(root)


class ProductDetailXMLView(BaseXMLView):
    """Ürün detayı için XML API view"""
    
    def get(self, request, product_id):
        """
        Belirli bir ürünün detayını XML formatında döndürür
        
        Args:
            product_id: Ürün ID
            
        Query params:
            city_id: Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)
            include_stores: Mağaza stok bilgilerini dahil etmek için "1" (opsiyonel)
            include_description: HTML açıklamayı dahil etmek için "1" (opsiyonel, varsayılan: 1)
        """
        # Query parametrelerini al
        city_id = request.GET.get('city_id', get_default_city_id())
        include_stores = request.GET.get('include_stores') == '1'
        include_description = request.GET.get('include_description', '1') == '1'
        
        # Ürünü getir
        product = get_object_or_404(Product, id=product_id)
        
        # XML response oluştur
        root = self.create_root_element(
            "product_detail", 
            id=str(product.id),
            code=product.product_code,
            in_stock=str(product.in_stock).lower(),
            city_id=city_id
        )
        
        # Temel bilgiler
        self.add_element(root, "url", text=product.url)
        self.add_element(root, "title", text=product.title)
        self.add_element(root, "category", text=product.category)
        self.add_element(root, "color", text=product.color)
        self.add_element(root, "price", text=product.price)
        
        if product.discount_ratio:
            self.add_element(root, "discount_ratio", text=product.discount_ratio)
        
        # Toplam stok bilgisi
        self.add_element(
            root, 
            "total_stock", 
            text=product.get_total_stock(),
            city_id=city_id,
            last_updated=product.timestamp.isoformat()
        )
        
        # Resimler
        images_elem = self.add_element(root, "images")
        for i, image_url in enumerate(product.images):
            self.add_element(
                images_elem, 
                "image", 
                text=image_url, 
                position=str(i+1),
                is_main="true" if i == 0 else "false"
            )
        
        # HTML Açıklama
        if include_description and product.description:
            self.add_element(root, "description", text=product.description, format="html")
        
        # Bedenler ve stok bilgileri
        sizes_elem = self.add_element(root, "sizes")
        for size in product.sizes.all():
            size_elem = self.add_element(
                sizes_elem, 
                "size",
                id=str(size.id),
                name=size.size_name,
                general_stock=str(size.size_general_stock)
            )
            
            # Barkodlar
            if size.barcode_list:
                barcodes_elem = self.add_element(size_elem, "barcodes")
                for barcode in size.barcode_list:
                    self.add_element(barcodes_elem, "barcode", text=barcode)
            
            # Mağaza stok bilgileri
            if include_stores:
                stores_elem = self.add_element(size_elem, "stores")
                
                # Mağaza bazında stok bilgilerini getir
                store_stocks = size.store_stocks.all()
                
                # Şehir filtresi
                if city_id:
                    store_stocks = store_stocks.filter(store__city_id=city_id)
                
                for store_stock in store_stocks.filter(stock__gt=0):
                    store = store_stock.store
                    
                    store_elem = self.add_element(
                        stores_elem,
                        "store",
                        id=store.store_code,
                        stock=str(store_stock.stock)
                    )
                    
                    self.add_element(store_elem, "name", text=store.store_name)
                    self.add_element(store_elem, "city", text=store.city.name, id=store.city.city_id)
                    
                    if store.store_county:
                        self.add_element(store_elem, "county", text=store.store_county)
                    
                    if store.store_phone:
                        self.add_element(store_elem, "phone", text=store.store_phone)
                    
                    if store.address:
                        self.add_element(store_elem, "address", text=store.address)
                    
                    if store.latitude and store.longitude:
                        self.add_element(
                            store_elem, 
                            "location", 
                            latitude=store.latitude,
                            longitude=store.longitude
                        )
        
        # Ek ürün özellikleri (gelecekte eklenebilir)
        return XMLResponse(root)


class StoreListXMLView(BaseXMLView):
    """Mağaza listesi için XML API view"""
    
    def get(self, request):
        """
        Mağaza listesini XML formatında döndürür
        
        Query params:
            city_id: Şehir ID filtresi (opsiyonel, varsayılan: Sakarya=870)
            has_stock: Belirli stok ID'si için stok bulunan mağazaları filtrele (opsiyonel)
            limit: Maksimum döndürülecek mağaza sayısı (varsayılan: 100)
            offset: Kaç mağaza atlanacak (sayfalama için) (varsayılan: 0)
        """
        # Query parametrelerini al
        city_id = request.GET.get('city_id', get_default_city_id())
        has_stock_id = request.GET.get('has_stock')
        limit = int(request.GET.get('limit', 100))
        offset = int(request.GET.get('offset', 0))
        
        # Mağazaları filtrele
        stores = Store.objects.all()
        
        if city_id:
            stores = stores.filter(city_id=city_id)
        
        # Stok filtresi
        if has_stock_id:
            try:
                product_size = ProductSize.objects.get(id=has_stock_id)
                # Stok bulunan mağazaları filtrele
                store_ids = SizeStoreStock.objects.filter(
                    product_size=product_size,
                    stock__gt=0
                ).values_list('store_id', flat=True)
                stores = stores.filter(store_code__in=store_ids)
            except ProductSize.DoesNotExist:
                pass
        
        # Sayfalama
        total_count = stores.count()
        stores = stores.order_by('city_id', 'store_name')[offset:offset+limit]
        
        # XML response oluştur
        root = self.create_root_element(
            "stores", 
            total_count=str(total_count),
            returned_count=str(stores.count()),
            city_id=city_id if city_id else "",
            limit=str(limit),
            offset=str(offset)
        )
        
        # Şehirler bazında grupla
        if stores:
            cities_elem = self.add_element(root, "cities")
            current_city = None
            city_elem = None
            
            for store in stores:
                # Eğer yeni bir şehire geçilmişse, yeni şehir elementi oluştur
                if current_city != store.city.city_id:
                    current_city = store.city.city_id
                    city_elem = self.add_element(
                        cities_elem, 
                        "city",
                        id=store.city.city_id,
                        name=store.city.name
                    )
                
                # Mağaza bilgileri
                store_elem = self.add_element(
                    city_elem, 
                    "store",
                    id=store.store_code
                )
                
                self.add_element(store_elem, "name", text=store.store_name)
                
                if store.store_county:
                    self.add_element(store_elem, "county", text=store.store_county)
                
                if store.store_phone:
                    self.add_element(store_elem, "phone", text=store.store_phone)
                
                if store.address:
                    self.add_element(store_elem, "address", text=store.address)
                
                if store.latitude and store.longitude:
                    self.add_element(
                        store_elem, 
                        "location", 
                        latitude=store.latitude,
                        longitude=store.longitude
                    )
                
                # Eğer has_stock filtresi varsa, bu mağazadaki ürün stok sayısını ekle
                if has_stock_id:
                    try:
                        store_stock = SizeStoreStock.objects.get(
                            product_size_id=has_stock_id,
                            store=store
                        )
                        self.add_element(store_elem, "stock", text=store_stock.stock)
                    except SizeStoreStock.DoesNotExist:
                        self.add_element(store_elem, "stock", text="0")
        
        return XMLResponse(root)


class CityListXMLView(BaseXMLView):
    """Şehir listesi için XML API view"""
    
    def get(self, request):
        """Şehir listesini XML formatında döndürür"""
        # Şehirleri getir
        cities = City.objects.all().order_by('name')
        
        # XML response oluştur
        root = self.create_root_element(
            "cities", 
            total_count=str(cities.count()),
            default_city_id=get_default_city_id()
        )
        
        # Şehirleri ekle
        for city in cities:
            city_elem = self.add_element(
                root, 
                "city",
                id=city.city_id,
                is_default="true" if city.city_id == get_default_city_id() else "false"
            )
            
            self.add_element(city_elem, "name", text=city.name)
            
            # Şehirdeki mağaza sayısını ekle
            store_count = Store.objects.filter(city=city).count()
            self.add_element(city_elem, "store_count", text=store_count)
        
        return XMLResponse(root)


class ProductInventoryXMLView(BaseXMLView):
    """Ürün stok durumu için XML API view"""
    
    def get(self, request, product_id):
        """
        Belirli bir ürünün stok durumunu XML formatında döndürür
        
        Args:
            product_id: Ürün ID
            
        Query params:
            city_id: Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)
            size_id: Beden ID filtresi (opsiyonel)
            min_stock: Minimum stok filtresi (opsiyonel)
        """
        # Query parametrelerini al
        city_id = request.GET.get('city_id', get_default_city_id())
        size_id = request.GET.get('size_id')
        min_stock = request.GET.get('min_stock')
        
        if min_stock:
            min_stock = int(min_stock)
        
        # Ürünü getir
        product = get_object_or_404(Product, id=product_id)
        
        # XML response oluştur
        root = self.create_root_element(
            "inventory", 
            product_id=str(product.id),
            product_code=product.product_code,
            product_title=product.title,
            city_id=city_id,
            timestamp=timezone.now().isoformat()
        )
        
        # Beden filtresi
        sizes = product.sizes.all()
        if size_id:
            sizes = sizes.filter(id=size_id)
        
        # Toplam stok özeti
        if not size_id:
            total_stock = sum(size.size_general_stock for size in sizes)
            self.add_element(
                root, 
                "total_stock", 
                text=total_stock,
                city_id=city_id,
                available="true" if total_stock > 0 else "false"
            )
        
        # Beden bazında stok bilgileri
        sizes_elem = self.add_element(root, "sizes")
        
        for size in sizes:
            # Mağaza bazında stok toplamını getir
            stores_with_stock = SizeStoreStock.objects.filter(product_size=size)
            
            if city_id:
                stores_with_stock = stores_with_stock.filter(store__city_id=city_id)
            
            if min_stock:
                stores_with_stock = stores_with_stock.filter(stock__gte=min_stock)
            
            size_total_stock = stores_with_stock.aggregate(total=Sum('stock'))['total'] or 0
            
            # Hiç stok yoksa ve minimum stok filtresi varsa, bu bedeni atla
            if min_stock and size_total_stock < min_stock:
                continue
            
            size_elem = self.add_element(
                sizes_elem, 
                "size",
                id=str(size.id),
                name=size.size_name,
                total_stock=str(size_total_stock),
                available="true" if size_total_stock > 0 else "false"
            )
            
            # Bu bedendeki stok bulunan mağazaları listele
            stores_elem = self.add_element(size_elem, "stores")
            
            for store_stock in stores_with_stock.filter(stock__gt=0):
                store = store_stock.store
                
                store_elem = self.add_element(
                    stores_elem,
                    "store",
                    id=store.store_code,
                    stock=str(store_stock.stock)
                )
                
                self.add_element(store_elem, "name", text=store.store_name)
                self.add_element(store_elem, "city", text=store.city.name, id=store.city.city_id)
                
                if store.store_county:
                    self.add_element(store_elem, "county", text=store.store_county)
        
        return XMLResponse(root)


@method_decorator(csrf_exempt, name='dispatch')
class ProductSearchXMLView(BaseXMLView):
    """Ürün arama için XML API view"""
    
    def get(self, request):
        """
        Ürünleri arama ve XML formatında döndürür
        
        Query params:
            q: Arama sorgusu (başlık, kategori, renk içerisinde arama yapar)
            category: Kategori filtresi (opsiyonel)
            color: Renk filtresi (opsiyonel)
            min_price: Minimum fiyat filtresi (opsiyonel)
            max_price: Maksimum fiyat filtresi (opsiyonel)
            in_stock: Sadece stokta olanlar için "1" (opsiyonel)
            city_id: Şehir ID (stok kontrolü için, varsayılan: Sakarya=870)
            limit: Maksimum döndürülecek ürün sayısı (varsayılan: 20)
            offset: Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)
            size: Beden filtresi (opsiyonel)
        """
        # Query parametrelerini al
        query = request.GET.get('q', '')
        category = request.GET.get('category')
        color = request.GET.get('color')
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        in_stock = request.GET.get('in_stock') == '1'
        city_id = request.GET.get('city_id', get_default_city_id())
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        size = request.GET.get('size')
        
        # Arama filtrelerini oluştur
        filters = Q()
        
        if query:
            filters |= Q(title__icontains=query)
            filters |= Q(category__icontains=query)
            filters |= Q(color__icontains=query)
            filters |= Q(description__icontains=query)
        
        # Ek filtreler
        if category:
            filters &= Q(category__icontains=category)
        
        if color:
            filters &= Q(color__icontains=color)
        
        if in_stock:
            filters &= Q(in_stock=True)
        
        if min_price:
            filters &= Q(price__gte=float(min_price))
        
        if max_price:
            filters &= Q(price__lte=float(max_price))
        
        # Beden filtresi
        if size:
            products_with_size = ProductSize.objects.filter(
                size_name__icontains=size
            ).values_list('product_id', flat=True)
            filters &= Q(id__in=products_with_size)
        
        # Ürünleri filtrele ve sırala
        products = Product.objects.filter(filters).order_by('-timestamp')
        total_count = products.count()
        products = products[offset:offset+limit]
        
        # XML response oluştur
        root = self.create_root_element(
            "search_results", 
            query=query,
            total_count=str(total_count),
            returned_count=str(products.count()),
            city_id=city_id,
            limit=str(limit),
            offset=str(offset)
        )
        
        # Arama filtrelerini ekle
        filters_elem = self.add_element(root, "applied_filters")
        
        if query:
            self.add_element(filters_elem, "query", text=query)
        
        if category:
            self.add_element(filters_elem, "category", text=category)
        
        if color:
            self.add_element(filters_elem, "color", text=color)
        
        if in_stock:
            self.add_element(filters_elem, "in_stock", text="true")
        
        if min_price:
            self.add_element(filters_elem, "min_price", text=min_price)
        
        if max_price:
            self.add_element(filters_elem, "max_price", text=max_price)
        
        if size:
            self.add_element(filters_elem, "size", text=size)
        
        # Ürünleri ekle
        products_elem = self.add_element(root, "products")
        
        for product in products:
            product_elem = self.add_element(
                products_elem, 
                "product",
                id=str(product.id),
                code=product.product_code,
                in_stock=str(product.in_stock).lower()
            )
            
            self.add_element(product_elem, "url", text=product.url)
            self.add_element(product_elem, "title", text=product.title)
            self.add_element(product_elem, "category", text=product.category)
            self.add_element(product_elem, "color", text=product.color)
            self.add_element(product_elem, "price", text=product.price)
            
            if product.discount_ratio:
                self.add_element(product_elem, "discount_ratio", text=product.discount_ratio)
            
            # Toplam stok bilgisi
            self.add_element(
                product_elem, 
                "total_stock", 
                text=product.get_total_stock(),
                city_id=city_id
            )
            
            # Ana resim
            if product.images:
                self.add_element(product_elem, "main_image", text=product.images[0])
            
            # Bedenler
            if size:
                sizes_elem = self.add_element(product_elem, "matching_sizes")
                for prod_size in product.sizes.filter(size_name__icontains=size):
                    self.add_element(
                        sizes_elem,
                        "size",
                        id=str(prod_size.id),
                        name=prod_size.size_name,
                        stock=str(prod_size.size_general_stock)
                    )
        
        return XMLResponse(root)
    
    def post(self, request):
        """
        POST yöntemiyle gelişmiş arama
        
        Body: JSON formatında arama parametreleri
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
            "sort": "price_asc" // price_asc, price_desc, newest, popularity
        }
        """
        try:
            # JSON verisini al
            data = json.loads(request.body)
            
            # Arama parametrelerini al
            query = data.get('query', '')
            filters = data.get('filters', {})
            city_id = data.get('city_id', get_default_city_id())
            pagination = data.get('pagination', {'limit': 20, 'offset': 0})
            sort_by = data.get('sort', 'newest')
            
            # Limit ve offset
            limit = pagination.get('limit', 20)
            offset = pagination.get('offset', 0)
            
            # Arama filtrelerini oluştur
            query_filters = Q()
            
            if query:
                query_filters |= Q(title__icontains=query)
                query_filters |= Q(category__icontains=query)
                query_filters |= Q(color__icontains=query)
                query_filters |= Q(description__icontains=query)
            
            # Ek filtreler
            if 'category' in filters:
                query_filters &= Q(category__icontains=filters['category'])
            
            if 'color' in filters:
                query_filters &= Q(color__icontains=filters['color'])
            
            if filters.get('in_stock', False):
                query_filters &= Q(in_stock=True)
            
            if 'price' in filters:
                price = filters['price']
                if 'min' in price:
                    query_filters &= Q(price__gte=float(price['min']))
                if 'max' in price:
                    query_filters &= Q(price__lte=float(price['max']))
            
            # Beden filtresi
            if 'sizes' in filters and filters['sizes']:
                size_filters = Q()
                for size in filters['sizes']:
                    size_filters |= Q(sizes__size_name__icontains=size)
                query_filters &= size_filters
            
            # Ürünleri filtrele
            products = Product.objects.filter(query_filters).distinct()
            
            # Sıralama
            if sort_by == 'price_asc':
                products = products.order_by('price')
            elif sort_by == 'price_desc':
                products = products.order_by('-price')
            elif sort_by == 'popularity':
                # Popülerlik için örnek bir sıralama (burada sadece stok miktarına göre)
                products = products.annotate(
                    total_stock=Sum('sizes__size_general_stock')
                ).order_by('-total_stock')
            else:  # 'newest' veya varsayılan
                products = products.order_by('-timestamp')
            
            # Toplam sayı ve sayfalama
            total_count = products.count()
            products = products[offset:offset+limit]
            
            # XML response oluştur
            root = self.create_root_element(
                "advanced_search_results", 
                query=query,
                total_count=str(total_count),
                returned_count=str(products.count()),
                city_id=city_id,
                limit=str(limit),
                offset=str(offset),
                sort=sort_by
            )
            
            # Arama filtrelerini ekle
            filters_elem = self.add_element(root, "applied_filters")
            
            if query:
                self.add_element(filters_elem, "query", text=query)
            
            # JSON filtrelerini XML'e dönüştür
            self.json_to_xml(filters_elem, filters)
            
            # Ürünleri ekle
            products_elem = self.add_element(root, "products")
            
            for product in products:
                product_elem = self.add_element(
                    products_elem, 
                    "product",
                    id=str(product.id),
                    code=product.product_code,
                    in_stock=str(product.in_stock).lower()
                )
                
                self.add_element(product_elem, "url", text=product.url)
                self.add_element(product_elem, "title", text=product.title)
                self.add_element(product_elem, "category", text=product.category)
                self.add_element(product_elem, "color", text=product.color)
                self.add_element(product_elem, "price", text=product.price)
                
                if product.discount_ratio:
                    self.add_element(product_elem, "discount_ratio", text=product.discount_ratio)
                
                # Toplam stok bilgisi
                self.add_element(
                    product_elem, 
                    "total_stock", 
                    text=product.get_total_stock(),
                    city_id=city_id
                )
                
                # Ana resim
                if product.images:
                    self.add_element(product_elem, "main_image", text=product.images[0])
                
                # Bedenler - Sadece eşleşen bedenleri göster
                if 'sizes' in filters and filters['sizes']:
                    sizes_elem = self.add_element(product_elem, "matching_sizes")
                    for size_name in filters['sizes']:
                        for prod_size in product.sizes.filter(size_name__icontains=size_name):
                            self.add_element(
                                sizes_elem,
                                "size",
                                id=str(prod_size.id),
                                name=prod_size.size_name,
                                stock=str(prod_size.size_general_stock)
                            )
            
            return XMLResponse(root)
            
        except json.JSONDecodeError:
            # Geçersiz JSON formatı
            root = self.create_root_element("error")
            self.add_element(root, "message", text="Invalid JSON format")
            return XMLResponse(root, status=400)
        
        except Exception as e:
            # Genel hata
            root = self.create_root_element("error")
            self.add_element(root, "message", text=str(e))
            return XMLResponse(root, status=500)


class StoreDetailXMLView(BaseXMLView):
    """Mağaza detayı için XML API view"""
    
    def get(self, request, store_id):
        """
        Belirli bir mağazanın detayını XML formatında döndürür
        
        Args:
            store_id: Mağaza ID (store_code)
            
        Query params:
            include_products: Stokta bulunan ürünleri dahil etmek için "1" (opsiyonel)
            limit: Maksimum döndürülecek ürün sayısı (varsayılan: 20)
            offset: Kaç ürün atlanacak (sayfalama için) (varsayılan: 0)
            min_stock: Minimum stok filtresi (opsiyonel, varsayılan: 1)
        """
        # Query parametrelerini al
        include_products = request.GET.get('include_products') == '1'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        min_stock = int(request.GET.get('min_stock', 1))
        
        # Mağazayı getir
        store = get_object_or_404(Store, store_code=store_id)
        
        # XML response oluştur
        root = self.create_root_element(
            "store_detail", 
            id=store.store_code,
            name=store.store_name,
            city_id=store.city.city_id,
            city_name=store.city.name
        )
        
        # Temel bilgiler
        if store.store_county:
            self.add_element(root, "county", text=store.store_county)
        
        if store.store_phone:
            self.add_element(root, "phone", text=store.store_phone)
        
        if store.address:
            self.add_element(root, "address", text=store.address)
        
        if store.latitude and store.longitude:
            self.add_element(
                root, 
                "location", 
                latitude=store.latitude,
                longitude=store.longitude
            )
        
        # Mağazadaki stok bulunan ürünleri getir
        if include_products:
            # Stok bulunan ürünleri getir
            stock_items = SizeStoreStock.objects.filter(
                store=store,
                stock__gte=min_stock
            ).select_related('product_size', 'product_size__product')
            
            # Toplam kayıt sayısı
            total_product_count = stock_items.values('product_size__product').distinct().count()
            
            # Ürünleri ekle
            products_elem = self.add_element(
                root, 
                "products",
                total_count=str(total_product_count),
                returned_count=str(min(limit, total_product_count)),
                min_stock=str(min_stock)
            )
            
            # Ürünleri sayfalama ile getir
            unique_products = stock_items.values('product_size__product').distinct()[offset:offset+limit]
            product_ids = [item['product_size__product'] for item in unique_products]
            
            for product_id in product_ids:
                product = Product.objects.get(id=product_id)
                
                product_elem = self.add_element(
                    products_elem, 
                    "product",
                    id=str(product.id),
                    code=product.product_code
                )
                
                self.add_element(product_elem, "url", text=product.url)
                self.add_element(product_elem, "title", text=product.title)
                self.add_element(product_elem, "price", text=product.price)
                
                # Ana resim
                if product.images:
                    self.add_element(product_elem, "main_image", text=product.images[0])
                
                # Bu mağazada stok bulunan bedenler
                sizes_elem = self.add_element(product_elem, "sizes")
                for stock_item in stock_items.filter(
                    product_size__product=product,
                    stock__gte=min_stock
                ):
                    size = stock_item.product_size
                    self.add_element(
                        sizes_elem,
                        "size",
                        id=str(size.id),
                        name=size.size_name,
                        stock=str(stock_item.stock)
                    )
        
        return XMLResponse(root)


class ProductStatisticsXMLView(BaseXMLView):
    """Ürün istatistikleri için XML API view"""
    
    def get(self, request):
        """
        Ürün istatistiklerini XML formatında döndürür
        
        Query params:
            city_id: Şehir ID filtresi (opsiyonel, varsayılan: Sakarya=870)
        """
        # Query parametrelerini al
        city_id = request.GET.get('city_id', get_default_city_id())
        
        # İstatistikleri hesapla
        total_products = Product.objects.count()
        in_stock_products = Product.objects.filter(in_stock=True).count()
        
        # Kategori bazında ürün sayıları
        categories = Product.objects.values('category').annotate(count=Count('id')).order_by('-count')[:10]
        
        # Renk bazında ürün sayıları
        colors = Product.objects.values('color').annotate(count=Count('id')).order_by('-count')[:10]
        
        # Fiyat aralıklarına göre ürün sayıları
        price_ranges = [
            {'min': 0, 'max': 100, 'count': Product.objects.filter(price__gte=0, price__lt=100).count()},
            {'min': 100, 'max': 200, 'count': Product.objects.filter(price__gte=100, price__lt=200).count()},
            {'min': 200, 'max': 500, 'count': Product.objects.filter(price__gte=200, price__lt=500).count()},
            {'min': 500, 'max': 1000, 'count': Product.objects.filter(price__gte=500, price__lt=1000).count()},
            {'min': 1000, 'max': None, 'count': Product.objects.filter(price__gte=1000).count()}
        ]
        
        # XML response oluştur
        root = self.create_root_element(
            "product_statistics", 
            total_products=str(total_products),
            in_stock_products=str(in_stock_products),
            city_id=city_id,
            timestamp=timezone.now().isoformat()
        )
        
        # Kategori istatistikleri
        categories_elem = self.add_element(root, "category_statistics")
        for category in categories:
            if category['category']:  # Null kategori atla
                self.add_element(
                    categories_elem,
                    "category",
                    name=category['category'],
                    count=str(category['count'])
                )
        
        # Renk istatistikleri
        colors_elem = self.add_element(root, "color_statistics")
        for color in colors:
            if color['color']:  # Null renk atla
                self.add_element(
                    colors_elem,
                    "color",
                    name=color['color'],
                    count=str(color['count'])
                )
        
        # Fiyat aralığı istatistikleri
        price_ranges_elem = self.add_element(root, "price_range_statistics")
        for price_range in price_ranges:
            range_elem = self.add_element(
                price_ranges_elem,
                "price_range",
                min=str(price_range['min']),
                max=str(price_range['max']) if price_range['max'] else "∞",
                count=str(price_range['count'])
            )
            
            # İnsan okunabilir aralık etiketi ekle
            if price_range['max']:
                label = f"{price_range['min']} - {price_range['max']} TL"
            else:
                label = f"{price_range['min']}+ TL"
            
            self.add_element(range_elem, "label", text=label)
        
        # Beden istatistikleri
        sizes_elem = self.add_element(root, "size_statistics")
        size_stats = (
            ProductSize.objects
            .values('size_name')
            .annotate(count=Count('id'), total_stock=Sum('size_general_stock'))
            .order_by('-count')
            .filter(count__gt=0)[:20]
        )
        
        for size_stat in size_stats:
            self.add_element(
                sizes_elem,
                "size",
                name=size_stat['size_name'],
                product_count=str(size_stat['count']),
                total_stock=str(size_stat['total_stock'] or 0)
            )
        
        return XMLResponse(root)