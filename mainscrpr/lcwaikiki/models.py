from django.db import models
from django.core.exceptions import ValidationError
import json
from django.utils import timezone


class CityConfiguration(models.Model):
  CITY_CHOICES = [
      ("866", "Adana"),
      ("894", "Adıyaman"),
      ("882", "Afyon"),
      ("927", "Ağrı"),
      ("920", "Aksaray"),
      ("935", "Amasya"),
      ("873", "Ankara"),
      ("867", "Antalya"),
      ("948", "Ardahan"),
      ("905", "Artvin"),
      ("871", "Aydın"),
      ("885", "Balıkesir"),
      ("939", "Bartın"),
      ("925", "Batman"),
      ("936", "Bayburt"),
      ("917", "Bilecik"),
      ("941", "Bingöl"),
      ("897", "Bitlis"),
      ("923", "Bolu"),
      ("919", "Burdur"),
      ("868", "Bursa"),
      ("910", "Çanakkale"),
      ("929", "Çankırı"),
      ("888", "Çorum"),
      ("874", "Denizli"),
      ("926", "Diyarbakır"),
      ("947", "Düzce"),
      ("906", "Edirne"),
      ("913", "Elazığ"),
      ("922", "Erzincan"),
      ("900", "Erzurum"),
      ("887", "Eskişehir"),
      ("890", "Gaziantep"),
      ("884", "Giresun"),
      ("943", "Gümüşhane"),
      ("924", "Hakkari"),
      ("877", "Hatay"),
      ("914", "Iğdır"),
      ("908", "Isparta"),
      ("865", "İstanbul"),
      ("872", "İzmir"),
      ("898", "Kahramanmaraş"),
      ("912", "Karabük"),
      ("883", "Karaman"),
      ("915", "Kars"),
      ("895", "Kastamonu"),
      ("869", "Kayseri"),
      ("896", "Kırıkkale"),
      ("902", "Kırklareli"),
      ("940", "Kırşehir"),
      ("876", "Kocaeli"),
      ("875", "Konya"),
      ("901", "Kütahya"),
      ("893", "Malatya"),
      ("891", "Manisa"),
      ("930", "Mardin"),
      ("903", "Mersin"),
      ("899", "Muğla"),
      ("932", "Muş"),
      ("907", "Nevşehir"),
      ("911", "Niğde"),
      ("904", "Ordu"),
      ("892", "Osmaniye"),
      ("928", "Rize"),
      ("870", "Sakarya"),
      ("916", "Samsun"),
      ("931", "Siirt"),
      ("918", "Sinop"),
      ("879", "Sivas"),
      ("921", "Şanlıurfa"),
      ("942", "Şırnak"),
      ("880", "Tekirdağ"),
      ("909", "Tokat"),
      ("878", "Trabzon"),
      ("937", "Tunceli"),
      ("886", "Uşak"),
      ("933", "Van"),
      ("889", "Yalova"),
      ("938", "Yozgat"),
      ("881", "Zonguldak"),
  ]

  city_id = models.CharField(max_length=3,
                             choices=CITY_CHOICES,
                             primary_key=True,
                             verbose_name="City ID")
  is_active = models.BooleanField(default=True, verbose_name="Is Active")
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  class Meta:
    verbose_name = "City Configuration"
    verbose_name_plural = "City Configurations"

  def __str__(self):
    return self.get_city_id_display()


class Config(models.Model):
  name = models.CharField(max_length=100,
                          unique=True,
                          help_text="Configuration name")
  brands = models.JSONField(
      help_text="List of brands in JSON format, e.g. ['lcw-classic', 'lcw-abc']"
  )
  price_config = models.JSONField(
      default=dict, help_text="Price configuration in JSON format")
  default_city = models.ForeignKey(
      CityConfiguration,
      on_delete=models.SET_NULL,
      null=True,
      blank=True,
      help_text="Default city for inventory checks")
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  def __str__(self):
    return self.name

  def clean(self):
    if not isinstance(self.brands, list):
      raise ValidationError({'brands': 'Brands must be a list'})
    for brand in self.brands:
      if not isinstance(brand, str):
        raise ValidationError({'brands': 'All brands must be strings'})

    # Set default price config if not provided
    if not self.price_config:
      self.price_config = {
          "default_multiplier":
          1.8,
          "rules": [{
              "max_price": 700,
              "multiplier": 2.0
          }, {
              "min_price": 700,
              "multiplier": 1.5
          }]
      }

  def save(self, *args, **kwargs):
    self.clean()
    super().save(*args, **kwargs)

  class Meta:
    verbose_name = "Configuration"
    verbose_name_plural = "Configurations"


class Product(models.Model):
  STATUS_CHOICES = [
      ('pending', 'Pending'),
      ('success', 'Success'),
      ('error', 'Error'),
  ]

  url = models.URLField(max_length=255, unique=True)
  title = models.CharField(max_length=255, blank=True, null=True)
  category = models.CharField(max_length=255, blank=True, null=True)
  description = models.TextField(blank=True, null=True)
  product_code = models.CharField(max_length=35, blank=True, null=True)
  color = models.CharField(max_length=100, blank=True, null=True)
  original_price = models.DecimalField(max_digits=10,
                                       decimal_places=2,
                                       null=True,
                                       blank=True)
  price = models.DecimalField(max_digits=10,
                              decimal_places=2,
                              null=True,
                              blank=True)
  discount_ratio = models.DecimalField(max_digits=5,
                                       decimal_places=2,
                                       null=True,
                                       blank=True)
  in_stock = models.BooleanField(default=False)
  images = models.JSONField(default=list)
  timestamp = models.DateTimeField(auto_now=True)
  status = models.CharField(max_length=50,
                            choices=STATUS_CHOICES,
                            default="pending")
  last_checking = models.DateTimeField(default=timezone.now)

  def __str__(self):
    return self.title or self.url

  class Meta:
    verbose_name = "Product"
    verbose_name_plural = "Products"
    indexes = [
        models.Index(fields=['status']),
        models.Index(fields=['last_checking']),
        models.Index(fields=['product_code']),
    ]


class ProductSize(models.Model):
  product = models.ForeignKey(Product,
                              on_delete=models.CASCADE,
                              related_name='sizes')
  size_name = models.CharField(max_length=50)
  size_id = models.CharField(max_length=50, blank=True, null=True)
  size_general_stock = models.IntegerField(default=0)
  product_option_size_reference = models.CharField(max_length=50,
                                                   blank=True,
                                                   null=True)
  barcode_list = models.JSONField(default=list)

  def __str__(self):
    return f"{self.product} - {self.size_name}"

  class Meta:
    verbose_name = "Product Size"
    verbose_name_plural = "Product Sizes"
    unique_together = ('product', 'size_name')


class Store(models.Model):
  store_code = models.CharField(max_length=20, primary_key=True)
  store_name = models.CharField(max_length=200)
  city = models.ForeignKey(CityConfiguration,
                           on_delete=models.CASCADE,
                           related_name='stores')
  store_county = models.CharField(max_length=100, blank=True, null=True)
  store_phone = models.CharField(max_length=20, blank=True, null=True)
  address = models.TextField(blank=True, null=True)
  latitude = models.CharField(max_length=20, blank=True, null=True)
  longitude = models.CharField(max_length=20, blank=True, null=True)

  def __str__(self):
    return self.store_name

  class Meta:
    verbose_name = "Store"
    verbose_name_plural = "Stores"


class SizeStoreStock(models.Model):
  product_size = models.ForeignKey(ProductSize,
                                   on_delete=models.CASCADE,
                                   related_name='store_stocks')
  store = models.ForeignKey(Store,
                            on_delete=models.CASCADE,
                            related_name='size_stocks')
  original_stock = models.IntegerField(default=0)
  stock = models.IntegerField(default=0)

  def __str__(self):
    return f"{self.product_size} - {self.store}: {self.stock}"

  class Meta:
    verbose_name = "Size Store Stock"
    verbose_name_plural = "Size Store Stocks"
    unique_together = ('product_size', 'store')


class ProductAvailableUrl(models.Model):
  page_id = models.CharField(max_length=255, help_text="Page identifier")
  product_id_in_page = models.CharField(
      max_length=255, help_text="Product identifier within the page")
  url = models.URLField(max_length=1000, help_text="URL to the product")
  last_checking = models.DateTimeField(default=timezone.now,
                                       help_text="Date of last check")
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  def __str__(self):
    return f"{self.page_id} - {self.product_id_in_page}"

  class Meta:
    verbose_name = "Available Product URL"
    verbose_name_plural = "Available Product URLs"
    indexes = [
        models.Index(fields=['page_id']),
        models.Index(fields=['product_id_in_page']),
        models.Index(fields=['last_checking']),
        models.Index(fields=['url']),
    ]


class ProductDeletedUrl(models.Model):
  url = models.URLField(max_length=1000,
                        help_text="URL to the deleted product")
  last_checking = models.DateTimeField(default=timezone.now,
                                       help_text="Date of last check")
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  def __str__(self):
    return self.url

  class Meta:
    verbose_name = "Deleted Product URL"
    verbose_name_plural = "Deleted Product URLs"
    indexes = [
        models.Index(fields=['last_checking']),
        models.Index(fields=['url']),
    ]


class ProductNewUrl(models.Model):
  url = models.URLField(max_length=1000, help_text="URL to the new product")
  last_checking = models.DateTimeField(default=timezone.now,
                                       help_text="Date of last check")
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  def __str__(self):
    return self.url

  class Meta:
    verbose_name = "New Product URL"
    verbose_name_plural = "New Product URLs"
    indexes = [
        models.Index(fields=['last_checking']),
        models.Index(fields=['url']),
    ]
