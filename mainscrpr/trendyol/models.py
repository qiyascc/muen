from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import json
import logging

logger = logging.getLogger(__name__)

class TrendyolAPIConfig(models.Model):
    """Configuration for Trendyol API credentials"""
    name = models.CharField(_("Configuration Name"), max_length=255)
    seller_id = models.CharField(_("Seller ID"), max_length=100)
    api_key = models.CharField(_("API Key"), max_length=255)
    api_secret = models.CharField(_("API Secret"), max_length=255)
    base_url = models.URLField(_("API Base URL"), default="https://apigw.trendyol.com/integration/")
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    
    class Meta:
        verbose_name = _("Trendyol API Configuration")
        verbose_name_plural = _("Trendyol API Configurations")
        ordering = ['-is_active', '-updated_at']
    
    def __str__(self):
        return f"{self.name} - {self.seller_id}"
    
    def save(self, *args, **kwargs):
        # Ensure only one active configuration
        if self.is_active:
            TrendyolAPIConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

class TrendyolBrand(models.Model):
    """Brands in Trendyol system"""
    brand_id = models.PositiveIntegerField(_("Brand ID"), unique=True)
    name = models.CharField(_("Brand Name"), max_length=255)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    
    class Meta:
        verbose_name = _("Trendyol Brand")
        verbose_name_plural = _("Trendyol Brands")
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} (ID: {self.brand_id})"

class TrendyolCategory(models.Model):
    """Categories in Trendyol system"""
    category_id = models.PositiveIntegerField(_("Category ID"), unique=True)
    name = models.CharField(_("Category Name"), max_length=255)
    parent_id = models.PositiveIntegerField(_("Parent ID"), null=True, blank=True)
    path = models.TextField(_("Category Path"), blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    
    class Meta:
        verbose_name = _("Trendyol Category")
        verbose_name_plural = _("Trendyol Categories")
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} (ID: {self.category_id})"

class TrendyolBatchRequest(models.Model):
    """Batch request tracking for Trendyol operations"""
    STATUS_CHOICES = (
        ('waiting', _('Waiting')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    )
    
    batch_id = models.CharField(_("Batch ID"), max_length=100, unique=True)
    status = models.CharField(_("Status"), max_length=50, choices=STATUS_CHOICES, default='waiting')
    status_message = models.TextField(_("Status Message"), blank=True)
    operation_type = models.CharField(_("Operation Type"), max_length=100)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    last_checked_at = models.DateTimeField(_("Last Checked At"), auto_now_add=True)
    items_count = models.PositiveIntegerField(_("Items Count"), default=0)
    success_count = models.PositiveIntegerField(_("Success Count"), default=0)
    fail_count = models.PositiveIntegerField(_("Fail Count"), default=0)
    response_data = models.TextField(_("Response Data"), blank=True, null=True)
    
    class Meta:
        verbose_name = _("Trendyol Batch Request")
        verbose_name_plural = _("Trendyol Batch Requests")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Batch: {self.batch_id} ({self.status})"
    
    def get_response_data(self):
        """Get parsed response data"""
        if not self.response_data:
            return {}
        try:
            return json.loads(self.response_data)
        except json.JSONDecodeError:
            return {"raw": self.response_data}

class TrendyolProduct(models.Model):
    """Products in Trendyol system"""
    STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('deleted', _('Deleted')),
    )
    
    # Basic product information
    title = models.CharField(_("Title"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    barcode = models.CharField(_("Barcode"), max_length=100, db_index=True)
    product_main_id = models.CharField(_("Product Main ID"), max_length=100, db_index=True)
    stock_code = models.CharField(_("Stock Code"), max_length=100)
    
    # Identifiers
    trendyol_id = models.CharField(_("Trendyol Product ID"), max_length=100, null=True, blank=True)
    batch_id = models.CharField(_("Batch ID"), max_length=100, null=True, blank=True)
    
    # Status
    batch_status = models.CharField(_("Batch Status"), max_length=50, choices=STATUS_CHOICES, default='pending')
    status_message = models.TextField(_("Status Message"), blank=True)
    
    # Brand information
    brand_id = models.PositiveIntegerField(_("Brand ID"), null=True, blank=True)
    brand_name = models.CharField(_("Brand Name"), max_length=255, blank=True)
    
    # Category information
    category_id = models.PositiveIntegerField(_("Category ID"), null=True, blank=True)
    pim_category_id = models.PositiveIntegerField(_("PIM Category ID"), null=True, blank=True)
    category_name = models.CharField(_("Category Name"), max_length=255, blank=True)
    
    # Pricing and stock
    price = models.DecimalField(_("Price"), max_digits=10, decimal_places=2, default=0)
    sale_price = models.DecimalField(_("Sale Price"), max_digits=10, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField(_("Quantity"), default=0)
    vat_rate = models.PositiveIntegerField(_("VAT Rate"), default=18)
    currency_type = models.CharField(_("Currency"), max_length=10, default="TRY")
    dimensional_weight = models.PositiveIntegerField(_("Dimensional Weight"), default=1)
    cargo_company_id = models.PositiveIntegerField(_("Cargo Company ID"), default=10)
    
    # Images
    image_url = models.URLField(_("Main Image URL"), max_length=1000, blank=True)
    additional_images = models.JSONField(_("Additional Images"), default=list, blank=True, null=True)
    
    # Additional data
    attributes = models.JSONField(_("Attributes"), default=list, blank=True, null=True)
    
    # Relations
    lcwaikiki_product = models.ForeignKey('lcwaikiki.Product', on_delete=models.SET_NULL, verbose_name=_("LC Waikiki Product"), null=True, blank=True, related_name="trendyol_products")
    batch_request = models.ForeignKey(TrendyolBatchRequest, on_delete=models.SET_NULL, verbose_name=_("Batch Request"), null=True, blank=True, related_name="products")
    
    # Timestamps
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    last_synced_at = models.DateTimeField(_("Last Synced At"), null=True, blank=True)
    
    class Meta:
        verbose_name = _("Trendyol Product")
        verbose_name_plural = _("Trendyol Products")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['barcode']),
            models.Index(fields=['product_main_id']),
            models.Index(fields=['batch_status']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.barcode})"
    
    def sync_to_trendyol(self):
        """Sync this product to Trendyol"""
        from trendyol.trendyol_api_client import get_product_manager, ProductData
        
        try:
            self.batch_status = 'processing'
            self.status_message = 'Syncing to Trendyol...'
            self.save()
            
            # Get product manager
            product_manager = get_product_manager()
            if not product_manager:
                self.batch_status = 'failed'
                self.status_message = 'Failed to get product manager'
                self.save()
                return False
            
            # Prepare product data
            product_data = ProductData(
                barcode=self.barcode,
                title=self.title,
                product_main_id=self.product_main_id,
                brand_id=self.brand_id,
                category_id=self.category_id,
                quantity=self.quantity,
                stock_code=self.stock_code,
                price=float(self.price),
                description=self.description,
                image_url=self.image_url,
                additional_images=self.additional_images or [],
                attributes=self.attributes or [],
                vat_rate=self.vat_rate,
                currency_type=self.currency_type,
                cargo_company_id=self.cargo_company_id,
                dimensional_weight=self.dimensional_weight
            )
            
            # Create product in Trendyol
            batch_id = product_manager.create_product(product_data)
            
            # Update batch info
            self.batch_id = batch_id
            self.batch_status = 'processing'
            self.status_message = f'Product submitted to Trendyol. Batch ID: {batch_id}'
            self.last_synced_at = timezone.now()
            self.save()
            
            # Create batch request record
            TrendyolBatchRequest.objects.create(
                batch_id=batch_id,
                status='waiting',
                operation_type='create_product',
                items_count=1
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error syncing product to Trendyol: {str(e)}")
            self.batch_status = 'failed'
            self.status_message = f'Error: {str(e)}'
            self.save()
            return False
    
    def check_batch_status(self):
        """Check the status of the batch request"""
        from trendyol.trendyol_api_client import get_product_manager
        
        if not self.batch_id:
            return False
        
        try:
            # Get product manager
            product_manager = get_product_manager()
            if not product_manager:
                return False
            
            # Check batch status
            status_data = product_manager.check_batch_status(self.batch_id)
            
            # Update batch request if it exists
            batch_request = TrendyolBatchRequest.objects.filter(batch_id=self.batch_id).first()
            if batch_request:
                batch_request.status = status_data.get('status', 'unknown').lower()
                batch_request.status_message = status_data.get('message', '')
                batch_request.last_checked_at = timezone.now()
                batch_request.success_count = status_data.get('successCount', 0)
                batch_request.fail_count = status_data.get('failCount', 0)
                batch_request.items_count = status_data.get('itemCount', 0)
                batch_request.response_data = json.dumps(status_data)
                batch_request.save()
            
            # Update product status
            batch_status = status_data.get('status', '').lower()
            if batch_status == 'completed':
                self.batch_status = 'completed'
                self.status_message = 'Product synchronized successfully'
                
                # Try to get product ID from results
                results = status_data.get('results', [])
                for result in results:
                    if result.get('status') == 'SUCCESS' and result.get('productId'):
                        self.trendyol_id = str(result.get('productId'))
                        break
                        
            elif batch_status == 'failed':
                self.batch_status = 'failed'
                self.status_message = status_data.get('message', 'Unknown error')
                
                # Try to get error message from results
                results = status_data.get('results', [])
                for result in results:
                    if result.get('status') == 'FAILED':
                        error_message = result.get('failureReasons', [])
                        if error_message:
                            self.status_message = ', '.join([r.get('message', '') for r in error_message])
                        break
            else:
                self.batch_status = 'processing'
                self.status_message = f"Status: {batch_status.capitalize()} - {status_data.get('message', '')}"
            
            self.save()
            return True
            
        except Exception as e:
            logger.error(f"Error checking batch status: {str(e)}")
            return False
    
    def update_price(self):
        """Update price in Trendyol"""
        from trendyol.trendyol_api_client import get_product_manager
        
        if not self.trendyol_id:
            return False
        
        try:
            # Get product manager
            product_manager = get_product_manager()
            if not product_manager:
                return False
            
            # Update price
            sale_price = self.sale_price if self.sale_price is not None else self.price
            batch_id = product_manager.update_price(
                self.trendyol_id, 
                float(self.price), 
                float(sale_price)
            )
            
            # Create batch request record
            TrendyolBatchRequest.objects.create(
                batch_id=batch_id,
                status='waiting',
                operation_type='update_price',
                items_count=1
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating price: {str(e)}")
            return False
    
    def update_stock(self):
        """Update stock in Trendyol"""
        from trendyol.trendyol_api_client import get_product_manager
        
        if not self.trendyol_id:
            return False
        
        try:
            # Get product manager
            product_manager = get_product_manager()
            if not product_manager:
                return False
            
            # Update stock
            batch_id = product_manager.update_stock(self.trendyol_id, self.quantity)
            
            # Create batch request record
            TrendyolBatchRequest.objects.create(
                batch_id=batch_id,
                status='waiting',
                operation_type='update_stock',
                items_count=1
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating stock: {str(e)}")
            return False