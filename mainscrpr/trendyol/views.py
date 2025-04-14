from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.urls import reverse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import TrendyolProduct, TrendyolBatchRequest
import json
import logging

logger = logging.getLogger(__name__)

# API endpoints
@api_view(['GET'])
def product_list(request):
    """API endpoint to list all Trendyol products"""
    products = TrendyolProduct.objects.all()
    data = []
    
    for product in products:
        data.append({
            'id': product.id,
            'title': product.title,
            'barcode': product.barcode,
            'price': str(product.price),
            'quantity': product.quantity,
            'status': product.batch_status,
            'created_at': product.created_at.isoformat(),
        })
    
    return Response(data)

@api_view(['GET'])
def product_detail(request, product_id):
    """API endpoint to get details of a specific Trendyol product"""
    product = get_object_or_404(TrendyolProduct, id=product_id)
    
    data = {
        'id': product.id,
        'title': product.title,
        'description': product.description,
        'barcode': product.barcode,
        'product_main_id': product.product_main_id,
        'stock_code': product.stock_code,
        'trendyol_id': product.trendyol_id,
        'batch_id': product.batch_id,
        'batch_status': product.batch_status,
        'status_message': product.status_message,
        'brand_id': product.brand_id,
        'brand_name': product.brand_name,
        'category_id': product.category_id,
        'category_name': product.category_name,
        'price': str(product.price),
        'sale_price': str(product.sale_price) if product.sale_price else None,
        'quantity': product.quantity,
        'vat_rate': product.vat_rate,
        'currency_type': product.currency_type,
        'image_url': product.image_url,
        'additional_images': product.additional_images,
        'attributes': product.attributes,
        'created_at': product.created_at.isoformat(),
        'updated_at': product.updated_at.isoformat(),
        'last_synced_at': product.last_synced_at.isoformat() if product.last_synced_at else None,
    }
    
    return Response(data)

# Admin action views
@staff_member_required
def sync_product_to_trendyol(request, product_id):
    """Admin action to sync a product to Trendyol"""
    product = get_object_or_404(TrendyolProduct, id=product_id)
    
    try:
        if product.sync_to_trendyol():
            messages.success(request, f"Product '{product.title}' successfully submitted to Trendyol.")
        else:
            messages.error(request, f"Failed to submit product '{product.title}' to Trendyol. See status message for details.")
    except Exception as e:
        logger.error(f"Error syncing product to Trendyol: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
    
    return redirect('admin:trendyol_trendyolproduct_change', product_id)

@staff_member_required
def check_product_status(request, product_id):
    """Admin action to check a product's status in Trendyol"""
    product = get_object_or_404(TrendyolProduct, id=product_id)
    
    try:
        if product.check_batch_status():
            messages.success(request, f"Successfully checked status for product '{product.title}'.")
        else:
            messages.error(request, f"Failed to check status for product '{product.title}'. No batch ID found or API error.")
    except Exception as e:
        logger.error(f"Error checking product status: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
    
    return redirect('admin:trendyol_trendyolproduct_change', product_id)

@staff_member_required
def update_product_price(request, product_id):
    """Admin action to update a product's price in Trendyol"""
    product = get_object_or_404(TrendyolProduct, id=product_id)
    
    try:
        if product.update_price():
            messages.success(request, f"Price update for product '{product.title}' successfully submitted to Trendyol.")
        else:
            messages.error(request, f"Failed to update price for product '{product.title}'. No Trendyol ID found or API error.")
    except Exception as e:
        logger.error(f"Error updating product price: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
    
    return redirect('admin:trendyol_trendyolproduct_change', product_id)

@staff_member_required
def update_product_stock(request, product_id):
    """Admin action to update a product's stock in Trendyol"""
    product = get_object_or_404(TrendyolProduct, id=product_id)
    
    try:
        if product.update_stock():
            messages.success(request, f"Stock update for product '{product.title}' successfully submitted to Trendyol.")
        else:
            messages.error(request, f"Failed to update stock for product '{product.title}'. No Trendyol ID found or API error.")
    except Exception as e:
        logger.error(f"Error updating product stock: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
    
    return redirect('admin:trendyol_trendyolproduct_change', product_id)

@staff_member_required
def check_batch_status(request, batch_id):
    """Admin action to check a batch's status in Trendyol"""
    batch_request = get_object_or_404(TrendyolBatchRequest, id=batch_id)
    
    try:
        from trendyol.trendyol_api_client import get_product_manager
        
        product_manager = get_product_manager()
        if not product_manager:
            messages.error(request, "Failed to initialize API client. Check API configuration.")
            return redirect('admin:trendyol_trendyolbatchrequest_change', batch_id)
            
        # Check batch status
        status_data = product_manager.check_batch_status(batch_request.batch_id)
        
        # Update batch request
        batch_request.status = status_data.get('status', 'unknown').lower()
        batch_request.status_message = status_data.get('message', '')
        batch_request.last_checked_at = timezone.now()
        batch_request.success_count = status_data.get('successCount', 0)
        batch_request.fail_count = status_data.get('failCount', 0)
        batch_request.items_count = status_data.get('itemCount', 0)
        batch_request.response_data = json.dumps(status_data)
        batch_request.save()
        
        # Update associated products
        products = TrendyolProduct.objects.filter(batch_id=batch_request.batch_id)
        batch_status = status_data.get('status', '').lower()
        results = status_data.get('results', [])
        
        for product in products:
            if batch_status == 'completed':
                product.batch_status = 'completed'
                product.status_message = 'Product synchronized successfully'
                
                # Try to get product ID from results
                for result in results:
                    if result.get('status') == 'SUCCESS' and result.get('productId'):
                        product.trendyol_id = str(result.get('productId'))
                        break
                        
            elif batch_status == 'failed':
                product.batch_status = 'failed'
                product.status_message = status_data.get('message', 'Unknown error')
                
                # Try to get error message from results
                for result in results:
                    if result.get('status') == 'FAILED':
                        error_message = result.get('failureReasons', [])
                        if error_message:
                            product.status_message = ', '.join([r.get('message', '') for r in error_message])
                        break
            else:
                product.batch_status = 'processing'
                product.status_message = f"Status: {batch_status.capitalize()} - {status_data.get('message', '')}"
                
            product.save()
        
        messages.success(request, f"Successfully checked status for batch '{batch_request.batch_id}'.")
    except Exception as e:
        logger.error(f"Error checking batch status: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
    
    return redirect('admin:trendyol_trendyolbatchrequest_change', batch_id)