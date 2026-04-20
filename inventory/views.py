from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from .models import (
    InventoryItem, InventoryLog, PurchaseOrder, PurchaseOrderRequest, Product, 
    PurchaseOrderLog, PurchaseOrderRequestLog, PurchaseOrderItem, ProductMaterial, 
    ProductComboItem, Employee, EmploymentHistory, EmployeeEducation, EmployeeSkill, 
    EmployeeDocument, ActivityLog, Client, JobOrder, Expense, JobOrderProduct,
    Payment, LaborOutput, ProductionArea, WithdrawalSlip, WithdrawalSlipItem, DeliveryReceipt,
    DeliveryReceiptItem, ExpenseCategory, ExpenseType, Supplier, ExpenseSummary,
    EmployeeSalary, Payroll, PayrollRecord, JobOrderProductMaterial,
    AuthItem, AuthAssignment, UserProfile,
)
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.db.models import Count, Sum, F, Value, CharField
from django.db.models.functions import Coalesce, Cast
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.http import JsonResponse, HttpResponse
import json
import base64
from datetime import datetime, timedelta, time

def handle_uploaded_image(request_file):
    if not request_file:
        return ''
    try:
        binary_data = request_file.read()
        base64_data = base64.b64encode(binary_data).decode('utf-8')
        extension = request_file.name.split('.')[-1].lower()
        if extension in ['jpg', 'jpeg']:
            mime = 'image/jpeg'
        elif extension == 'png':
            mime = 'image/png'
        elif extension == 'gif':
            mime = 'image/gif'
        else:
            mime = 'image/octet-stream'
        return f"data:{mime};base64,{base64_data}"
    except Exception as e:
        print(f"Error handling image: {e}")
        return ''

class CustomLoginView(auth_views.LoginView):
    template_name = 'auth/login.html'
    
    def form_valid(self, form):
        remember_me = self.request.POST.get('remember_me')
        if not remember_me:
            # Session expires when browser closes
            self.request.session.set_expiry(0)
        else:
            # Session stays for "forever" (set to 10 years)
            self.request.session.set_expiry(10 * 365 * 24 * 60 * 60)
        return super().form_valid(form)

@login_required
def inventory_view(request):
    filter_type = request.GET.get('filter', 'all')
    
    # Base query for statistics (always based on active items)
    all_active = InventoryItem.objects.filter(is_archived=False)
    total_items = all_active.count()
    archived_count = InventoryItem.objects.filter(is_archived=True).count()
    
    # Database-level stats for speed and consistency
    out_of_stock_count = all_active.filter(Q(is_negative='yes') | Q(total_balance__lte=0)).count()
    low_stock_count = all_active.filter(is_negative='no', total_balance__gt=0, total_balance__lte=10).count()
    in_stock_count = all_active.filter(is_negative='no', total_balance__gt=10).count()
    
    # Base query for displaying items
    if filter_type == 'archived':
        query = InventoryItem.objects.filter(is_archived=True)
    else:
        query = all_active
    
    items = query.order_by('id')
    
    total_value = 0.0
    filtered_items = []
    
    for item in items:
        # Calculate stock status for individual items
        balance = item.total_balance
        is_out_of_stock = (item.is_negative == 'yes' or balance <= 0)
        
        if is_out_of_stock:
            status = 'Out of Stock'
        elif 0 < balance <= 10:
            status = 'Low Stock'
        else:
            status = 'In Stock'
        
        # Pre-calculate fields for template
        desc_parts = [p for p in [item.color, item.item_type, item.name] if p]
        item.description_full = " ".join(desc_parts)
        item.stock_status = status
        
        # Filter logic for displaying rows
        if filter_type == 'low_stock':
            if status == 'Low Stock':
                filtered_items.append(item)
        elif filter_type == 'in_stock':
            if status == 'In Stock':
                filtered_items.append(item)
        elif filter_type == 'out_of_stock':
            if status == 'Out of Stock':
                filtered_items.append(item)
        else:
            filtered_items.append(item)
        
        # Accumulate total value (only for non-archived items usually, but we'll follow previous logic)
        try:
            total_value += item.inventory_value
        except:
            pass

    statistics = {
        'total_items': total_items,
        'in_stock': in_stock_count,
        'out_of_stock': out_of_stock_count,
        'low_stock': low_stock_count,
        'archived': archived_count,
        'total_value': f"₱{total_value:,.2f}",
        'current_filter': filter_type
    }
    
    recent_logs = InventoryLog.objects.order_by('-timestamp')[:10]

    return render(request, 'inventory/inventory.html', {
        'inventory': filtered_items,
        'active_page': 'inventory',
        'stats': statistics,
        'recent_logs': recent_logs
    })

@login_required
@csrf_exempt
def all_inventory_items_view(request):
    filter_type = request.GET.get('filter', 'all')
    
    # Base stats calculation (consistent with inventory_view)
    all_active = InventoryItem.objects.filter(is_archived=False)
    total_items = all_active.count()
    archived_count = InventoryItem.objects.filter(is_archived=True).count()
    
    out_of_stock_count = all_active.filter(Q(is_negative='yes') | Q(total_balance__lte=0)).count()
    low_stock_count = all_active.filter(is_negative='no', total_balance__gt=0, total_balance__lte=10).count()
    in_stock_count = all_active.filter(is_negative='no', total_balance__gt=10).count()
    
    # Base query for display
    if filter_type == 'archived':
        query = InventoryItem.objects.filter(is_archived=True)
    else:
        query = all_active
    
    items = query.order_by('id')
    filtered_items = []
    
    for item in items:
        # Stock status logic
        balance = item.total_balance
        is_out_of_stock = (item.is_negative == 'yes' or balance <= 0)
        
        if is_out_of_stock:
            status = 'Out of Stock'
        elif 0 < balance <= 10:
            status = 'Low Stock'
        else:
            status = 'In Stock'
            
        # Pre-calculate fields for template
        item.stock_status = status
            
        # Prepare description
        desc_parts = []
        for field in ['color', 'model', 'shape', 'size', 'dimensions', 'volume', 'material', 'addon', 'other', 'occasion']:
            val = getattr(item, field, None)
            if val:
                desc_parts.append(val)
        item.description_full = ", ".join(desc_parts)

        # Apply filter
        if filter_type == 'low_stock':
            if status == 'Low Stock':
                filtered_items.append(item)
        elif filter_type == 'in_stock':
            if status == 'In Stock':
                filtered_items.append(item)
        elif filter_type == 'out_of_stock':
            if status == 'Out of Stock':
                filtered_items.append(item)
        else:
            filtered_items.append(item)

    # Stats
    stats = {
        'total_items': total_items,
        'in_stock': in_stock_count,
        'out_of_stock': out_of_stock_count,
        'low_stock': low_stock_count,
        'archived': archived_count,
        'current_filter': filter_type
    }

    if request.method == 'POST':
        # Create new item logic
        try:
            # Check if it's form data or JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
                
            item = InventoryItem.objects.create(
                item_type=data.get('item_type', ''),
                sku=data.get('sku', ''),
                name=data.get('name', ''),
                sub_unit=data.get('sub_unit', ''),
                color=data.get('color', ''),
                model=data.get('model', ''),
                shape=data.get('shape', ''),
                size=data.get('size', ''),
                dimensions=data.get('dimensions', ''),
                volume=data.get('volume', ''),
                material=data.get('material', ''),
                addon=data.get('addon', ''),
                other=data.get('other', ''),
                occasion=data.get('occasion', ''),
                description=data.get('description', ''),
                cost=float(data.get('cost', 0)) if data.get('cost') else 0.0,
                shipping_fee=float(data.get('shipping_fee', 0)) if data.get('shipping_fee') else 0.0,
                price=float(data.get('price', 0)) if data.get('price') else 0.0,
                total_balance=float(data.get('total_balance', 0)) if data.get('total_balance') else 0.0,
                updated_by=request.user.username if request.user.is_authenticated else 'admin',
                datetime_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                image=handle_uploaded_image(request.FILES.get('image'))
            )
            item.inventory_value = item.total_balance * item.price
            item.is_negative = 'yes' if item.total_balance < 0 else 'no'
            item.save()
            
            # Create log
            InventoryLog.objects.create(
                inventory_item=item,
                user=request.user.username if request.user.is_authenticated else 'admin',
                transaction_type='initial',
                quantity=str(item.total_balance),
                notes='Initial stock on creation'
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                messages.success(request, f'Item "{item.name}" added successfully.')
                return JsonResponse({'success': True, 'message': 'Item added successfully'})
            
            messages.success(request, 'Item added successfully')
            return redirect('all_inventory_items')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
            messages.error(request, f'Error adding item: {str(e)}')
            return redirect('all_inventory_items')

    return render(request, 'inventory/all_inventory_items.html', {
        'inventory': filtered_items,
        'active_page': 'all_inventory_items',
        'stats': stats,
        'recent_logs': InventoryLog.objects.order_by('-timestamp')[:10],
        'total_count': InventoryItem.objects.filter(is_archived=False).count()
    })

@login_required
def bulk_archive(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_ids = data.get('item_ids', [])
            
            items = InventoryItem.objects.filter(id__in=item_ids)
            count = items.count()
            
            for item in items:
                item.is_archived = True
                item.save()
                
                # Create log
                InventoryLog.objects.create(
                    inventory_item=item,
                    user=request.user.username if request.user.is_authenticated else 'Stephen',
                    transaction_type='archive',
                    quantity=str(item.total_balance),
                    notes=f'Bulk archived item'
                )
            
            if count > 0:
                messages.success(request, f'Successfully archived {count} items.')
            return JsonResponse({'success': True, 'count': count})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@login_required
def inventory_logs_view(request):
    period = request.GET.get('period', 'all')
    transaction_filter = request.GET.get('transaction_type', '')
    item_type_filter = request.GET.get('item_type', '')
    selected_year = int(request.GET.get('year', datetime.now().year))
    
    logs = InventoryLog.objects.all().order_by('-timestamp')
    
    # Apply Filters
    if transaction_filter:
        logs = logs.filter(transaction_type=transaction_filter)
    if item_type_filter:
        logs = logs.filter(inventory_item__item_type=item_type_filter)
    
    # Period Filter
    now = datetime.now()
    if period == 'weekly':
        logs = logs.filter(timestamp__gte=now - timedelta(days=7))
    elif period == 'monthly':
        logs = logs.filter(timestamp__month=now.month, timestamp__year=selected_year)
        
    elif period == 'yearly':
        logs = logs.filter(timestamp__year=selected_year)
        
    # Statistics
    stats = {
        'total_transactions': logs.count(),
        'purchases_count': logs.filter(transaction_type='purchase').count(),
        'purchases_qty': sum([float(l.quantity) for l in logs.filter(transaction_type='purchase') if l.quantity]),
        'withdrawals_count': logs.filter(transaction_type='withdrawal').count(),
        'withdrawals_qty': sum([float(l.quantity) for l in logs.filter(transaction_type='withdrawal') if l.quantity]),
        'damage_count': logs.filter(transaction_type='damage').count(),
        'damage_qty': sum([float(l.quantity) for l in logs.filter(transaction_type='damage') if l.quantity]),
        'returned_count': logs.filter(transaction_type='returned').count(),
        'returned_qty': sum([float(l.quantity) for l in logs.filter(transaction_type='returned') if l.quantity]),
    }
    stats['other_count'] = stats['total_transactions'] - (stats['purchases_count'] + stats['withdrawals_count'] + stats['damage_count'] + stats['returned_count'])
    
    # Chart Data
    chart_distribution = {
        'labels': ['Purchases', 'Withdrawals', 'Damage', 'Returned'],
        'data': [stats['purchases_count'], stats['withdrawals_count'], stats['damage_count'], stats['returned_count']],
        'colors': ['#10b981', '#f59e0b', '#ef4444', '#06b6d4']
    }
    
    # Trends logic
    trend_labels = []
    trend_purchases = []
    trend_withdrawals = []
    trend_damage = []
    trend_returned = []
    
    if period == 'weekly':
        for i in range(6, -1, -1):
            date = (now - timedelta(days=i)).date()
            trend_labels.append(date.strftime('%a'))
            day_logs = logs.filter(timestamp__date=date)
            trend_purchases.append(day_logs.filter(transaction_type='purchase').count())
            trend_withdrawals.append(day_logs.filter(transaction_type='withdrawal').count())
            trend_damage.append(day_logs.filter(transaction_type='damage').count())
            trend_returned.append(day_logs.filter(transaction_type='returned').count())
    elif period == 'monthly':
        # Start from the current month but in the selected year
        start_date = datetime(selected_year, now.month, now.day) if selected_year != now.year else now
        for i in range(29, -1, -1):
            date = (start_date - timedelta(days=i)).date()
            label = date.strftime('%d') if i % 5 == 0 or i == 0 or i == 29 else ''
            trend_labels.append(label)
            day_logs = logs.filter(timestamp__date=date)
            trend_purchases.append(day_logs.filter(transaction_type='purchase').count())
            trend_withdrawals.append(day_logs.filter(transaction_type='withdrawal').count())
            trend_damage.append(day_logs.filter(transaction_type='damage').count())
            trend_returned.append(day_logs.filter(transaction_type='returned').count())
    elif period == 'yearly':
        for i in range(1, 13):
            month_name = datetime(selected_year, i, 1).strftime('%b')
            trend_labels.append(month_name)
            month_logs = logs.filter(timestamp__month=i)
            trend_purchases.append(month_logs.filter(transaction_type='purchase').count())
            trend_withdrawals.append(month_logs.filter(transaction_type='withdrawal').count())
            trend_damage.append(month_logs.filter(transaction_type='damage').count())
            trend_returned.append(month_logs.filter(transaction_type='returned').count())
    else: # period == 'all'
        for i in range(11, -1, -1):
            # Calculate year and month for each of the last 12 months
            month = (now.month - i - 1) % 12 + 1
            year = now.year + (now.month - i - 1) // 12
            trend_labels.append(datetime(year, month, 1).strftime('%b %y'))
            month_logs = logs.filter(timestamp__year=year, timestamp__month=month)
            trend_purchases.append(month_logs.filter(transaction_type='purchase').count())
            trend_withdrawals.append(month_logs.filter(transaction_type='withdrawal').count())
            trend_damage.append(month_logs.filter(transaction_type='damage').count())
            trend_returned.append(month_logs.filter(transaction_type='returned').count())

    chart_trends = {
        'labels': trend_labels,
        'purchases': trend_purchases,
        'withdrawals': trend_withdrawals,
        'damage': trend_damage,
        'returned': trend_returned
    }

    # Usage Analysis
    from django.db.models import Count, Sum
    items_with_counts = InventoryItem.objects.annotate(
        transaction_count=Count('logs'),
        total_qty_moved=Sum('logs__quantity')
    )
    
    most_active_items_raw = items_with_counts.order_by('-transaction_count')[:50]
    least_used_items_raw = items_with_counts.order_by('transaction_count')[:50]
    
    def add_stock_status(items):
        for item in items:
            status = 'Out of Stock'
            balance = item.total_balance
            is_out_of_stock = (item.is_negative == 'yes' or balance <= 0)
            if not is_out_of_stock:
                if 0 < balance <= 10:
                    status = 'Low Stock'
                elif balance > 10:
                    status = 'In Stock'
            item.stock_status = status
        return items

    most_active_items = add_stock_status(list(most_active_items_raw))
    least_used_items = add_stock_status(list(least_used_items_raw))

    return render(request, 'inventory/inventory_logs.html', {
        'active_page': 'inventory_logs',
        'logs': logs[:100],
        'stats': stats,
        'chart_distribution': json.dumps(chart_distribution),
        'chart_trends': json.dumps(chart_trends),
        'period': period,
        'selected_year': selected_year,
        'year_options': range(datetime.now().year, datetime.now().year - 5, -1),
        'transaction_filter': transaction_filter,
        'item_type_filter': item_type_filter,
        'item_types': [t[0] for t in InventoryItem.objects.values_list('item_type').distinct() if t[0]],
        'most_active_items': most_active_items,
        'least_used_items': least_used_items
    })

@login_required
def toggle_archive(request, item_id):
    item = get_object_or_404(InventoryItem, id=item_id)
    item.is_archived = not item.is_archived
    item.save()
    
    status = "archived" if item.is_archived else "restored"
    
    # Create log entry
    InventoryLog.objects.create(
        inventory_item=item,
        user=request.user.username if request.user.is_authenticated else 'Stephen',
        transaction_type='archive' if item.is_archived else 'restore',
        quantity=str(item.total_balance),
        notes=f'Item {status}: {item.name}'
    )
    
    messages.success(request, f'Item {status} successfully')
    return redirect(request.META.get('HTTP_REFERER', 'inventory'))

@login_required
@csrf_exempt
def update_stock(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            transaction_type = data.get('transaction_type')
            quantity = float(data.get('quantity', 0))
            notes = data.get('notes', '')
            
            item = get_object_or_404(InventoryItem, id=item_id)
            
            # Parse current values
            try:
                current_balance = float(item.total_balance) if item.total_balance else 0
                total_purchases = float(item.total_purchases) if item.total_purchases else 0
                total_withdrawal = float(item.total_withdrawal) if item.total_withdrawal else 0
            except (ValueError, TypeError):
                current_balance = 0
                total_purchases = 0
                total_withdrawal = 0
                
            if transaction_type == 'purchase':
                item.total_purchases += quantity
                new_balance = item.total_balance + quantity
            elif transaction_type == 'withdrawal':
                item.total_withdrawal += quantity
                new_balance = item.total_balance - quantity
            elif transaction_type == 'returned':
                new_balance = current_balance + quantity
            elif transaction_type == 'damage':
                new_balance = current_balance - quantity
            else:
                return JsonResponse({'success': False, 'message': 'Invalid transaction type'}, status=400)
            
            item.total_balance = new_balance
            item.is_negative = 'yes' if new_balance < 0 else 'no'
            item.datetime_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Recalculate value
            if item.price:
                item.inventory_value = new_balance * item.price
                
            item.save()
            
            # Create Log
            InventoryLog.objects.create(
                inventory_item=item,
                user=request.user.username if request.user.is_authenticated else 'Stephen',
                transaction_type=transaction_type,
                quantity=str(quantity),
                notes=notes
            )
            
            messages.success(request, f'Stock updated successfully for {item.name}. New balance: {new_balance}')
            return JsonResponse({
                'success': True,
                'message': 'Stock updated successfully',
                'new_balance': new_balance
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

@login_required
def get_inventory_logs(request, item_id):
    item = get_object_or_404(InventoryItem, id=item_id)
    logs = item.logs.all().order_by('-timestamp')
    
    # Helper for formatting
    def format_val(val):
        try:
            f = float(val)
            return str(int(f)) if f.is_integer() else str(val)
        except:
            return val

    # Compute stock status
    balance = item.total_balance
    is_out_of_stock = (item.is_negative == 'yes' or balance <= 0)
    stock_status = 'Out of Stock'
    if not is_out_of_stock:
        if 0 < balance <= 10:
            stock_status = 'Low Stock'
        elif balance > 10:
            stock_status = 'In Stock'

    return JsonResponse({
        'success': True,
        'item': {
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'item_type': item.item_type,
            'total_balance': format_val(item.total_balance),
            'sub_unit': item.sub_unit,
            'stock_status': stock_status
        },
        'logs': [{
            'id': log.id,
            'user': log.user,
            'transaction_type': log.transaction_type,
            'quantity': format_val(log.quantity),
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'notes': log.notes
        } for log in logs]
    })

@login_required
@csrf_exempt
def update_item(request, item_id):
    item = get_object_or_404(InventoryItem, id=item_id)
    if request.method == 'POST':
        try:
            # Handle multipart/form-data or JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            # Update fields
            fields = [
                'item_type', 'sku', 'name', 'sub_unit', 'color', 
                'model', 'shape', 'size', 'dimensions', 'volume', 
                'material', 'addon', 'other', 'occasion', 'description'
            ]
            
            for field in fields:
                if field in data:
                    setattr(item, field, data.get(field))

            # Update numeric fields
            if 'cost' in data: item.cost = float(data.get('cost') or 0)
            if 'shipping_fee' in data: item.shipping_fee = float(data.get('shipping_fee') or 0)
            if 'price' in data: item.price = float(data.get('price') or 0)
            
            # Recalculate values
            item.inventory_value = item.total_balance * item.price
            item.is_negative = 'yes' if item.total_balance < 0 else 'no'
            item.updated_by = request.user.username if request.user.is_authenticated else 'admin'
            item.datetime_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Handle image if provided
            new_image = request.FILES.get('image')
            if new_image:
                item.image = handle_uploaded_image(new_image)

            item.save()

            # Create log entry
            InventoryLog.objects.create(
                inventory_item=item,
                user=request.user.username if request.user.is_authenticated else 'admin',
                transaction_type='update',
                quantity=str(item.total_balance),
                notes=f'Updated item details for: {item.name}'
            )

            messages.success(request, f'Item "{item.name}" metadata updated successfully.')
            return JsonResponse({'success': True, 'message': 'Item updated successfully'})
        except Exception as e:
            messages.error(request, f'Failed to update item: {str(e)}')
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

@login_required
def products_view(request):
    products = Product.objects.filter(is_archived=False).order_by('-created_at')
    inventory_items = InventoryItem.objects.filter(is_archived=False).order_by('name')
    
    return render(request, 'inventory/products.html', {
        'active_page': 'products',
        'products': products,
        'inventory_items': inventory_items,
        'total_count': products.count()
    })

@login_required
def purchase_order_detail(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)
    items = po.items.all()
    
    subtotal = sum([item.total for item in items])
    vat = subtotal * 0.12 # Assuming 12% VAT as per template
    
    # Suppliers for update modal
    suppliers = PurchaseOrder.objects.values_list('supplier', flat=True).distinct()
    # Inventory items for adding new items
    inventory_items = InventoryItem.objects.filter(is_archived=False).order_by('name')
    
    return render(request, 'purchase_orders/purchase_order_detail.html', {
        'po': po,
        'items': items,
        'subtotal': subtotal,
        'vat': vat,
        'total': subtotal + vat,
        'suppliers': suppliers,
        'inventory_items': inventory_items,
        'active_page': 'purchase_orders'
    })

@login_required
def purchase_order_requests_view(request):
    requests_qs = PurchaseOrderRequest.objects.all().order_by('-datetime_created')
    suppliers = PurchaseOrder.objects.values_list('supplier', flat=True).distinct()
    inventory_items = InventoryItem.objects.filter(is_archived=False).order_by('name')
    open_pos = PurchaseOrder.objects.filter(is_archived=False, status='Open')

    return render(request, 'purchase_orders/purchase_order_requests.html', {
        'active_page': 'purchase_order_requests',
        'requests': requests_qs,
        'total_count': requests_qs.count(),
        'suppliers': suppliers,
        'inventory_items': inventory_items,
        'open_pos': open_pos,
    })


@login_required
def purchase_orders_view(request):
    current_view = request.GET.get('view', 'active')
    
    # Base querysets
    all_pos = PurchaseOrder.objects.all()
    active_pos = all_pos.filter(is_archived=False)
    
    # Count stats (unfiltered by 'view')
    total_pos = active_pos.count()
    open_count = active_pos.filter(status='Open').count()
    locked_count = active_pos.filter(status='Locked').count()
    archived_count = all_pos.filter(is_archived=True).count()
    
    # Filter the main listing based on current_view
    if current_view == 'Open':
        pos = active_pos.filter(status='Open')
    elif current_view == 'Locked':
        pos = active_pos.filter(status='Locked')
    elif current_view == 'archived':
        pos = all_pos.filter(is_archived=True)
    else: # 'active' or 'total'
        pos = active_pos
        
    pos = pos.order_by('-po_date')
    
    po_requests = PurchaseOrderRequest.objects.all().order_by('-datetime_created')
    
    # Get recent PO activity logs
    po_logs = PurchaseOrderLog.objects.all().order_by('-timestamp')[:50]
    
    # Stats for the sidebar/header
    stats = {
        'pending_requests': po_requests.filter(status='Pending').count(),
        'open_po': open_count,
        'received_po': active_pos.filter(status='Received').count(),
        'total_value': sum([po.total for po in active_pos])
    }

    return render(request, 'purchase_orders/purchase_orders.html', {
        'active_page': 'purchase_orders',
        'purchase_orders': pos,
        'po_requests': po_requests,
        'po_logs': po_logs,
        'stats': stats,
        'total_pos': total_pos,
        'open_count': open_count,
        'locked_count': locked_count,
        'archived_count': archived_count,
        'current_view': current_view,
        'suppliers': PurchaseOrder.objects.values_list('supplier', flat=True).distinct(),
        'creators': PurchaseOrder.objects.values_list('created_by', flat=True).distinct(),
        'request_creators': PurchaseOrderRequest.objects.values_list('created_by', flat=True).distinct(),
        'request_adders': PurchaseOrderRequest.objects.values_list('added_by', flat=True).distinct(),
        'inventory_items': InventoryItem.objects.filter(is_archived=False).order_by('name'),
        'open_pos': active_pos.filter(status='Open')
    })

@csrf_exempt
@login_required
def create_po(request):
    if request.method == 'POST':
        supplier = request.POST.get('supplier')
        if supplier == 'custom':
            supplier = request.POST.get('custom_supplier')
        
        po_date = request.POST.get('po_date')
        comments = request.POST.get('comments', '')
        
        # Simple PO number generation
        count = PurchaseOrder.objects.count() + 1
        po_number = f"PO-{datetime.now().year}-{count:04d}"
        
        po = PurchaseOrder.objects.create(
            po_number=po_number,
            supplier=supplier,
            po_date=po_date or timezone.now(),
            comments=comments,
            status='Open',
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        PurchaseOrderLog.objects.create(
            purchase_order=po,
            action='create',
            po_number=po_number,
            details=f"Created PO for {supplier}",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        messages.success(request, f'Purchase Order {po_number} created successfully.')
        return JsonResponse({'success': True, 'message': 'PO created', 'id': po.id})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def create_purchase_order_request(request):
    if request.method == 'POST':
        request_type = request.POST.get('request_type', 'ASAP')
        product_id = request.POST.get('product_id')
        custom_name = request.POST.get('custom_name', '').strip()
        description = request.POST.get('description', '')
        quantity = float(request.POST.get('quantity') or 0)
        unit = request.POST.get('unit', 'pc')
        remarks = request.POST.get('remarks', '')
        
        name = custom_name or None
        if product_id and product_id != 'custom':
            try:
                item = InventoryItem.objects.get(id=product_id)
                name = item.name
            except InventoryItem.DoesNotExist:
                pass

        if not name:
            return JsonResponse({'success': False, 'message': 'Please select a product or enter a name.'}, status=400)
            
        pr = PurchaseOrderRequest.objects.create(
            request_type=request_type,
            name=name,
            description=description,
            quantity=quantity,
            unit=unit,
            remarks=remarks,
            status='Pending',
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        PurchaseOrderRequestLog.objects.create(
            purchase_order_request=pr,
            action='create',
            item_name=name,
            details=f"Created request: {name}",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        messages.success(request, f'Request for {name} created successfully.')
        return JsonResponse({'success': True, 'id': pr.id})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)


# ============================================================
# Reports Section Views
# ============================================================

@login_required
def reports_view(request):
    return render(request, 'reports/reports.html', {
        'active_page': 'reports'
    })

@login_required
def collections_report_view(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Mocking behavior for now
    collections = JobOrder.objects.filter(amount_paid__gt=0)
    if date_from and date_to:
        collections = collections.filter(transaction_date__range=[date_from, date_to])
        
    cash_total = sum([c.amount_paid for c in collections if c.order_type != 'Gov']) # Simple heuristic
    cheque_total = sum([c.amount_paid for c in collections if c.order_type == 'Gov'])
    
    return render(request, 'reports/report_collections.html', {
        'active_page': 'reports',
        'collections': collections,
        'cash_total': cash_total,
        'cheque_total': cheque_total,
        'total_collections': cash_total + cheque_total,
        'date_from': date_from,
        'date_to': date_to,
    })

@login_required
def expenses_report_view(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    expenses = Expense.objects.all().order_by('-date')
    if date_from and date_to:
        expenses = expenses.filter(date__range=[date_from, date_to])
        
    total_expenses = sum([e.amount for e in expenses])
    
    # Funding Source Summary (Mocked logic)
    sources = Expense.objects.values('fund_source').annotate(total=Sum('amount'))
    
    return render(request, 'reports/report_expenses.html', {
        'active_page': 'reports',
        'expenses': expenses,
        'total_expenses': total_expenses,
        'sources': sources,
        'date_from': date_from,
        'date_to': date_to,
    })

@login_required
def monthly_report_view(request):
    month = request.GET.get('month', datetime.now().month)
    year = request.GET.get('year', datetime.now().year)
    
    # In a real scenario, this would aggregate data per product
    product_stats = Product.objects.all() # Placeholder
    
    return render(request, 'reports/report_monthly.html', {
        'active_page': 'reports',
        'product_stats': product_stats,
        'selected_month': int(month),
        'selected_year': int(year),
        'months': range(1, 13),
        'years': range(datetime.now().year, datetime.now().year - 5, -1)
    })


# ============================================================
# Operations Section Views
# ============================================================

@login_required
def clients_view(request):
    if request.method == 'POST':
        try:
            Client.objects.create(
                first_name=request.POST.get('firstname'),
                last_name=request.POST.get('lastname'),
                middle_name=request.POST.get('middlename', ''),
                business_name=request.POST.get('businessname', ''),
                mobile_number=request.POST.get('mobile_number', ''),
                email_address=request.POST.get('email_address', ''),
                tin=request.POST.get('tin', ''),
                enrolled_by=request.user.username if request.user.is_authenticated else 'Stephen'
            )
            messages.success(request, 'Client added successfully.')
            return redirect('clients')
        except Exception as e:
            messages.error(request, f'Error adding client: {str(e)}')
            
    filter_type = request.GET.get('filter', 'active')
    
    all_clients = Client.objects.all()
    
    # Annotate with computed balance from non-void job orders
    annotated_clients = all_clients.annotate(
        computed_balance=Coalesce(
            Sum('job_orders__balance', filter=~Q(job_orders__status='Void')),
            Value(0.0)
        )
    )
    
    active_count = all_clients.filter(is_archived=False).count()
    archived_count = all_clients.filter(is_archived=True).count()
    
    if filter_type == 'archived':
        clients = annotated_clients.filter(is_archived=True).order_by('-date_enrolled')
    else:
        clients = annotated_clients.filter(is_archived=False).order_by('-date_enrolled')
        
    return render(request, 'clients/clients.html', {
        'active_page': 'clients',
        'clients': clients,
        'active_count': active_count,
        'archived_count': archived_count,
        'current_filter': filter_type,
        'total_count': clients.count()
    })
@login_required
@csrf_exempt
def update_client(request, client_id):
    if request.method == 'POST':
        client = get_object_or_404(Client, id=client_id)
        try:
            client.first_name = request.POST.get('firstname', client.first_name)
            client.last_name = request.POST.get('lastname', client.last_name)
            client.middle_name = request.POST.get('middlename', client.middle_name)
            client.business_name = request.POST.get('businessname', client.business_name)
            client.mobile_number = request.POST.get('mobile_number', client.mobile_number)
            client.email_address = request.POST.get('email_address', client.email_address)
            client.facebook = request.POST.get('facebook', client.facebook)
            client.save()
            return JsonResponse({'success': True, 'message': 'Client updated successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})
# ============================================================
# Operation Actions
# ============================================================
@login_required
def archive_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client.is_archived = True
    client.save()
    messages.success(request, f'Client {client.full_name} archived successfully.')
    return redirect('clients')

@login_required
def restore_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client.is_archived = False
    client.save()
    messages.success(request, f'Client {client.full_name} restored successfully.')
    return redirect(reverse('clients') + '?filter=archived')

@login_required
@csrf_exempt
def bulk_archive_clients(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            client_ids = data.get('ids', [])
            
            clients = Client.objects.filter(id__in=client_ids)
            count = clients.count()
            
            for client in clients:
                client.is_archived = True
                client.save()
            
            if count > 0:
                messages.success(request, f'Successfully archived {count} client(s).')
            return JsonResponse({'success': True, 'count': count})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)

@login_required
def client_detail_view(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    job_orders = client.joborder_set.all().order_by('-transaction_date')
    
    return render(request, 'clients/client_detail.html', {
        'active_page': 'clients',
        'client': client,
        'job_orders': job_orders,
    })
@login_required
def job_orders_view(request):
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')
    client_name = request.GET.get('client_name', '')
    status_tab = request.GET.get('status_tab', 'all')
    
    query = JobOrder.objects.all().order_by('-transaction_date', '-id')
    
    if date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_start, '%Y-%m-%d'), time.min))
            query = query.filter(transaction_date__gte=start_dt)
        except ValueError:
            pass
    if date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_end, '%Y-%m-%d'), time.max))
            query = query.filter(transaction_date__lte=end_dt)
        except ValueError:
            pass
    
    # Base Stats query
    stats_query = JobOrder.objects.all()
    if date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_start, '%Y-%m-%d'), time.min))
            stats_query = stats_query.filter(transaction_date__gte=start_dt)
        except ValueError:
            pass
    if date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_end, '%Y-%m-%d'), time.max))
            stats_query = stats_query.filter(transaction_date__lte=end_dt)
        except ValueError:
            pass
    
    stats = {
        'total': stats_query.filter(is_archived=False).count(),
        'active': stats_query.filter(status='ACTIVE', is_archived=False).count(),
        'completed': stats_query.filter(status='DONE', is_archived=False).count(),
        'void': stats_query.filter(status='VOID', is_archived=False).count(),
        'archived': stats_query.filter(is_archived=True).count(),
    }
    
    # Filter based on tab
    if status_tab == 'active':
        query = query.filter(status='ACTIVE', is_archived=False)
    elif status_tab == 'completed':
        query = query.filter(status='DONE', is_archived=False)
    elif status_tab == 'void':
        query = query.filter(status='VOID', is_archived=False)
    elif status_tab == 'archived':
        query = query.filter(is_archived=True)
    else:
        query = query.filter(is_archived=False)

    if client_name:
        query = query.filter(Q(client__first_name__icontains=client_name) | Q(client__last_name__icontains=client_name))
        
    # Filter logs by its own date parameters
    jo_logs_query = ActivityLog.objects.filter(entity_type='JobOrder')
    if log_date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            jo_logs_query = jo_logs_query.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    if log_date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            jo_logs_query = jo_logs_query.filter(timestamp__lte=end_dt)
        except ValueError:
            pass
    
    jo_logs = jo_logs_query.order_by('-timestamp')[:100]

    return render(request, 'job_orders/job_orders.html', {
        'active_page': 'job_orders',
        'job_orders': query,
        'jo_logs': jo_logs,
        'total_count': query.count(),
        'stats': stats,
        'current_tab': status_tab,
        'date_start': date_start,
        'date_end': date_end,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end
    })

@login_required
@csrf_exempt
def toggle_job_order_archive(request, jo_id):
    jo = get_object_or_404(JobOrder, id=jo_id)
    jo.is_archived = not jo.is_archived
    jo.save()
    
    status = "archived" if jo.is_archived else "restored"
    status_label = status.capitalize()
    desc = f"Job Order {status_label}:\n"
    desc += f"• WIP: {jo.wip}\n"
    desc += f"• Action: {status.upper()}"
    
    ActivityLog.objects.create(
        action='updated',
        description=desc,
        user=request.user.username if request.user.is_authenticated else 'System',
        entity_type='JobOrder',
        entity_id=jo.id
    )

    # Log for each product in this JO
    for product in jo.products.all():
        ActivityLog.objects.create(
            action='updated',
            description=f"Product {status_label}:\n• Product: {product.product_name}\n• JO: {jo.wip}",
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='JobOrderProduct',
            entity_id=product.id
        )
    
    return JsonResponse({
        'success': True, 
        'message': f'Job Order {jo.wip} {status} successfully.',
        'is_archived': jo.is_archived
    })

@csrf_exempt
@login_required
def create_job_order(request):
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client = get_object_or_404(Client, id=client_id)
        
        # Generate a simple WIP for now, can be refined later
        count = JobOrder.objects.count() + 1
        wip = f"{timezone.now().strftime('%m-%Y')}-{count:04d}"
        
        jo = JobOrder.objects.create(
            client=client,
            wip=wip,
            status='ACTIVE',
            transaction_date=timezone.now().date(),
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        desc = "New Job Order Created:\n"
        desc += f"• WIP: {wip}\n"
        desc += f"• Client: {client.full_name}\n"
        desc += f"• Date: {timezone.now().strftime('%Y-%m-%d')}"
        
        ActivityLog.objects.create(
            action='created',
            description=desc,
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='JobOrder',
            entity_id=jo.id
        )
        
        messages.success(request, f"New Job Order Created: {wip}")
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('job_order_detail', args=[jo.id])
        })
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

@login_required
def job_order_detail_view(request, jo_id):
    jo = get_object_or_404(JobOrder, id=jo_id)
    products = jo.products.all()
    payments = jo.payments.all()
    all_products = Product.objects.filter(is_archived=False)
    all_clients = Client.objects.all().order_by('last_name')
    all_inventory = InventoryItem.objects.all().order_by('name')
    needs_slip = products.filter(withdrawal_slip__isnull=True).exists()
    
    context = {
        'jo': jo,
        'products': products,
        'needs_slip': needs_slip,
        'payments': payments,
        'all_products': all_products,
        'all_clients': all_clients,
        'all_inventory': all_inventory,
        'active_page': 'job_orders'
    }
    return render(request, 'job_orders/job_order_detail.html', context)

@login_required
@csrf_exempt
def update_job_order(request, jo_id):
    if request.method == 'POST':
        jo = get_object_or_404(JobOrder, id=jo_id)
        try:
            # Store old values for logging
            old_client = jo.client.full_name
            old_order_type = jo.order_type
            old_transaction_mode = jo.transaction_mode
            old_status = jo.status
            old_delivery_mode = jo.delivery_mode
            old_remarks = jo.remarks
            old_transaction_date = str(jo.transaction_date)
            old_due_date = str(jo.due_date) if jo.due_date else "N/A"
            old_fully_paid = "Yes" if jo.is_fully_paid else "No"
            
            changes = []
            
            client_id = request.POST.get('client_id')
            if client_id:
                new_client_obj = get_object_or_404(Client, id=client_id)
                if jo.client != new_client_obj:
                    changes.append(f"Client: {old_client} → {new_client_obj.full_name}")
                    jo.client = new_client_obj
            
            new_order_type = request.POST.get('order_type', jo.order_type)
            if jo.order_type != new_order_type:
                changes.append(f"Order Type: {jo.order_type} → {new_order_type}")
                jo.order_type = new_order_type
                
            new_transaction_mode = request.POST.get('transaction_mode', jo.transaction_mode)
            if jo.transaction_mode != new_transaction_mode:
                changes.append(f"Transaction Mode: {jo.transaction_mode} → {new_transaction_mode}")
                jo.transaction_mode = new_transaction_mode
                
            new_status = request.POST.get('status', jo.status)
            if jo.status != new_status:
                changes.append(f"Status: {jo.status} → {new_status}")
                jo.status = new_status
                
                # If changed to Void, cascade to products and Withdrawal Slips
                if new_status.upper() == 'VOID':
                    for product in jo.products.all():
                        if product.status != 'Void':
                            product.status = 'Void'
                            product.save()
                    
                    slips = WithdrawalSlip.objects.filter(wip=jo.wip)
                    for slip in slips:
                        if slip.status != 'Void':
                            slip.status = 'Void'
                            slip.save()
                            ActivityLog.objects.create(
                                action='status_change',
                                description=f"Withdrawal Slip Voided (auto-synced with Job Order update):\n• Slip ID: WS-{slip.id:05d}\n• WIP: {jo.wip}",
                                user=request.user.username if request.user.is_authenticated else 'System',
                                entity_type='WithdrawalSlip',
                                entity_id=slip.id
                            )
                
            new_delivery_mode = request.POST.get('delivery_mode', jo.delivery_mode)
            if jo.delivery_mode != new_delivery_mode:
                changes.append(f"Delivery Mode: {jo.delivery_mode} → {new_delivery_mode}")
                jo.delivery_mode = new_delivery_mode
                
            new_remarks = request.POST.get('remarks', jo.remarks)
            if jo.remarks != new_remarks:
                changes.append(f"Remarks: {jo.remarks or 'N/A'} → {new_remarks or 'N/A'}")
                jo.remarks = new_remarks
            
            transaction_date = request.POST.get('transaction_date')
            if transaction_date and str(jo.transaction_date) != transaction_date:
                changes.append(f"Transaction Date: {jo.transaction_date} → {transaction_date}")
                jo.transaction_date = transaction_date
            
            due_date = request.POST.get('due_date')
            if due_date and (str(jo.due_date) if jo.due_date else "") != due_date:
                changes.append(f"Due Date: {jo.due_date or 'N/A'} → {due_date or 'N/A'}")
                jo.due_date = due_date
            
            is_fully_paid = request.POST.get('is_fully_paid')
            if is_fully_paid is not None:
                new_fully_paid_val = is_fully_paid.lower() == 'true' or is_fully_paid == '1'
                if jo.is_fully_paid != new_fully_paid_val:
                    changes.append(f"Fully Paid: {old_fully_paid} → {'Yes' if new_fully_paid_val else 'No'}")
                    jo.is_fully_paid = new_fully_paid_val
            
            # Recalculate everything via model methods
            jo.update_totals()
            jo.save()
            
            # Create Activity Log if changes were made
            if changes:
                desc = "Updated Job Order Details:\n" + "\n".join([f"• {c}" for c in changes])
                ActivityLog.objects.create(
                    action='updated',
                    description=desc,
                    user=request.user.username if request.user.is_authenticated else 'System',
                    entity_type='JobOrder',
                    entity_id=jo.id
                )
            
            return JsonResponse({'success': True, 'message': 'Job order updated successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

@csrf_exempt
@login_required
def add_jo_product(request, jo_id):
    if request.method == 'POST':
        jo = get_object_or_404(JobOrder, id=jo_id)
        product_id = request.POST.get('product_id')
        product_obj = get_object_or_404(Product, id=product_id)
        
        quantity = float(request.POST.get('quantity', 1))
        unit_price = request.POST.get('unit_price')
        
        if not unit_price:
            unit_price = product_obj.srp
        else:
            unit_price = float(unit_price)
            
        # Generate PID (Product ID from system) - can be refined
        pid_count = JobOrderProduct.objects.count() + 1
        pid = f"PID{pid_count:06d}"
        
        jop = JobOrderProduct.objects.create(
            job_order=jo,
            product=product_obj,
            product_name=product_obj.name,
            product_type=product_obj.product_type,
            quantity=quantity,
            unit_price=unit_price,
            pid=pid,
            transaction_date=timezone.now().date(),
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        # Copy product materials to job order product materials
        for material in product_obj.materials.all():
            JobOrderProductMaterial.objects.create(
                job_order_product=jop,
                inventory_item=material.inventory_item,
                category=material.category,
                item_name=material.item_name,
                quantity=material.quantity,
                cost=material.cost,
                total_cost=material.total_cost
            )
        
        # Update JO total amount due and balance via model method
        jo.update_totals()
        
        # Create activity log
        ActivityLog.objects.create(
            user=request.user.username if request.user.is_authenticated else 'Stephen',
            action="created",
            description=f"Product Added to JO:\n• Product: {product_obj.name}\n• JO: {jo.wip}\n• Quantity: {jop.quantity}",
            entity_type='JobOrderProduct',
            entity_id=jop.id
        )
        
        messages.success(request, f"Product {product_obj.name} added to Job Order.")
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@csrf_exempt
@login_required
@require_POST
def api_update_jo_product_materials(request, jopm_id):
    try:
        jopm = get_object_or_404(JobOrderProductMaterial, id=jopm_id)
        inventory_item_id = request.POST.get('inventory_item_id')
        quantity = request.POST.get('quantity')
        
        if inventory_item_id:
            inventory_item = get_object_or_404(InventoryItem, id=inventory_item_id)
            jopm.inventory_item = inventory_item
            jopm.item_name = inventory_item.name
            jopm.cost = inventory_item.cost
            
        if quantity:
            jopm.quantity = float(quantity)
            
        jopm.total_cost = jopm.quantity * jopm.cost
        jopm.save()
        
        # Recalculate parent JobOrderProduct materials_cost
        jop = jopm.job_order_product
        total_m_cost = sum(m.total_cost for m in jop.jop_materials.all())
        jop.materials_cost = total_m_cost
        # Reset withdrawal slip to allow regeneration since materials changed
        jop.withdrawal_slip = None
        jop.save()
        
        return JsonResponse({'success': True, 'message': 'Material updated successfully.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# ============================================================
# Batch 2 Sections Views
# ============================================================

@login_required
def jo_products_view(request):
    pid = request.GET.get('pid', '')
    wip = request.GET.get('wip', '')
    show_all = request.GET.get('all', 'false') == 'true'
    
    # Date filters for table
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    
    # Date filters for logs
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')
    
    # Base query: exclude archived job orders by default unless 'all' is true
    products = JobOrderProduct.objects.all()
    
    if not show_all:
        products = products.filter(job_order__is_archived=False).exclude(job_order__status='VOID')
        
    products = products.order_by('-transaction_date')
    
    # Table Date Filtering
    if date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_start, '%Y-%m-%d'), time.min)).date()
            products = products.filter(transaction_date__gte=start_dt)
        except (ValueError, TypeError):
            pass
    if date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_end, '%Y-%m-%d'), time.max)).date()
            products = products.filter(transaction_date__lte=end_dt)
        except (ValueError, TypeError):
            pass

    if pid:
        products = products.filter(pid__icontains=pid)
    if wip:
        products = products.filter(job_order__wip__icontains=wip)

    # Base query for stats (consistent with filters applied so far including dates, pid, and wip)
    stats_base = products
    
    stats = {
        'total': stats_base.count(),
        'pending': stats_base.filter(status='Pending').count(),
        'released': stats_base.filter(is_released=True).count(),
        'production': stats_base.exclude(status='Pending').exclude(is_released=True).count(),
        'current_filter': request.GET.get('filter', 'all')
    }

    # Final filtering for the stat card selection
    if stats['current_filter'] == 'pending':
        products = products.filter(status='Pending')
    elif stats['current_filter'] == 'released':
        products = products.filter(is_released=True)
    elif stats['current_filter'] == 'production':
        products = products.exclude(status='Pending').exclude(is_released=True)
        
    total_count = products.count()

    # Filter logs by its own date parameters
    jo_products_logs = ActivityLog.objects.filter(entity_type='JobOrderProduct')
    if log_date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            jo_products_logs = jo_products_logs.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    if log_date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            jo_products_logs = jo_products_logs.filter(timestamp__lte=end_dt)
        except ValueError:
            pass
    
    return render(request, 'job_orders/jo_products.html', {
        'active_page': 'jo_products',
        'products': products,
        'total_count': total_count,
        'show_all': show_all,
        'stats': stats,
        'jo_products_logs': jo_products_logs,
        'date_start': date_start,
        'date_end': date_end,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end
    })

@login_required
def payments_view(request):
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')
    or_number = request.GET.get('or_number', '')
    wip = request.GET.get('wip', '')
    
    payments = Payment.objects.all().order_by('-date')
    
    # Base Stats query - initialized early to collect date filters
    stats_base = Payment.objects.all()
    
    if date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_start, '%Y-%m-%d'), time.min))
            payments = payments.filter(date__gte=start_dt)
            stats_base = stats_base.filter(date__gte=start_dt)
        except ValueError:
            pass
    if date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(date_end, '%Y-%m-%d'), time.max))
            payments = payments.filter(date__lte=end_dt)
            stats_base = stats_base.filter(date__lte=end_dt)
        except ValueError:
            pass

    if or_number:
        payments = payments.filter(or_number__icontains=or_number)
    if wip:
        payments = payments.filter(job_order__wip__icontains=wip)
    
    current_filter = request.GET.get('filter', 'all')
    if current_filter == 'cash':
        payments = payments.filter(payment_type='CASH')
    elif current_filter == 'cheque':
        payments = payments.filter(payment_type='Cheque')
    elif current_filter == 'online':
        payments = payments.exclude(payment_type='CASH').exclude(payment_type='Cheque')
        
    # Calculate stats based on potentially date-filtered base
    from django.db.models import Sum
    stats = {
        'total_count': stats_base.count(),
        'total_amount': stats_base.aggregate(Sum('amount'))['amount__sum'] or 0,
        'cash_count': stats_base.filter(payment_type='CASH').count(),
        'online_count': stats_base.exclude(payment_type='CASH').exclude(payment_type='Cheque').count(),
        'current_filter': current_filter
    }

    # Filter logs by its own date parameters
    payment_logs_query = ActivityLog.objects.filter(entity_type='Payment').order_by('-timestamp')
    if log_date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            payment_logs_query = payment_logs_query.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    if log_date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            payment_logs_query = payment_logs_query.filter(timestamp__lte=end_dt)
        except ValueError:
            pass

    payment_logs = payment_logs_query[:100]

    return render(request, 'payments/payments.html', {
        'active_page': 'payments',
        'payments': payments,
        'payment_logs': payment_logs,
        'total_count': payments.count(),
        'stats': stats,
        'date_start': date_start,
        'date_end': date_end,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end,
    })

@login_required
@require_POST
def api_update_payment(request, payment_id):
    try:
        payment = get_object_or_404(Payment, pk=payment_id)
        
        payment_date = request.POST.get('payment_date')
        payment_type = request.POST.get('payment_type')
        amount_str = request.POST.get('amount')
        or_number = request.POST.get('or_number', '')
        ewt_str = request.POST.get('ewt', '0')
        
        if not all([payment_date, payment_type, amount_str]):
            return JsonResponse({'success': False, 'message': 'Date, Payment Type, and Amount are required.'})
            
        old_amount = payment.amount
        new_amount = float(amount_str)
        new_ewt = float(ewt_str)
        
        # Prepare log description
        changes = []
        if old_amount != new_amount:
            changes.append(f"Amount: ₱{old_amount:,.2f} → ₱{new_amount:,.2f}")
        
        # Format date for comparison
        old_date_str = payment.date.strftime('%Y-%m-%d') if hasattr(payment.date, 'strftime') else str(payment.date)
        if old_date_str != payment_date:
            changes.append(f"Date: {old_date_str} → {payment_date}")
            
        if payment.payment_type != payment_type:
            changes.append(f"Type: {payment.payment_type} → {payment_type}")
        if payment.or_number != or_number:
            changes.append(f"OR: {payment.or_number or 'N/A'} → {or_number or 'N/A'}")
            
        desc = "Updated Payment Details:\n" + ("\n".join([f"• {c}" for c in changes]) if changes else "• No significant field changes.")
        
        # Update the payment record
        payment.date = payment_date
        payment.payment_type = payment_type
        payment.or_number = or_number
        payment.amount = new_amount
        payment.ewt = new_ewt
        payment.updated_by = request.user.username if request.user.is_authenticated else 'System'
        payment.save()
        
        # Create Activity Log
        ActivityLog.objects.create(
            action='updated',
            description=desc,
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='Payment',
            entity_id=payment.id
        )
        
        # Update JobOrder totals if linked
        if payment.job_order:
            jo = payment.job_order
            jo.amount_paid = (jo.amount_paid - old_amount) + new_amount
            jo.save() 
            
        return JsonResponse({'success': True})
        
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid numeric value.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def jo_releasing_view(request):
    wip = request.GET.get('wip', '')
    name = request.GET.get('name', '')
    is_released = request.GET.get('is_released', '')
    is_packed = request.GET.get('is_packed', '')
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')
    
    # Show only non-archived, non-voided JO products
    products = JobOrderProduct.objects.filter(
        job_order__is_archived=False
    ).exclude(
        job_order__status='VOID'
    ).order_by('-is_released', '-released_at', '-id')
    
    if wip:
        products = products.filter(job_order__wip__icontains=wip)
    if name:
        products = products.filter(name__icontains=name)
        
    if is_released == 'Yes':
        products = products.filter(is_released=True)
    elif is_released == 'No':
        products = products.filter(is_released=False)
        
    if is_packed == 'Yes':
        products = products.filter(is_packed=True)
    elif is_packed == 'No':
        products = products.filter(is_packed=False)

    # Use Coalesce to handle fallback to parent job_order.due_date
    products = products.annotate(
        effective_due_date=Coalesce('due_date', 'job_order__due_date')
    )
    
    if date_start:
        try:
            start_date_obj = datetime.strptime(date_start, '%Y-%m-%d').date()
            products = products.filter(effective_due_date__gte=start_date_obj)
        except ValueError:
            pass
    if date_end:
        try:
            end_date_obj = datetime.strptime(date_end, '%Y-%m-%d').date()
            products = products.filter(effective_due_date__lte=end_date_obj)
        except ValueError:
            pass
    
    # Calculate stats - derive from products but BEFORE category filters ('ready', etc.)
    stats_base = products

    current_filter = request.GET.get('filter', '')
    if current_filter == 'ready':
        products = products.filter(is_packed=True, is_released=False)
    elif current_filter == 'pending_unpack':
        products = products.filter(is_packed=False, is_released=False)
    elif current_filter == 'released':
        products = products.filter(is_released=True)
    elif not is_released and not current_filter:
        products = products.filter(is_released=False)
        
    stats = {
        'total': stats_base.count(),
        'ready': stats_base.filter(is_packed=True, is_released=False).count(),
        'pending_unpack': stats_base.filter(is_packed=False, is_released=False).count(),
        'released': stats_base.filter(is_released=True).count(),
        'current_filter': current_filter or ('all' if is_released or is_packed or wip or name else 'pending')
    }

    # Activity Logs
    releasing_logs_query = ActivityLog.objects.filter(
        entity_type='JobOrderProduct',
        action__in=['packed', 'unpacked', 'released', 'unreleased', 'acknowledged', 'transferred', 'sent to production', 'tag as packed', 'release', 'created', 'updated']
    ).order_by('-timestamp')

    if log_date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            releasing_logs_query = releasing_logs_query.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    if log_date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            releasing_logs_query = releasing_logs_query.filter(timestamp__lte=end_dt)
        except ValueError:
            pass

    releasing_logs = releasing_logs_query[:100]

    return render(request, 'job_orders/jo_releasing.html', {
        'active_page': 'jo_releasing',
        'products': products,
        'releasing_logs': releasing_logs,
        'total_count': products.count(),
        'stats': stats,
        'date_start': date_start,
        'date_end': date_end,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end,
    })

    return render(request, 'job_orders/jo_releasing.html', {
        'active_page': 'jo_releasing',
        'products': products,
        'total_count': products.count(),
        'stats': stats
    })

@login_required
def get_jo_product_release_details(request, product_id):
    product = get_object_or_404(JobOrderProduct, id=product_id)
    return JsonResponse({
        'success': True,
        'product_name': product.product_name,
        'quantity': product.quantity,
        'qty_released': product.qty_released,
        'is_released': product.is_released,
        'wip': product.job_order.wip,
        'client_name': product.name or product.job_order.client.full_name
    })

@csrf_exempt
@login_required
def api_pack_jo_product(request, product_id):
    product = get_object_or_404(JobOrderProduct, id=product_id)
    product.is_packed = not product.is_packed
    product.packed_at = timezone.now() if product.is_packed else None
    product.save()
    
    # Create activity log
    ActivityLog.objects.create(
        user=request.user.username,
        action="packed" if product.is_packed else "unpacked",
        description=f'Product {"Packed" if product.is_packed else "Unpacked"}:\n• Product: {product.product_name}\n• JO: {product.job_order.wip}',
        entity_type='JobOrderProduct',
        entity_id=product.id
    )
    
    return JsonResponse({
        'success': True,
        'is_packed': product.is_packed,
        'message': f'Product {"packed" if product.is_packed else "unpacked"} successfully.'
    })

@csrf_exempt
@login_required
def api_release_jo_product(request, product_id):
    product = get_object_or_404(JobOrderProduct, id=product_id)
    
    # Handle both AJAX full release and potentially partial later
    if product.is_released:
        product.is_released = False
        product.released_at = None
        product.qty_released = 0
        product.status = 'Pending' # Revert to Pending when un-released
    else:
        product.is_released = True
        product.released_at = timezone.now()
        product.qty_released = product.quantity
        product.status = 'Released'
        product.current_area = None # Move out of production when released
        
    product.save()
    
    # Create activity log
    ActivityLog.objects.create(
        user=request.user.username,
        action="released" if product.is_released else "unreleased",
        description=f'Product {"Released" if product.is_released else "Reverted from Release"}:\n• Product: {product.product_name}\n• JO: {product.job_order.wip}',
        entity_type='JobOrderProduct',
        entity_id=product.id
    )
    
    # Force update of parent JobOrder release status
    product.job_order.update_release_status()
    
    return JsonResponse({
        'success': True,
        'is_released': product.is_released,
        'qty_released': product.qty_released,
        'job_order_status': product.job_order.product_release_status,
        'message': f'Product {"released" if product.is_released else "unreleased"} successfully.'
    })

@login_required
def labor_output_view(request):
    employee_id = request.GET.get('employee')
    wip = request.GET.get('wip')
    pid = request.GET.get('pid')
    product_name = request.GET.get('product_name')
    particulars = request.GET.get('particulars')
    output_type = request.GET.get('output_type')
    date_start = request.GET.get('date_start')
    date_end = request.GET.get('date_end')
    log_date_start = request.GET.get('log_date_start')
    log_date_end = request.GET.get('log_date_end')
    
    labor_logs = LaborOutput.objects.all().order_by('-date_accomplished', '-id')
    
    if date_start:
        labor_logs = labor_logs.filter(date_accomplished__gte=date_start)
    if date_end:
        labor_logs = labor_logs.filter(date_accomplished__lte=date_end)
        
    # Fetch Labor Activity Logs
    activity_logs_query = ActivityLog.objects.filter(entity_type='Labor').order_by('-timestamp')
    if log_date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            activity_logs_query = activity_logs_query.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    if log_date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            activity_logs_query = activity_logs_query.filter(timestamp__lte=end_dt)
        except ValueError:
            pass
            
    activity_logs = activity_logs_query[:100] # Limit to last 100 for now
        
    employees = Employee.objects.all().order_by('first_name', 'last_name')
    job_orders = JobOrder.objects.filter(is_archived=False).exclude(status='VOID').order_by('-id')
    
    return render(request, 'employees/labor_output.html', {
        'items': labor_logs, 
        'employees': employees,
        'job_orders': job_orders,
        'output_types': LaborOutput.OUTPUT_TYPES,
        'activity_logs': activity_logs,
        'active_page': 'labor_output',
        'date_start': date_start,
        'date_end': date_end,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end
    })

@login_required
@require_POST
def add_labor_ajax(request):
    try:
        employee_id = request.POST.get('employee')
        jo_id = request.POST.get('job_order')
        jop_id = request.POST.get('job_order_product')
        date_accomplished = request.POST.get('date_accomplished')
        output_type = request.POST.get('output_type')
        quantity = request.POST.get('quantity', 0)
        unit_price = request.POST.get('unit_price', 0)
        particulars = request.POST.get('particulars', '')
        
        employee = get_object_or_404(Employee, id=employee_id)
        jo = get_object_or_404(JobOrder, id=jo_id)
        jop = get_object_or_404(JobOrderProduct, id=jop_id) if jop_id else None

        quantity = float(quantity)
        unit_price = float(unit_price)
        total = quantity * unit_price
        
        labor = LaborOutput.objects.create(
            employee=employee,
            job_order=jo,
            job_order_product=jop,
            date_accomplished=date_accomplished or timezone.now().date(),
            particulars=particulars,
            output_type=output_type,
            quantity=quantity,
            unit_price=unit_price,
            total=total,
            status='Pending'
        )

        # Create Activity Log
        ActivityLog.objects.create(
            action='created',
            description=f"Added Labor Entry:\n• Employee: {employee.full_name}\n• JO: {jo.wip}\n• Type: {output_type}\n• Qty: {quantity}",
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='Labor',
            entity_id=labor.id
        )

        return JsonResponse({'status': 'success', 'message': 'Labor output recorded successfully.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def approve_labor_view(request, labor_id):
    try:
        labor = get_object_or_404(LaborOutput, id=labor_id)
        qty_approved = request.POST.get('quantity_approved')
        
        approved_qty = float(qty_approved)
        approved_total = approved_qty * labor.unit_price
        
        labor.status = 'Approved'
        labor.quantity_approved = approved_qty
        labor.datetime_approved = timezone.now()
        labor.approved_by = request.user.username
        labor.total_labor_approved = approved_total
        labor.save()
        
        # Create Activity Log
        ActivityLog.objects.create(
            action='status_change',
            description=f"Approved Labor Entry:\n• ID: {labor.id}\n• Employee: {labor.employee.full_name}\n• Approved Qty: {approved_qty}\n• Total: ₱{approved_total}",
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='Labor',
            entity_id=labor.id
        )
        
        return JsonResponse({'status': 'success', 'message': 'Labor output approved.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def get_jo_products(request, jo_id):
    products = JobOrderProduct.objects.filter(job_order_id=jo_id)
    data = [{'id': p.id, 'name': p.product_name} for p in products]
    return JsonResponse({'products': data})

@login_required
@require_POST
def delete_labor_ajax(request, labor_id):
    try:
        labor = get_object_or_404(LaborOutput, id=labor_id)
        desc = f"Deleted Labor Entry (ID: {labor.id}) for {labor.employee.full_name} (JO: {labor.job_order.wip})"
        labor.delete()
        
        # Create Activity Log
        ActivityLog.objects.create(
            action='deleted',
            description=desc,
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='Labor',
            entity_id=labor_id
        )
        
        return JsonResponse({'status': 'success', 'message': 'Labor output deleted.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def area_view(request, area_id):
    area = get_object_or_404(ProductionArea, id=area_id)
    products = JobOrderProduct.objects.filter(current_area=area, is_released=False).order_by('due_date')
    areas = ProductionArea.objects.all().exclude(id=area.id)
    
    # Calculate stats for the sidebar (badges)
    area_stats = {}
    for a in ProductionArea.objects.all():
        area_stats[a.id] = JobOrderProduct.objects.filter(current_area=a, is_released=False).count()
        
    context = {
        'area': area,
        'products': products,
        'all_areas': areas,
        'area_stats': area_stats,
        'active_page': f'area_{area.id}'
    }
    return render(request, 'inventory/area_view.html', context)

@login_required
@require_POST
def acknowledge_product(request, product_id):
    product = get_object_or_404(JobOrderProduct, id=product_id)
    product.is_acknowledged = True
    product.acknowledged_by = request.user.username
    product.acknowledged_at = timezone.now()
    
    # Update status for dashboard sync
    area_name = product.current_area.name if product.current_area else "Production"
    product.status = f"In-Progress: {area_name}"
    
    product.save()
    
    # Create activity log
    ActivityLog.objects.create(
        user=request.user.username,
        action="acknowledged",
        description=f"Product Acknowledged:\n• Product: {product.product_name}\n• JO: {product.job_order.wip}\n• Area: {product.current_area.name if product.current_area else 'N/A'}",
        entity_type='JobOrderProduct',
        entity_id=product.id
    )
    
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def transfer_product(request, product_id):
    product = get_object_or_404(JobOrderProduct, id=product_id)
    next_area_id = request.POST.get('next_area')
    remarks = request.POST.get('remarks', '')
    
    if not next_area_id:
        return JsonResponse({'status': 'error', 'message': 'Next area is required'}, status=400)
        
    next_area = get_object_or_404(ProductionArea, id=next_area_id)
    
    old_area_name = product.current_area.name if product.current_area else "None"
    product.current_area = next_area
    product.is_acknowledged = False # Reset for next area
    product.last_transfer_remarks = remarks
    
    # Update status for dashboard sync
    product.status = f"Pending: {next_area.name}"
    
    product.save()
    
    # Create activity log
    ActivityLog.objects.create(
        user=request.user.username,
        action="transferred",
        description=f"Product Transferred:\n• Product: {product.product_name}\n• JO: {product.job_order.wip}\n• From: {old_area_name}\n• To: {next_area.name}\n• Remarks: {remarks}",
        entity_type='JobOrderProduct',
        entity_id=product.id
    )
    
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def send_to_production(request, product_id):
    product = get_object_or_404(JobOrderProduct, id=product_id)
    
    # Get the first production area (Production Head)
    first_area = ProductionArea.objects.all().order_by('display_order').first()
    
    if not first_area:
        return JsonResponse({'status': 'error', 'message': 'No production areas defined'}, status=400)
    
    product.current_area = first_area
    product.is_acknowledged = False
    
    product.status = f"Pending: {first_area.name}"
    
    product.save()
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user.username if request.user.is_authenticated else 'Stephen',
        action="sent_to_production",
        description=f"Sent to Production:\n• Product: {product.product_name}\n• JO: {product.job_order.wip}\n• Area: {first_area.name}",
        entity_type='JobOrderProduct',
        entity_id=product.id
    )
    
    return JsonResponse({'status': 'success', 'new_status': product.status})

@login_required
def force_sync_production(request):
    """Admin utility to reconcile production statuses and Job Order release states."""
    products = JobOrderProduct.objects.all()
    updated_count = 0
    
    for product in products:
        changed = False
        
        # 1. Ensure released products have no current_area and correct status
        if product.is_released:
            if product.current_area is not None:
                product.current_area = None
                changed = True
            if product.status != 'Released':
                product.status = 'Released'
                changed = True
        
        # 2. Ensure active production items have synchronized statuses
        elif product.current_area:
            area_name = product.current_area.name
            target_status = f"In-Progress: {area_name}" if product.is_acknowledged else f"Pending: {area_name}"
            
            if product.status != target_status:
                product.status = target_status
                changed = True
        
        if changed:
            product.save()
            updated_count += 1
            
    # 3. Force update all Job Order release statuses
    jos = JobOrder.objects.all()
    for jo in jos:
        jo.update_release_status()
        
    return JsonResponse({
        'status': 'success', 
        'message': f'Successfully synchronized {updated_count} products and {jos.count()} job orders.'
    })

@login_required
@require_POST
def api_generate_withdrawal_slip(request, jo_id):
    jo = get_object_or_404(JobOrder, id=jo_id)
    
    # Get products that need a slip (any product in the JO that doesn't have one)
    pending_products = JobOrderProduct.objects.filter(
        job_order=jo,
        withdrawal_slip__isnull=True
    )
    
    if not pending_products.exists():
        return JsonResponse({'success': False, 'message': 'No products found needing a withdrawal slip.'})
    
    # Reuse existing Pending Withdrawal Slip for this WIP if it exists
    slip = WithdrawalSlip.objects.filter(wip=jo.wip, status='Pending').order_by('-id').first()
    
    if not slip:
        # Create a new Withdrawal Slip if no pending one exists
        slip_name = f"{jo.client.full_name} Materials - {timezone.now().date()}"
        slip = WithdrawalSlip.objects.create(
            wip=jo.wip,
            name=slip_name,
            status='Pending',
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
    
    # Link products and create slip items
    for product in pending_products:
        product.withdrawal_slip = slip
        product.save()
        
        # Use snapshotted materials (JobOrderProductMaterial) if available
        jop_materials = product.jop_materials.all()
        if jop_materials.exists():
            for mat in jop_materials:
                req_qty = mat.quantity * product.quantity
                
                # Prevent duplication if the material is already in this slip
                if not WithdrawalSlipItem.objects.filter(withdrawal_slip=slip, jop_material=mat).exists():
                    WithdrawalSlipItem.objects.create(
                        withdrawal_slip=slip,
                        inventory_item=mat.inventory_item,
                        jop_material=mat,
                        product_name=product.product_name,
                        item_name=mat.item_name,
                        quantity=req_qty,
                        withdrawal_slip_number=f"WS-{slip.id}"
                    )
        # Fallback to base Product materials if no snapshot exists (for older JOs)
        elif product.product:
            materials = ProductMaterial.objects.filter(product=product.product)
            for mat in materials:
                req_qty = mat.quantity * product.quantity
                WithdrawalSlipItem.objects.create(
                    withdrawal_slip=slip,
                    inventory_item=mat.inventory_item,
                    product_name=product.product_name,
                    item_name=mat.item_name,
                    quantity=req_qty,
                    withdrawal_slip_number=f"WS-{slip.id}"
                )
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user.username if request.user.is_authenticated else 'Stephen',
        action="generated",
        entity_type='WithdrawalSlip',
        entity_id=slip.id,
        description=f"Generated {f'WS-{slip.id}'} for {jo.wip}"
    )
    
    return JsonResponse({'success': True, 'slip_id': slip.id})

@login_required
def api_get_withdrawal_slip_details(request, product_id):
    product = get_object_or_404(JobOrderProduct, id=product_id)
    
    data = []
    # If the product is linked to a slip, show all items in that slip
    if product.withdrawal_slip:
        items = WithdrawalSlipItem.objects.filter(withdrawal_slip=product.withdrawal_slip)
        for item in items:
            data.append({
                'item_name': item.item_name,
                'quantity': f"{item.quantity:.2f}",
                'quantity_approved': f"{item.quantity_approved:.2f}",
                'ws_number': item.withdrawal_slip_number,
                'status': item.withdrawal_slip.status
            })
    # If not linked to a slip yet, show materials for this product (preview mode)
    else:
        # Try snapshotted materials first
        jop_materials = product.jop_materials.all()
        if jop_materials.exists():
            for mat in jop_materials:
                data.append({
                    'item_name': mat.item_name,
                    'quantity': f"{mat.quantity * product.quantity:.2f}",
                    'quantity_approved': f"{mat.quantity_released:.2f}",
                    'ws_number': "",
                    'status': "PREVIEW"
                })
        # Fallback to base Product if no snapshot
        elif product.product:
            materials = ProductMaterial.objects.filter(product=product.product)
            for mat in materials:
                data.append({
                    'item_name': mat.item_name,
                    'quantity': f"{mat.quantity * product.quantity:.2f}",
                    'ws_number': ""
                })
    
    return JsonResponse({'success': True, 'items': data})

@login_required
def print_withdrawal_slip(request, slip_id):
    slip = get_object_or_404(WithdrawalSlip, id=slip_id)
    
    # Try to find the associated Job Order to get client name and original date
    jo = JobOrder.objects.filter(wip=slip.wip).first()
    
    client_name = jo.client.full_name if jo and jo.client else ""
    transaction_date = jo.transaction_date if jo else slip.created_at
    wip = jo.wip if jo else slip.wip
    
    table_data = []
    
    # Use WithdrawalSlipItem as the source of truth
    for item in slip.items.all().order_by('id'):
        table_data.append({
            'wip': slip.wip,
            'product_name': item.product_name,
            'item_name': item.item_name,
            'unit': item.inventory_item.sub_unit if item.inventory_item else '',
            'qty_requested': f"{item.quantity:.2f}",
            'qty_approved': f"{item.quantity_approved:.2f}",
            'released_by': item.released_by,
            'datetime_updated': item.datetime_updated.strftime('%Y-%m-%d %H:%M') if item.datetime_updated else ''
        })
    
    context = {
        'slip': slip,
        'client_name': client_name,
        'transaction_date': transaction_date,
        'wip': wip,
        'table_data': table_data,
        'active_page': 'withdrawal_slips'
    }
    return render(request, 'withdrawal/withdrawal_slip_print.html', context)

@login_required
def print_job_order(request, jo_id):
    jo = get_object_or_404(JobOrder, id=jo_id)
    products = jo.products.all()
    
    # Process products and their materials for the table
    table_data = []
    for p in products:
        table_data.append({
            'product_name': p.product_name,
            'quantity': p.quantity,
            'unit_price': p.unit_price,
            'total': p.quantity * p.unit_price,
        })
    
    payments = jo.payments.all()
    
    context = {
        'jo': jo,
        'products': table_data,
        'payments': payments,
        'transaction_date': jo.transaction_date,
        'due_date': jo.due_date,
        'client': jo.client,
    }
    
    return render(request, 'job_orders/job_order_print.html', context)

@login_required
@require_POST
def api_add_payment(request, jo_id):
    try:
        jo = get_object_or_404(JobOrder, pk=jo_id)
        
        payment_date = request.POST.get('payment_date')
        payment_type = request.POST.get('payment_type')
        amount_str = request.POST.get('amount')
        or_number = request.POST.get('or_number', '')
        
        if not all([payment_date, payment_type, amount_str]):
            return JsonResponse({'success': False, 'message': 'Date, Payment Type, and Amount are required.'})
            
        amount = float(amount_str)
        
        # Create the payment record
        payment = Payment.objects.create(
            date=payment_date,
            client=jo.client,
            payment_type=payment_type,
            or_number=or_number,
            job_order=jo,
            amount=amount,
            received_by=request.user.username if request.user.is_authenticated else 'System'
        )
        
        # Create Activity Log
        ActivityLog.objects.create(
            action='created',
            description=f"New Payment Added:\n• Amount: ₱{amount:,.2f}\n• JO: {jo.wip}\n• Client: {jo.client.full_name}",
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='Payment',
            entity_id=payment.id
        )
        
        # Update JobOrder totals via automated save() logic
        jo.amount_paid += amount
        jo.update_totals() 
        
        return JsonResponse({'success': True})
        
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid amount value.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@require_POST
def api_void_job_order(request, jo_id):
    try:
        jo = get_object_or_404(JobOrder, pk=jo_id)
        jo.status = 'Void'
        jo.save()
        
        # Update products status and log each
        for product in jo.products.all():
            product.status = 'Void'
            product.save()
            ActivityLog.objects.create(
                action='updated',
                description=f"Product Void:\n• Product: {product.product_name}\n• JO: {jo.wip}",
                user=request.user.username if request.user.is_authenticated else 'System',
                entity_type='JobOrderProduct',
                entity_id=product.id
            )
        
        desc = "Job Order Voided:\n"
        desc += f"• WIP: {jo.wip}\n"
        desc += f"• Status: VOIDED"
        
        ActivityLog.objects.create(
            action='updated',
            description=desc,
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='JobOrder',
            entity_id=jo.id
        )
        
        # Also void any associated Withdrawal Slips
        slips = WithdrawalSlip.objects.filter(wip=jo.wip)
        for slip in slips:
            if slip.status != 'Void':
                slip.status = 'Void'
                slip.save()
                ActivityLog.objects.create(
                    action='status_change',
                    description=f"Withdrawal Slip Voided (auto-synced with Job Order):\n• Slip ID: WS-{slip.id:05d}\n• WIP: {jo.wip}",
                    user=request.user.username if request.user.is_authenticated else 'System',
                    entity_type='WithdrawalSlip',
                    entity_id=slip.id
                )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@require_POST
def api_update_discount(request, jo_id):
    try:
        jo = get_object_or_404(JobOrder, pk=jo_id)
        
        discount_str = request.POST.get('discount')
        if discount_str is None:
            return JsonResponse({'success': False, 'message': 'Discount amount is required.'})
            
        discount_amount = float(discount_str)
        if discount_amount < 0:
            return JsonResponse({'success': False, 'message': 'Discount cannot be negative.'})
            
        # Update balance and is_fully_paid via model save()
        jo.save()
        
        desc = "Discount Updated:\n"
        desc += f"• WIP: {jo.wip}\n"
        desc += f"• New Discount: ₱{discount_amount:,.2f}"
        
        # Log the activity
        ActivityLog.objects.create(
            action='updated',
            description=desc,
            user=request.user.username,
            entity_type='JobOrder',
            entity_id=jo.id
        )
        
        return JsonResponse({'success': True})
        
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid discount value.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def withdrawal_slips_view(request):
    wip = request.GET.get('wip', '')
    name = request.GET.get('name', '')
    status = request.GET.get('status', '')
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')
    
    slips = WithdrawalSlip.objects.all().order_by('-created_at')
    
    # 1. Apply global date filters first (using explicit ranges for better DB compatibility)
    if date_start:
        try:
            start_dt = datetime.strptime(date_start, '%Y-%m-%d')
            start_dt = timezone.make_aware(start_dt)
            slips = slips.filter(created_at__gte=start_dt)
        except Exception:
            pass
            
    if date_end:
        try:
            end_dt = datetime.strptime(date_end, '%Y-%m-%d')
            # Set to end of day (23:59:59) to include all records on that date
            end_dt = timezone.make_aware(datetime.combine(end_dt.date(), time(23, 59, 59)))
            slips = slips.filter(created_at__lte=end_dt)
        except Exception:
            pass
        
    # 2. Calculate stats based on date-filtered set
    pending = slips.filter(status='Pending').count()
    completed = slips.filter(status='Completed').count()
    void = slips.filter(status='Void').count()
    stats = {
        'total_count': pending + completed + void,
        'pending_count': pending,
        'completed_count': completed,
        'void_count': void,
    }
    
    # 3. Apply search/status filters for the table
    if wip:
        slips = slips.filter(wip__icontains=wip)
    if name:
        slips = slips.filter(name__icontains=name)
    if status is not None and status != '':
        slips = slips.filter(status=status)

    # 4. Filter logs by its own date parameters
    ws_logs_query = ActivityLog.objects.filter(entity_type='WithdrawalSlip').order_by('-timestamp')
    if log_date_start:
        try:
            start_dt_log = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            ws_logs_query = ws_logs_query.filter(timestamp__gte=start_dt_log)
        except ValueError:
            pass
    if log_date_end:
        try:
            end_dt_log = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            ws_logs_query = ws_logs_query.filter(timestamp__lte=end_dt_log)
        except ValueError:
            pass

    ws_logs = ws_logs_query[:100]
        
    context = {
        'items': slips,
        'stats': stats,
        'withdrawal_slip_logs': ws_logs,
        'date_start': date_start,
        'date_end': date_end,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end,
        'current_status': status,
        'active_page': 'withdrawal_slips'
    }
    return render(request, 'withdrawal/withdrawal_slips.html', context)

@login_required
def dr_view(request):
    po_id = request.GET.get('po_id', '')
    supplier = request.GET.get('supplier', '')
    date = request.GET.get('date', '')
    status = request.GET.get('status', '')
    tag_delivered_by = request.GET.get('tag_delivered_by', '')
    current_filter = request.GET.get('filter', 'all')
    
    # Sorting parameters
    sort = request.GET.get('sort', 'datetime_created')
    direction = request.GET.get('direction', 'desc')
    
    # Sorting map
    sort_fields = {
        'po': 'purchase_order__id',
        'supplier': 'supplier',
        'date': 'date',
        'status': 'status',
        'created': 'datetime_created',
        'delivered_by': 'tag_delivered_by'
    }
    
    order_by = sort_fields.get(sort, 'datetime_created')
    if direction == 'desc':
        order_by = '-' + order_by
    
    receipts_base = DeliveryReceipt.objects.all().order_by(order_by)
    
    # Filtering
    if po_id:
        if po_id.isdigit():
            receipts_base = receipts_base.filter(purchase_order__id=po_id)
        else:
            receipts_base = receipts_base.filter(purchase_order__id__icontains=po_id)
    if supplier:
        receipts_base = receipts_base.filter(supplier__icontains=supplier)
    if date:
        receipts_base = receipts_base.filter(date=date)
    if status:
        receipts_base = receipts_base.filter(status=status)
    if tag_delivered_by:
        receipts_base = receipts_base.filter(tag_delivered_by__icontains=tag_delivered_by)
        
    # Stats calculation
    stats = {
        'total': receipts_base.count(),
        'open': receipts_base.filter(status='Open').count(),
        'locked': receipts_base.filter(status='Locked').count(),
        'current_filter': current_filter,
        'sort': sort,
        'direction': direction
    }
    
    # Apply card filter logic (Initial load)
    receipts = receipts_base
    if current_filter == 'open':
        receipts = receipts.filter(status='Open')
    elif current_filter == 'locked':
        receipts = receipts.filter(status='Locked')
        
    suppliers = Supplier.objects.all().order_by('name')
    purchase_orders = PurchaseOrder.objects.filter(is_archived=False).order_by('-datetime_created')
        
    # Activity Logs for Delivery Receipts
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')
    
    dr_logs_query = ActivityLog.objects.filter(entity_type='DeliveryReceipt').order_by('-timestamp')
    
    if log_date_start:
        try:
            start_dt_log = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            dr_logs_query = dr_logs_query.filter(timestamp__gte=start_dt_log)
        except (ValueError, Exception):
            pass
            
    if log_date_end:
        try:
            end_dt_log = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            dr_logs_query = dr_logs_query.filter(timestamp__lte=end_dt_log)
        except (ValueError, Exception):
            pass
            
    dr_logs = dr_logs_query[:100]  # Limit to 100 for performance
        
    context = {
        'items': receipts,
        'suppliers': suppliers,
        'purchase_orders': purchase_orders,
        'stats': stats,
        'dr_logs': dr_logs,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end,
        'active_page': 'dr'
    }
    return render(request, 'job_orders/dr.html', context)

@login_required
@require_POST
def api_create_dr(request):
    try:
        po_id = request.POST.get('purchase_order_id')
        supplier = request.POST.get('supplier')
        date = request.POST.get('date') or timezone.now().date()
        comments = request.POST.get('comments', '')
        
        dr = DeliveryReceipt.objects.create(
            purchase_order_id=po_id if po_id else None,
            supplier=supplier,
            date=date,
            comments=comments,
            tag_delivered_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        # Log action
        ActivityLog.objects.create(
            action='created',
            description=f"New Delivery Receipt Created: DR-{dr.id}\n• PO: {dr.purchase_order_id if dr.purchase_order_id else 'None'}\n• Supplier: {dr.supplier}",
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='DeliveryReceipt',
            entity_id=dr.id
        )
        
        return JsonResponse({'success': True, 'dr_id': dr.id})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
def dr_detail_view(request, dr_id):
    dr = get_object_or_404(DeliveryReceipt, id=dr_id)
    items = dr.items.all().order_by('-received_at')
    inventory_items = InventoryItem.objects.filter(is_archived=False).order_by('name')
    
    context = {
        'dr': dr,
        'items': items,
        'inventory_items': inventory_items,
        'active_page': 'dr'
    }
    return render(request, 'job_orders/dr_detail.html', context)

@login_required
@require_POST
def api_add_dr_item(request, dr_id):
    try:
        dr = get_object_or_404(DeliveryReceipt, id=dr_id)
        if dr.status == 'Locked':
            return JsonResponse({'success': False, 'message': 'Cannot add items to a locked receipt'}, status=400)
            
        item_id = request.POST.get('inventory_item_id')
        quantity = float(request.POST.get('quantity', 0))
        
        inventory_item = get_object_or_404(InventoryItem, id=item_id)
        
        DeliveryReceiptItem.objects.create(
            delivery_receipt=dr,
            inventory_item=inventory_item,
            quantity=quantity,
            unit=inventory_item.sub_unit or 'pc'
        )
        
        # Update inventory balance
        inventory_item.total_purchases += quantity
        inventory_item.total_balance += quantity
        inventory_item.save()
        
        # Create log entry
        InventoryLog.objects.create(
            inventory_item=inventory_item,
            transaction_type='purchase',
            quantity=str(quantity),
            notes=f"Added via DR-{dr.id}"
        )
        
        # Activity Log entry
        ActivityLog.objects.create(
            action='updated',
            description=f"Item Added to Delivery Receipt (DR-{dr.id}):\n• Item: {inventory_item.name}\n• Quantity: {quantity} {inventory_item.sub_unit or 'pc'}",
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='DeliveryReceipt',
            entity_id=dr.id
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
@require_POST
def api_lock_dr(request, dr_id):
    try:
        dr = get_object_or_404(DeliveryReceipt, id=dr_id)
        dr.status = 'Locked'
        dr.save()
        
        # Activity Log entry
        ActivityLog.objects.create(
            action='status_change',
            description=f"Delivery Receipt Locked: DR-{dr.id}\n• Status: Locked",
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='DeliveryReceipt',
            entity_id=dr.id
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
@require_POST
def api_delete_dr_item(request, item_id):
    try:
        item = get_object_or_404(DeliveryReceiptItem, id=item_id)
        dr = item.delivery_receipt
        if dr.status == 'Locked':
            return JsonResponse({'success': False, 'message': 'Cannot delete items from a locked receipt'}, status=400)
            
        inventory_item = item.inventory_item
        quantity = item.quantity
        
        # Reverse inventory balance
        inventory_item.total_purchases -= quantity
        inventory_item.total_balance -= quantity
        inventory_item.save()
        
        # Create reversal log entry
        InventoryLog.objects.create(
            inventory_item=inventory_item,
            transaction_type='adjustment',
            quantity=f"-{quantity}",
            notes=f"Deleted from DR-{dr.id} (Reversal)"
        )
        
        item.delete()
        
        # Activity Log entry
        ActivityLog.objects.create(
            action='deleted',
            description=f"Item Removed from Delivery Receipt (DR-{dr.id}):\n• Item: {inventory_item.name}\n• Quantity: {quantity} {inventory_item.sub_unit or 'pc'} (Reversed)",
            user=request.user.username if request.user.is_authenticated else 'System',
            entity_type='DeliveryReceipt',
            entity_id=dr.id
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
def expenses_view(request):
    dv_number = request.GET.get('dv_number', '')
    category_id = request.GET.get('category_id', '')
    supplier_id = request.GET.get('supplier_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')
    
    expenses = Expense.objects.all().order_by('-date', '-created_at')
    
    if dv_number:
        expenses = expenses.filter(dv_number__icontains=dv_number)
    if category_id:
        expenses = expenses.filter(expense_type__category_id=category_id)
    if supplier_id:
        expenses = expenses.filter(supplier_id=supplier_id)
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
        
    categories = ExpenseCategory.objects.all()
    types = ExpenseType.objects.all().select_related('category')
    suppliers = Supplier.objects.all().order_by('name')
    
    # Calculate totals
    total_amount = sum(e.amount for e in expenses)

    # Fetch Activity Logs for Expenses
    expense_logs_query = ActivityLog.objects.filter(entity_type='Expense').order_by('-timestamp')
    if log_date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            expense_logs_query = expense_logs_query.filter(timestamp__gte=start_dt)
        except ValueError: pass
    if log_date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            expense_logs_query = expense_logs_query.filter(timestamp__lte=end_dt)
        except ValueError: pass
        
    expense_logs = expense_logs_query[:100]
    
    if request.method == 'POST':
        date = request.POST.get('date')
        dv_number = request.POST.get('dv_number')
        type_id = request.POST.get('type_id')
        fund_source = request.POST.get('fund_source', 'Cash')
        try:
            amount = float(request.POST.get('amount', 0).replace(',', ''))
        except (ValueError, TypeError):
            amount = 0.0
        receipt_number = request.POST.get('receipt_number')
        supplier_id = request.POST.get('supplier_id')
        classification = request.POST.get('classification')
        particular = request.POST.get('particular')
        
        expense = Expense.objects.create(
            date=date or timezone.now().date(),
            dv_number=dv_number,
            expense_type_id=type_id if type_id else None,
            fund_source=fund_source,
            mode=fund_source, # Sync mode with fund_source
            amount=amount,
            receipt_number=receipt_number,
            supplier_id=supplier_id if supplier_id else None,
            classification=classification,
            particular=particular,
            created_by=request.user.username
        )
        
        # Create Activity Log
        ActivityLog.objects.create(
            action='created',
            description=f"New Expense Added:\n• Amount: ₱{expense.amount:,.2f}\n• Category: {expense.expense_type.name if expense.expense_type else 'Unclassified'}\n• Particular: {expense.particular}",
            user=request.user.username,
            entity_type='Expense',
            entity_id=expense.id
        )
        
        messages.success(request, f"Expense {expense.dv_number} created successfully.")
        return redirect('expenses')
        
    context = {
        'items': expenses,
        'categories': categories,
        'types': types,
        'suppliers': suppliers,
        'total_amount': total_amount,
        'date_from': date_from,
        'date_to': date_to,
        'activity_logs': expense_logs,
        'now': timezone.now(),
        'active_page': 'expenses'
    }
    return render(request, 'expenses/expenses.html', context)

@login_required
@require_POST
def api_update_expense(request, expense_id):
    try:
        expense = get_object_or_404(Expense, id=expense_id)
        
        # Store old values for logging
        old_amount = expense.amount
        old_date = expense.date.strftime('%Y-%m-%d') if hasattr(expense.date, 'strftime') else str(expense.date)
        old_type_name = expense.expense_type.name if expense.expense_type else 'Unclassified'
        old_fund_source = expense.fund_source
        old_dv_number = expense.dv_number
        old_receipt_number = expense.receipt_number
        old_supplier_name = expense.supplier.name if expense.supplier else 'N/A'
        old_classification = expense.classification
        old_particular = expense.particular

        # Get new values from request
        new_date_str = request.POST.get('date')
        new_dv_number = request.POST.get('dv_number', '')
        new_type_id = request.POST.get('type_id')
        new_fund_source = request.POST.get('fund_source', 'Cash')
        new_amount_str = request.POST.get('amount', '0')
        new_receipt_number = request.POST.get('receipt_number', '')
        new_supplier_id = request.POST.get('supplier_id')
        new_classification = request.POST.get('classification', '')
        new_particular = request.POST.get('particular', '')

        # Convert new amount to float
        new_amount = float(new_amount_str)

        # Update expense object
        expense.date = new_date_str or expense.date
        expense.dv_number = new_dv_number
        expense.expense_type_id = new_type_id if new_type_id else None
        expense.fund_source = new_fund_source
        expense.mode = new_fund_source # Sync mode with fund_source
        expense.amount = new_amount
        expense.receipt_number = new_receipt_number
        expense.supplier_id = new_supplier_id if new_supplier_id else None
        expense.classification = new_classification
        expense.particular = new_particular
        expense.save()
        
        # Get updated related object names for logging
        new_type_name = expense.expense_type.name if expense.expense_type else 'Unclassified'
        new_supplier_name = expense.supplier.name if expense.supplier else 'N/A'
        new_date = expense.date.strftime('%Y-%m-%d') if hasattr(expense.date, 'strftime') else str(expense.date)

        # Prepare log description
        changes = []
        if old_dv_number != new_dv_number:
            changes.append(f"DV Number: {old_dv_number} → {new_dv_number}")
        if old_amount != new_amount:
            changes.append(f"Amount: ₱{old_amount:,.2f} → ₱{new_amount:,.2f}")
        if old_date != new_date:
            changes.append(f"Date: {old_date} → {new_date}")
        if old_type_name != new_type_name:
            changes.append(f"Category: {old_type_name} → {new_type_name}")
        if old_fund_source != new_fund_source:
             changes.append(f"Fund Source: {old_fund_source} → {new_fund_source}")
        if old_receipt_number != new_receipt_number:
            changes.append(f"Receipt Number: {old_receipt_number} → {new_receipt_number}")
        if old_supplier_name != new_supplier_name:
            changes.append(f"Supplier: {old_supplier_name} → {new_supplier_name}")
        if old_classification != new_classification:
            changes.append(f"Classification: {old_classification} → {new_classification}")
        if old_particular != new_particular:
            changes.append(f"Particular: {old_particular} → {new_particular}")
             
        desc = f"Expense (DV-{expense.dv_number}) Updated:\n" + ("\n".join([f"• {c}" for c in changes]) if changes else "• No significant field changes.")
        
        # Create Activity Log
        ActivityLog.objects.create(
            action='updated',
            description=desc,
            user=request.user.username,
            entity_type='Expense',
            entity_id=expense.id
        )
        
        messages.success(request, f"Expense {expense.dv_number} updated successfully.")
        return redirect('expenses')
    except Exception as e:
        messages.error(request, f"Error updating expense: {str(e)}")
        return redirect('expenses')

@login_required
@require_POST
def api_delete_expense(request, expense_id):
    try:
        expense = get_object_or_404(Expense, id=expense_id)
        dv = expense.dv_number
        
        # Create Activity Log before deletion
        ActivityLog.objects.create(
            action='deleted',
            description=f"Expense [{dv}] Deleted:\n• Amount: ₱{expense.amount:,.2f}\n• Category: {expense.expense_type.name if expense.expense_type else 'Unclassified'}\n• Particular: {expense.particular}",
            user=request.user.username,
            entity_type='Expense',
            entity_id=expense_id
        )
        
        expense.delete()
        messages.success(request, f"Expense {dv} deleted successfully.")
        return redirect('expenses')
    except Exception as e:
        messages.error(request, f"Error deleting expense: {str(e)}")
        return redirect('expenses')

@login_required
def expenses_summary_view(request):
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    
    summaries = ExpenseSummary.objects.all().order_by('-date')
    
    if date_start:
        try:
            start_dt = datetime.strptime(date_start, '%Y-%m-%d').date()
            summaries = summaries.filter(date__gte=start_dt)
        except ValueError:
            pass
    if date_end:
        try:
            end_dt = datetime.strptime(date_end, '%Y-%m-%d').date()
            summaries = summaries.filter(date__lte=end_dt)
        except ValueError:
            pass

    if request.method == 'POST':
        date_str = request.POST.get('date')
        try:
            cash_from_chin_yu = float(str(request.POST.get('cash_from_chin_yu', 0)).replace(',', ''))
            transaction_by_chin_yu = float(str(request.POST.get('transaction_by_chin_yu', 0)).replace(',', ''))
            cash_reimbursement = float(str(request.POST.get('cash_reimbursement', 0)).replace(',', ''))
            others = float(str(request.POST.get('others', 0)).replace(',', ''))
        except (ValueError, TypeError):
            cash_from_chin_yu = 0.0
            transaction_by_chin_yu = 0.0
            cash_reimbursement = 0.0
            others = 0.0

        summary = ExpenseSummary.objects.create(
            date=date_str or timezone.now().date(),
            cash_from_chin_yu=cash_from_chin_yu,
            transaction_by_chin_yu=transaction_by_chin_yu,
            cash_reimbursement=cash_reimbursement,
            others=others,
            updated_by=request.user.username
        )

        # Create Activity Log
        ActivityLog.objects.create(
            action='created',
            description=f"Created Expenses Summary for {summary.date}:\n• Cash from Chin Yu: ₱{summary.cash_from_chin_yu:,.2f}\n• Transaction by Chin Yu: ₱{summary.transaction_by_chin_yu:,.2f}\n• Cash Reimbursement: ₱{summary.cash_reimbursement:,.2f}\n• Others: ₱{summary.others:,.2f}",
            user=request.user.username,
            entity_type='ExpenseSummary',
            entity_id=summary.id
        )

        messages.success(request, f"Daily summary for {summary.date} created successfully.")
        return redirect('expenses_summary')
        
    # Calculate totals for stat cards
    from django.db.models import Sum
    totals = summaries.aggregate(
        total_chin_yu=Sum('cash_from_chin_yu'),
        total_reimbursement=Sum('cash_reimbursement'),
        total_others=Sum('others')
    )
    
    total_chin_yu = totals['total_chin_yu'] or 0
    total_reimbursement = totals['total_reimbursement'] or 0
    total_others = totals['total_others'] or 0

    # Activity Logs
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')
    
    activity_logs_query = ActivityLog.objects.filter(entity_type='ExpenseSummary').order_by('-timestamp')
    if log_date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            activity_logs_query = activity_logs_query.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    if log_date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            activity_logs_query = activity_logs_query.filter(timestamp__lte=end_dt)
        except ValueError:
            pass
            
    activity_logs = activity_logs_query[:100]

    context = {
        'items': summaries,
        'total_chin_yu': total_chin_yu,
        'total_reimbursement': total_reimbursement,
        'total_others': total_others,
        'date_start': date_start,
        'date_end': date_end,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end,
        'activity_logs': activity_logs,
        'active_page': 'expenses_summary'
    }
    return render(request, 'expenses/expenses_summary.html', context)

@login_required
@require_POST
def api_update_expense_summary(request, summary_id):
    summary = get_object_or_404(ExpenseSummary, id=summary_id)
    
    # Store old values for logging
    old_date = str(summary.date)
    old_vals = {
        'cash_from_chin_yu': summary.cash_from_chin_yu,
        'transaction_by_chin_yu': summary.transaction_by_chin_yu,
        'cash_reimbursement': summary.cash_reimbursement,
        'others': summary.others
    }

    try:
        new_date = request.POST.get('date')
        new_cash = float(str(request.POST.get('cash_from_chin_yu', 0)).replace(',', ''))
        new_trans = float(str(request.POST.get('transaction_by_chin_yu', 0)).replace(',', ''))
        new_reimb = float(str(request.POST.get('cash_reimbursement', 0)).replace(',', ''))
        new_others = float(str(request.POST.get('others', 0)).replace(',', ''))

        summary.date = new_date or summary.date
        summary.cash_from_chin_yu = new_cash
        summary.transaction_by_chin_yu = new_trans
        summary.cash_reimbursement = new_reimb
        summary.others = new_others
        summary.updated_by = request.user.username
        summary.save()

        # Log changes
        changes = []
        if old_date != str(summary.date): changes.append(f"Date: {old_date} → {summary.date}")
        if old_vals['cash_from_chin_yu'] != summary.cash_from_chin_yu: 
            changes.append(f"Cash Chin Yu: ₱{old_vals['cash_from_chin_yu']:,.2f} → ₱{summary.cash_from_chin_yu:,.2f}")
        if old_vals['transaction_by_chin_yu'] != summary.transaction_by_chin_yu:
            changes.append(f"Trans Chin Yu: ₱{old_vals['transaction_by_chin_yu']:,.2f} → ₱{summary.transaction_by_chin_yu:,.2f}")
        if old_vals['cash_reimbursement'] != summary.cash_reimbursement:
            changes.append(f"Reimbursement: ₱{old_vals['cash_reimbursement']:,.2f} → ₱{summary.cash_reimbursement:,.2f}")
        if old_vals['others'] != summary.others:
            changes.append(f"Others: ₱{old_vals['others']:,.2f} → ₱{summary.others:,.2f}")

        if changes:
            ActivityLog.objects.create(
                action='updated',
                description=f"Updated Expenses Summary for {summary.date}:\n" + "\n".join([f"• {c}" for c in changes]),
                user=request.user.username,
                entity_type='ExpenseSummary',
                entity_id=summary.id
            )

        messages.success(request, f"Summary for {summary.date} updated successfully.")
    except Exception as e:
        messages.error(request, f"Error updating summary: {str(e)}")

    return redirect('expenses_summary')

@login_required
@require_POST
def api_delete_expense_summary(request, summary_id):
    summary = get_object_or_404(ExpenseSummary, id=summary_id)
    date_str = str(summary.date)
    
    ActivityLog.objects.create(
        action='deleted',
        description=f"Deleted Expenses Summary for {date_str}",
        user=request.user.username,
        entity_type='ExpenseSummary',
        entity_id=summary.id
    )
    
    summary.delete()
    messages.success(request, f"Summary for {date_str} deleted successfully.")
    return redirect('expenses_summary')

@login_required
def expenses_category_view(request):
    categories = ExpenseCategory.objects.all().order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            ExpenseCategory.objects.create(name=name)
            messages.success(request, f"Category '{name}' created.")
        return redirect('expenses_category')
        
    context = {
        'items': categories,
        'active_page': 'expenses_category'
    }
    return render(request, 'expenses/expenses_category.html', context)

@login_required
@require_POST
def api_update_expense_category(request, category_id):
    try:
        category = get_object_or_404(ExpenseCategory, id=category_id)
        name = request.POST.get('name')
        if name:
            category.name = name
            category.save()
            messages.success(request, f"Category '{name}' updated successfully.")
        else:
            messages.error(request, "Name is required.")
    except Exception as e:
        messages.error(request, f"Error updating category: {str(e)}")
    return redirect('expenses_category')

@login_required
@require_POST
def api_delete_expense_category(request, category_id):
    try:
        category = get_object_or_404(ExpenseCategory, id=category_id)
        name = category.name
        # Check if there are types under this category
        if category.types.exists():
            messages.error(request, f"Cannot delete category '{name}' because it contains expense types. Delete the types first.")
        else:
            category.delete()
            messages.success(request, f"Category '{name}' deleted successfully.")
    except Exception as e:
        messages.error(request, f"Error deleting category: {str(e)}")
    return redirect('expenses_category')

@login_required
def expenses_types_view(request):
    types = ExpenseType.objects.all().order_by('category__name', 'name')
    categories = ExpenseCategory.objects.all().order_by('name')
    
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        name = request.POST.get('name')
        if category_id and name:
            ExpenseType.objects.create(category_id=category_id, name=name)
            messages.success(request, f"Type '{name}' created.")
        return redirect('expenses_types')
        
    context = {
        'items': types,
        'categories': categories,
        'active_page': 'expenses_types'
    }
    return render(request, 'expenses/expenses_types.html', context)
    
@login_required
@require_POST
def api_update_expense_type(request, type_id):
    try:
        expense_type = get_object_or_404(ExpenseType, id=type_id)
        category_id = request.POST.get('category_id')
        name = request.POST.get('name')
        
        if category_id and name:
            expense_type.category_id = category_id
            expense_type.name = name
            expense_type.save()
            messages.success(request, f"Expense type '{name}' updated successfully.")
        else:
            messages.error(request, "Category and Name are required.")
    except Exception as e:
        messages.error(request, f"Error updating expense type: {str(e)}")
        
    return redirect('expenses_types')

@login_required
@require_POST
def api_delete_expense_type(request, type_id):
    try:
        expense_type = get_object_or_404(ExpenseType, id=type_id)
        name = expense_type.name
        expense_type.delete()
        messages.success(request, f"Expense type '{name}' deleted successfully.")
    except Exception as e:
        messages.error(request, f"Error deleting expense type: {str(e)}")
        
    return redirect('expenses_types')

@login_required
def suppliers_view(request):
    suppliers = Supplier.objects.all().order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        contact = request.POST.get('contact_number')
        email = request.POST.get('email')
        facebook = request.POST.get('facebook')
        address = request.POST.get('address')
        description = request.POST.get('description')
        tin = request.POST.get('tin')
        
        if name:
            Supplier.objects.create(
                name=name,
                contact_number=contact,
                email=email,
                facebook=facebook,
                address=address,
                description=description,
                tin=tin
            )
            messages.success(request, f"Supplier '{name}' created.")
        return redirect('suppliers')
        
    context = {
        'items': suppliers,
        'active_page': 'suppliers'
    }
    return render(request, 'purchase_orders/suppliers.html', context)

@login_required
@require_POST
def api_update_supplier(request, supplier_id):
    try:
        supplier = get_object_or_404(Supplier, id=supplier_id)
        supplier.name = request.POST.get('name')
        supplier.contact_number = request.POST.get('contact_number', '')
        supplier.email = request.POST.get('email', '')
        supplier.facebook = request.POST.get('facebook', '')
        supplier.address = request.POST.get('address', '')
        supplier.description = request.POST.get('description', '')
        supplier.tin = request.POST.get('tin', '')
        
        if supplier.name:
            supplier.save()
            messages.success(request, f"Supplier '{supplier.name}' updated successfully.")
        else:
            messages.error(request, "Supplier Name is required.")
    except Exception as e:
        messages.error(request, f"Error updating supplier: {str(e)}")
        
    return redirect('suppliers')

@login_required
@require_POST
def api_delete_supplier(request, supplier_id):
    try:
        supplier = get_object_or_404(Supplier, id=supplier_id)
        name = supplier.name
        supplier.delete()
        messages.success(request, f"Supplier '{name}' deleted successfully.")
    except Exception as e:
        messages.error(request, f"Error deleting supplier: {str(e)}")
        
    return redirect('suppliers')

@csrf_exempt
@login_required
def update_purchase_order_request(request, pr_id):
    if request.method == 'POST':
        pr = get_object_or_404(PurchaseOrderRequest, id=pr_id)
        pr.request_type = request.POST.get('request_type', pr.request_type)
        
        product_id = request.POST.get('product_id')
        if product_id and product_id != 'custom':
            try:
                item = InventoryItem.objects.get(id=product_id)
                pr.name = item.name
            except InventoryItem.DoesNotExist:
                pass

        pr.quantity = float(request.POST.get('quantity') or pr.quantity)
        pr.unit = request.POST.get('unit', pr.unit)
        pr.remarks = request.POST.get('remarks', pr.remarks)
        pr.save()
        
        PurchaseOrderRequestLog.objects.create(
            purchase_order_request=pr,
            action='update',
            item_name=pr.name,
            details=f"Updated request for {pr.name}",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        messages.success(request, f'Request for "{pr.name}" updated.')
        return redirect('/purchase-request/index')
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def delete_purchase_order_request(request, pr_id):
    if request.method == 'POST':
        pr = get_object_or_404(PurchaseOrderRequest, id=pr_id)
        name = pr.name
        
        # Log before deletion if cascade is not desired, but here we just log it
        # Actually we probably want a soft delete or just log the action
        # For now, let's just delete
        pr.delete()
        
        messages.success(request, f'Request for "{name}" deleted.')
        return redirect('/purchase-request/index')
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def cancel_purchase_order_request(request, pr_id):
    if request.method == 'POST':
        pr = get_object_or_404(PurchaseOrderRequest, id=pr_id)
        pr.status = 'cancelled'
        pr.save()
        
        PurchaseOrderRequestLog.objects.create(
            purchase_order_request=pr,
            action='cancel',
            item_name=pr.name,
            details=f"Cancelled request for {pr.name}",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        messages.warning(request, f'Request for "{pr.name}" has been cancelled.')
        return redirect('/purchase-request/index')
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def add_requests_to_po(request):
    if request.method == 'POST':
        # Determine if it's a JSON request or a form submission
        is_json = request.content_type == 'application/json'
        
        if is_json:
            try:
                data = json.loads(request.body)
                pr_ids = data.get('pr_ids', [])
                po_id = data.get('purchase_order_id')
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
        else:
            pr_ids = request.POST.getlist('pr_ids')
            # Handle comma-separated string from a hidden field
            if not pr_ids and request.POST.get('pr_ids_string'):
                pr_ids = [pid.strip() for pid in request.POST.get('pr_ids_string').split(',') if pid.strip()]
            po_id = request.POST.get('purchase_order_id')
        
        if not po_id:
            if is_json:
                return JsonResponse({'success': False, 'message': 'PO ID is required'}, status=400)
            messages.error(request, 'Please select a Purchase Order.')
            return redirect('/purchase-request/index')

        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        count = 0
        for pr_id in pr_ids:
            if not pr_id: continue
            try:
                pr = PurchaseOrderRequest.objects.get(id=pr_id)
                # Create PO item from request
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product_name=pr.name,
                    quantity=pr.quantity,
                    unit=pr.unit,
                    description=pr.description,
                    remarks=pr.remarks
                )
                # Update PR status
                pr.status = 'ordered'
                pr.purchase_order_id = po.po_number
                pr.datetime_added = timezone.now()
                pr.added_by = request.user.username if request.user.is_authenticated else 'Stephen'
                pr.save()
                
                # Log PR action
                PurchaseOrderRequestLog.objects.create(
                    purchase_order_request=pr,
                    action='add_to_po',
                    item_name=pr.name,
                    details=f"Added to PO {po.po_number}",
                    user=request.user.username if request.user.is_authenticated else 'Stephen'
                )
                count += 1
            except PurchaseOrderRequest.DoesNotExist:
                continue
            
        # Log PO action
        PurchaseOrderLog.objects.create(
            purchase_order=po,
            action='update',
            po_number=po.po_number,
            details=f"Added {count} items from requests",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        success_msg = f'Successfully added {count} items to PO {po.po_number}.'
        if is_json:
            return JsonResponse({'success': True, 'message': success_msg})
        
        messages.success(request, success_msg)
        return redirect('/purchase-request/index')
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

def get_po_items_api(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)
    items = po.items.all()
    items_data = []
    total = 0
    for item in items:
        item_total = item.quantity * (item.unit_price or 0)
        total += item_total
        items_data.append({
            'product_name': item.product_name,
            'description': item.description,
            'quantity': item.quantity,
            'unit': item.unit,
            'unit_price': item.unit_price or 0,
            'total': item_total
        })
    return JsonResponse({
        'success': True,
        'items': items_data,
        'total': total
    })

@login_required
def create_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        product_type = request.POST.get('product_type')
        description = request.POST.get('description', '')
        quantity = float(request.POST.get('quantity') or 0)
        unit = request.POST.get('unit', 'pc')
        markup = float(request.POST.get('markup') or 0)
        overhead = float(request.POST.get('overhead') or 0)
        
        # Handle Image
        image_data = ''
        if 'image' in request.FILES:
            image_data = handle_uploaded_image(request.FILES['image'])
        
        product = Product.objects.create(
            name=name,
            product_type=product_type,
            description=description,
            quantity=quantity,
            unit=unit,
            markup=markup,
            overhead=overhead,
            image=image_data,
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.success(request, f'Product "{product.name}" created successfully.')
            return JsonResponse({'success': True, 'message': 'Product created successfully'})
            
        messages.success(request, 'Product created successfully')
        return redirect('products')
        
    return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

def get_product_detail_context(product):
    materials = product.materials.all()
    
    # Categories for the template matching InventoryItem.item_type
    categories = [
        "RAW Materials", "Indirect Materials", "Print Materials", 
        "Special Boards/Papers", "Printing Process", "Garments", 
        "Office Supplies", "Labor Cost"
    ]
    
    materials_by_category = {}
    for cat in categories:
        cat_materials = list(materials.filter(category=cat))
        # For each material, check if sufficient stock
        for m in cat_materials:
            m.is_sufficient = (m.inventory_item.total_balance >= m.quantity) if m.inventory_item else True
        materials_by_category[cat] = cat_materials
        
    # Stats calculation
    total_materials = sum([m.total_cost for m in materials if m.category != 'Labor Cost'])
    total_labor = sum([m.total_cost for m in materials if m.category == 'Labor Cost'])
    total_materials_labor_overhead = total_materials + total_labor + product.overhead
    total_product_cost = total_materials_labor_overhead + product.markup
    total_pc_tax = float(total_product_cost) * 1.12
    
    # Update product SRP/MP/LP based on some business logic or just show them
    # For now we just use the calculated values
    product.srp = total_pc_tax
    product.mp = total_pc_tax * 0.9 # Example MP
    product.lp = total_pc_tax * 0.8 # Example LP
    product.save()

    return {
        'product': product,
        'total_materials': total_materials,
        'total_labor': total_labor,
        'total_product_cost': total_product_cost,
        'total_ml_overhead': total_materials_labor_overhead,
        'total_pc_tax': total_pc_tax,
        'material_categories': categories,
        'materials_by_category': materials_by_category,
    }

@login_required
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    context = get_product_detail_context(product)
    
    # Get all inventory items grouped by type for selection
    inventory_items = InventoryItem.objects.filter(is_archived=False)
    inventory_by_type = {}
    for item in inventory_items:
        it = item.item_type
        if it not in inventory_by_type:
            inventory_by_type[it] = []
        inventory_by_type[it].append({
            'id': item.id,
            'name': item.name,
            'cost': float(item.cost or 0),
            'balance': float(item.total_balance or 0)
        })

    context.update({
        'product_id': product_id,
        'active_page': 'products',
        'inventory_by_type': json.dumps(inventory_by_type)
    })

    return render(request, 'inventory/product_detail.html', context)

@login_required
def api_get_product_details(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    context = get_product_detail_context(product)
    return render(request, 'inventory/product_detail_partial.html', context)

@csrf_exempt
@login_required
def update_product_image(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        image = request.FILES.get('image')
        if image:
            product.image = handle_uploaded_image(image)
            product.save()
            return JsonResponse({'success': True, 'message': 'Image updated', 'image': product.image})
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@csrf_exempt
@login_required
def delete_product_image(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        product.image = ''
        product.save()
        return JsonResponse({'success': True, 'message': 'Image deleted', 'image': ''})
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@csrf_exempt
@login_required
def add_product_material(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        category = request.POST.get('category')
        inventory_item_id = request.POST.get('inventory_item_id')
        item_name = request.POST.get('item_name')
        quantity = float(request.POST.get('quantity') or 0)
        cost = float(request.POST.get('cost') or 0)
        
        if inventory_item_id:
            inventory_item = get_object_or_404(InventoryItem, id=inventory_item_id)
            material, created = ProductMaterial.objects.get_or_create(
                product=product,
                inventory_item=inventory_item,
                category=category,
                defaults={'item_name': inventory_item.name}
            )
            material.item_name = inventory_item.name
            material.quantity = quantity
            material.cost = inventory_item.cost
            material.total_cost = quantity * inventory_item.cost
            material.save()
            return JsonResponse({'success': True, 'message': 'Material added/updated'})
        elif category == 'Labor Cost' and item_name:
            # Handle Labor Cost without inventory item
            material, created = ProductMaterial.objects.get_or_create(
                product=product,
                item_name=item_name,
                category=category
            )
            material.quantity = quantity
            material.cost = cost
            material.total_cost = quantity * cost
            material.save()
            return JsonResponse({'success': True, 'message': 'Labor cost added/updated'})
            
    return JsonResponse({'success': False, 'message': 'Invalid request or missing data'}, status=400)
@login_required
def create_combo_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        product_type = request.POST.get('product_type', 'Combo')
        description = request.POST.get('description', '')
        quantity = float(request.POST.get('quantity') or 1.0)
        unit = request.POST.get('unit', 'set')
        markup = float(request.POST.get('markup') or 0.0)
        overhead = float(request.POST.get('overhead') or 0.0)
        
        # Selected products from the multiple select field
        selected_product_ids = request.POST.getlist('selected_products')
        
        # Handle Image
        image_data = ''
        if 'image' in request.FILES:
            image_data = handle_uploaded_image(request.FILES['image'])
        
        # Create the Combo Product
        combo_product = Product.objects.create(
            name=name,
            product_type=product_type,
            description=description,
            quantity=quantity,
            unit=unit,
            markup=markup,
            overhead=overhead,
            image=image_data,
            is_combo=True,
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        # Create Combo Items for each selected product
        for p_id in selected_product_ids:
            try:
                linked_p = Product.objects.get(id=p_id)
                ProductComboItem.objects.create(
                    product=combo_product,
                    linked_product=linked_p,
                    item_name=linked_p.name,
                    quantity=1.0 # Default quantity, can be adjusted if UI is expanded
                )
            except Product.DoesNotExist:
                continue
                
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.success(request, f'Combo Product "{combo_product.name}" created successfully.')
            return JsonResponse({'success': True, 'message': 'Combo Product created successfully'})
            
        messages.success(request, f'Combo Product "{combo_product.name}" created successfully.')
        return redirect('products')
        
    return redirect('products')

@login_required
def toggle_product_archive(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.is_archived = not product.is_archived
    product.save()
    status = "archived" if product.is_archived else "restored"
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': f'Product {status} successfully'})
        
    messages.success(request, f'Product {status} successfully')
    return redirect('products')

@csrf_exempt
@login_required
def update_product(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        product.name = request.POST.get('name', product.name)
        product.product_type = request.POST.get('product_type', product.product_type)
        product.description = request.POST.get('description', product.description)
        product.quantity = float(request.POST.get('quantity') or product.quantity)
        product.unit = request.POST.get('unit', product.unit)
        product.markup = float(request.POST.get('markup') or product.markup)
        product.overhead = float(request.POST.get('overhead') or product.overhead)
        product.save()
        return JsonResponse({'success': True, 'message': 'Product updated successfully'})
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@login_required
def duplicate_product(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        # Simple duplicate
        new_product = Product.objects.create(
            name=f"{product.name} (Copy)",
            product_type=product.product_type,
            description=product.description,
            quantity=product.quantity,
            unit=product.unit,
            markup=product.markup,
            overhead=product.overhead,
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        messages.success(request, f'Product duplicated successfully as "{new_product.name}".')
        return JsonResponse({'success': True, 'message': 'Product duplicated', 'id': new_product.id})
    return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

@csrf_exempt
@login_required
def add_item_to_po(request, po_id):
    if request.method == 'POST':
        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        # Get data from frontend (aligned with purchase_order_detail.html form names)
        product_id_raw = request.POST.get('product_id')
        quantity = float(request.POST.get('quantity') or 1)
        unit_price = float(request.POST.get('unit_price') or 0)
        
        inventory_item = None
        product_name = ""
        description = ""
        remarks = ""
        unit = "pc"
        
        if product_id_raw == 'custom':
            product_name = request.POST.get('custom_name', '')
            description = request.POST.get('custom_description', '')
            remarks = request.POST.get('custom_remarks', '')
            unit = request.POST.get('custom_unit', 'pc')
        elif product_id_raw:
            try:
                inventory_item = InventoryItem.objects.get(id=product_id_raw)
                product_name = inventory_item.name
                description = inventory_item.description
                unit = inventory_item.sub_unit or 'pc'
                remarks = "Auto-added"
            except (InventoryItem.DoesNotExist, ValueError):
                pass
        
        # Extended Validation: Ensure we actually have a product name
        if not product_name or product_name.strip() == "":
            return JsonResponse({
                'success': False, 
                'message': 'Product name is required. Please select a product or enter custom details.'
            })

        # Duplicate Check: Prevent adding the exact same item twice to the same PO
        if inventory_item:
            if PurchaseOrderItem.objects.filter(purchase_order=po, inventory_item=inventory_item).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'"{product_name}" is already in this Purchase Order. Please update its quantity instead.'
                })
        else:
            # Custom item check by name
            if PurchaseOrderItem.objects.filter(purchase_order=po, product_name__iexact=product_name).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'"{product_name}" is already in this Purchase Order. Please update its quantity instead.'
                })
            
        item_total = quantity * unit_price
        
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            inventory_item=inventory_item,
            product_name=product_name,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            total=item_total,
            remarks=remarks,
            description=description
        )
        
        # Update PO total
        po.total += item_total
        po.save()
        
        PurchaseOrderLog.objects.create(
            purchase_order=po,
            action='update',
            po_number=po.po_number,
            details=f"Added item {product_name} (Qty: {quantity})",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        messages.success(request, f'Item "{product_name}" added to PO.')
        return JsonResponse({'success': True, 'message': 'Item added'})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def delete_po(request, po_id):
    if request.method == 'POST':
        po = get_object_or_404(PurchaseOrder, id=po_id)
        po_number = po.po_number
        po.delete()
        messages.success(request, f'Purchase Order {po_number} has been deleted.')
        return redirect('/purchase-orders/')
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)



@csrf_exempt
@login_required
def toggle_po_archive(request, po_id):
    if request.method == 'POST':
        po = get_object_or_404(PurchaseOrder, id=po_id)
        po.is_archived = not po.is_archived
        po.save()
        
        status = "archived" if po.is_archived else "restored"
        
        PurchaseOrderLog.objects.create(
            purchase_order=po,
            action='archive' if po.is_archived else 'restore',
            po_number=po.po_number,
            details=f"Purchase Order {status}",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        messages.success(request, f'Purchase Order {po.po_number} has been {status}.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'PO {status}'})
            
        return redirect(request.META.get('HTTP_REFERER', '/purchase-orders/'))
        
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def update_po(request, po_id):
    if request.method == 'POST':
        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        # Safely handle empty strings for date fields
        new_po_date = request.POST.get('po_date')
        if new_po_date:
            po.po_date = new_po_date
            
        po.supplier = request.POST.get('supplier', po.supplier)
        po.comments = request.POST.get('comments', po.comments)
        po.save()
        PurchaseOrderLog.objects.create(
            purchase_order=po,
            action='update',
            po_number=po.po_number,
            details=f"Updated PO metadata",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        messages.success(request, f'Purchase Order {po.po_number} updated.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def delete_po_item(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(PurchaseOrderItem, id=item_id)
        po = item.purchase_order
        name = item.product_name
        po.total -= (item.total or 0)
        po.save()
        item.delete()
        PurchaseOrderLog.objects.create(
            purchase_order=po,
            action='update',
            po_number=po.po_number,
            details=f"Deleted item {name}",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        messages.success(request, f'Item "{name}" removed from PO.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def update_po_item(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(PurchaseOrderItem, id=item_id)
        po = item.purchase_order
        po.total -= (item.total or 0)
        item.quantity = float(request.POST.get('quantity') or item.quantity)
        item.unit = request.POST.get('unit', item.unit)
        item.unit_price = float(request.POST.get('unit_price') or item.unit_price)
        item.remarks = request.POST.get('remarks', item.remarks)
        item.total = item.quantity * item.unit_price
        item.save()
        po.total += item.total
        po.save()
        PurchaseOrderLog.objects.create(
            purchase_order=po,
            action='update',
            po_number=po.po_number,
            details=f"Updated item {item.product_name}",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        messages.success(request, f'Item "{item.product_name}" updated.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def toggle_po_lock(request, po_id):
    if request.method == 'POST':
        po = get_object_or_404(PurchaseOrder, id=po_id)
        po.status = 'Locked' if po.status == 'Open' else 'Open'
        po.save()
        action = 'lock' if po.status == 'Locked' else 'unlock'
        PurchaseOrderLog.objects.create(
            purchase_order=po,
            action=action,
            po_number=po.po_number,
            details=f"Purchase Order {po.status}",
            user=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        messages.success(request, f'Purchase Order {po.po_number} is now {po.status}.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)


# ============================================================
# Dashboard Views
# ============================================================

def log_activity(action, description, user='admin', entity_type='', entity_id=None):
    """Helper to log activity for the dashboard timeline."""
    ActivityLog.objects.create(
        action=action,
        description=description,
        user=user,
        entity_type=entity_type,
        entity_id=entity_id
    )


@login_required
def dashboard_view(request):
    # Inventory stats
    all_active = InventoryItem.objects.filter(is_archived=False)
    total_items = all_active.count()
    low_stock_count = all_active.filter(is_negative='no', total_balance__gt=0, total_balance__lte=10).count()
    out_of_stock_count = all_active.filter(Q(is_negative='yes') | Q(total_balance__lte=0)).count()

    total_value = 0.0
    for item in all_active:
        try:
            total_value += item.inventory_value
        except:
            pass

    # Employee stats
    active_employees = Employee.objects.filter(is_archived=False, status='Active').count()
    total_employees = Employee.objects.filter(is_archived=False).count()

    # Recent activity (from ActivityLog + InventoryLog as fallback)
    recent_activities = ActivityLog.objects.all()[:20]
    if not recent_activities.exists():
        # Seed from existing inventory logs
        recent_inv_logs = InventoryLog.objects.order_by('-timestamp')[:20]
        activity_list = []
        for log in recent_inv_logs:
            activity_list.append({
                'action': log.transaction_type,
                'description': f"{log.transaction_type.title()} {log.quantity} units of {log.inventory_item.name}",
                'user': log.user,
                'timestamp': log.timestamp.strftime('%d %b %Y %H:%M'),
                'entity_type': 'InventoryItem',
            })
    else:
        activity_list = [{
            'action': a.action,
            'description': a.description,
            'user': a.user,
            'timestamp': a.timestamp.strftime('%d %b %Y %H:%M'),
            'entity_type': a.entity_type,
        } for a in recent_activities]

    # Chart data — inventory by type (pie chart)
    type_counts = all_active.values('item_type').annotate(count=Count('id')).order_by('-count')[:8]
    pie_labels = [t['item_type'] or 'Uncategorized' for t in type_counts]
    pie_data = [t['count'] for t in type_counts]
    pie_colors = ['#ec4899', '#f472b6', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#64748b']

    # Chart data — monthly inventory trend (bar chart)
    now = timezone.now()
    trend_labels = []
    trend_purchases = []
    trend_withdrawals = []
    for i in range(5, -1, -1):
        month = (now.month - i - 1) % 12 + 1
        year = now.year + (now.month - i - 1) // 12
        trend_labels.append(datetime(year, month, 1).strftime('%b %y'))
        
        # Calculate start and end dates for the month to avoid CONVERT_TZ issues in MySQL
        start_date = timezone.make_aware(datetime(year, month, 1))
        if month == 12:
            end_date = timezone.make_aware(datetime(year + 1, 1, 1))
        else:
            end_date = timezone.make_aware(datetime(year, month + 1, 1))
            
        month_logs = InventoryLog.objects.filter(timestamp__gte=start_date, timestamp__lt=end_date)
        trend_purchases.append(month_logs.filter(transaction_type='purchase').count())
        trend_withdrawals.append(month_logs.filter(transaction_type='withdrawal').count())

    # Low stock items for mini table
    low_stock_items = []
    for item in all_active.order_by('total_balance')[:5]:
        balance = item.total_balance
        if item.is_negative == 'yes' or balance <= 0:
            status = 'Out of Stock'
        elif 0 < balance <= 10:
            status = 'Low Stock'
        else:
            status = 'In Stock'
        low_stock_items.append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'balance': balance,
            'status': status,
            'item_type': item.item_type,
        })

    context = {
        'active_page': 'dashboard',
        'stats': {
            'total_items': total_items,
            'low_stock': low_stock_count,
            'out_of_stock': out_of_stock_count,
            'active_employees': active_employees,
            'total_employees': total_employees,
            'total_value': f"\u20b1{total_value:,.2f}",
        },
        'activities': activity_list,
        'chart_pie': json.dumps({
            'labels': pie_labels,
            'data': pie_data,
            'colors': pie_colors[:len(pie_data)],
        }),
        'chart_trend': json.dumps({
            'labels': trend_labels,
            'purchases': trend_purchases,
            'withdrawals': trend_withdrawals,
        }),
        'low_stock_items': low_stock_items,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def api_dashboard_stats(request):
    """JSON endpoint for dashboard charts with optional date filtering."""
    start_date = request.GET.get('startDate')
    end_date = request.GET.get('endDate')

    logs = InventoryLog.objects.all()
    if start_date:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(start_date, '%Y-%m-%d'), time.min))
            logs = logs.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(end_date, '%Y-%m-%d'), time.max))
            logs = logs.filter(timestamp__lte=end_dt)
        except ValueError:
            pass
    

    stats = {
        'purchases': logs.filter(transaction_type='purchase').count(),
        'withdrawals': logs.filter(transaction_type='withdrawal').count(),
        'damage': logs.filter(transaction_type='damage').count(),
        'returned': logs.filter(transaction_type='returned').count(),
    }
    return JsonResponse({'success': True, 'stats': stats})


@login_required
def api_activity_log(request):
    """JSON endpoint returning the latest activity entries."""
    limit = int(request.GET.get('limit', 20))
    activities = ActivityLog.objects.all()[:limit]
    data = [{
        'action': a.action,
        'description': a.description,
        'user': a.user,
        'entity_type': a.entity_type,
        'timestamp': a.timestamp.strftime('%d %b %Y %H:%M'),
    } for a in activities]
    return JsonResponse({'success': True, 'activities': data})


# ============================================================
# Employment Views
# ============================================================

@login_required
def employee_list_view(request):
    employees_base = Employee.objects.filter(is_archived=False).order_by('-created_at')
    archived_employees = Employee.objects.filter(is_archived=True).order_by('-created_at')
    departments = Employee.objects.values_list('department', flat=True).distinct()

    total_count = employees_base.count() + archived_employees.count()
    terminated_count = employees_base.filter(status='Terminated').count() + archived_employees.count()

    stats = {
        'total': total_count,
        'active': employees_base.filter(status='Active').count(),
        'on_leave': employees_base.filter(status='On-Leave').count(),
        'terminated': terminated_count,
    }

    filter_by = request.GET.get('filter', 'all')
    stats['current_filter'] = filter_by

    from django.db.models import Q

    if filter_by == 'active':
        employees = employees_base.filter(status='Active')
    elif filter_by == 'on_leave':
        employees = employees_base.filter(status='On-Leave')
    elif filter_by == 'terminated':
        employees = Employee.objects.filter(Q(status='Terminated') | Q(is_archived=True)).order_by('-created_at')
    else:
        # Default 'all' shows only active directory employees as before, or both? 
        # Usually 'all' shows active ones, not archived unless in archive tab.
        employees = employees_base

    return render(request, 'employees/employee_list.html', {
        'active_page': 'employees',
        'employees': employees,
        'archived_employees': archived_employees,
        'departments': [d for d in departments if d],
        'stats': stats,
    })


@login_required
def employee_detail_view(request, emp_id):
    from datetime import date, timedelta
    employee = get_object_or_404(Employee, id=emp_id)
    education = employee.education_records.all()
    skills = employee.skills.all()
    work_history = employee.employment_history.all()
    documents = employee.documents.all()

    today = date.today()
    upcoming = today + timedelta(days=30)

    return render(request, 'employees/employee_detail.html', {
        'active_page': 'employees',
        'employee': employee,
        'education': education,
        'certifications': education.exclude(entry_type='education'),
        'degrees': education.filter(entry_type='education'),
        'skills': skills,
        'work_history': work_history,
        'documents': documents,
        'today': today,
        'upcoming': upcoming,
    })


@csrf_exempt
@login_required
def create_employee(request):
    if request.method == 'POST':
        try:
            data = request.POST
            # Auto-generate employee ID
            count = Employee.objects.count() + 1
            emp_id = f"EMP-{count:04d}"
            while Employee.objects.filter(employee_id=emp_id).exists():
                count += 1
                emp_id = f"EMP-{count:04d}"

            emp = Employee.objects.create(
                employee_id=emp_id,
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                middle_name=data.get('middle_name', ''),
                work_email=data.get('work_email', ''),
                phone=data.get('phone', ''),
                position=data.get('position', ''),
                department=data.get('department', ''),
                contract_type=data.get('contract_type', 'Full-Time'),
                status=data.get('status', 'Active'),
                gender=data.get('gender', 'Male'),
                date_of_birth=data.get('date_of_birth') or None,
                date_hired=data.get('date_hired') or None,
                created_by=request.user.username if request.user.is_authenticated else 'admin',
            )

            # Handle avatar upload
            avatar_file = request.FILES.get('avatar')
            if avatar_file:
                emp.avatar = handle_uploaded_image(avatar_file)
                emp.save()

            log_activity('created', f'New employee added: {emp.full_name}',
                         user=request.user.username if request.user.is_authenticated else 'admin',
                         entity_type='Employee', entity_id=emp.id)

            messages.success(request, f'Employee "{emp.full_name}" created successfully.')
            return JsonResponse({'success': True, 'id': emp.id})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)


@csrf_exempt
@login_required
def update_employee(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        try:
            data = request.POST
            # Text fields
            text_fields = [
                'first_name', 'last_name', 'middle_name', 'work_email',
                'personal_email', 'phone', 'home_address', 'position',
                'department', 'reporting_manager', 'contract_type', 'status',
                'gender', 'marital_status', 'nationality', 'pay_grade',
                'emergency_contact_name', 'emergency_contact_phone',
                'emergency_contact_relationship',
            ]
            for field in text_fields:
                if field in data:
                    setattr(employee, field, data.get(field))

            # Date fields
            for datefield in ['date_of_birth', 'date_hired', 'probation_end_date', 'contract_renewal_date']:
                if datefield in data:
                    val = data.get(datefield)
                    setattr(employee, datefield, val if val else None)

            # Numeric fields
            if 'salary' in data:
                employee.salary = float(data.get('salary') or 0)

            # Avatar
            avatar_file = request.FILES.get('avatar')
            if avatar_file:
                employee.avatar = handle_uploaded_image(avatar_file)

            employee.save()

            log_activity('updated', f'Employee updated: {employee.full_name}',
                         user=request.user.username if request.user.is_authenticated else 'admin',
                         entity_type='Employee', entity_id=employee.id)

            messages.success(request, f'Employee "{employee.full_name}" updated successfully.')
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)


@csrf_exempt
@login_required
def delete_employee(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        employee.is_archived = True
        employee.status = 'Terminated'
        employee.save()
        log_activity('archived', f'Employee archived: {employee.full_name}',
                     user=request.user.username if request.user.is_authenticated else 'admin',
                     entity_type='Employee', entity_id=employee.id)
        messages.success(request, f'Employee "{employee.full_name}" archived.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)


@csrf_exempt
@login_required
def unarchive_employee(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        employee.is_archived = False
        employee.status = 'Active'
        employee.save()
        log_activity('unarchived', f'Employee unarchived: {employee.full_name}',
                     user=request.user.username if request.user.is_authenticated else 'admin',
                     entity_type='Employee', entity_id=employee.id)
        messages.success(request, f'Employee "{employee.full_name}" unarchived successfully.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def hard_delete_employee(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        if not employee.is_archived:
            return JsonResponse({'success': False, 'message': 'Only archived employees can be permanently deleted'}, status=400)
        
        full_name = employee.full_name
        employee.delete()
        log_activity('deleted', f'Employee permanently deleted: {full_name}',
                     user=request.user.username if request.user.is_authenticated else 'admin',
                     entity_type='Employee', entity_id=emp_id)
        messages.success(request, f'Employee "{full_name}" permanently deleted.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)


@csrf_exempt
@login_required
def upload_employee_document(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES.get('document')
            if not uploaded_file:
                return JsonResponse({'success': False, 'message': 'No file provided'}, status=400)

            # Backend validation for allowed file extensions
            allowed_extensions = ['.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg']
            file_extension = '.' + uploaded_file.name.split('.')[-1].lower() if '.' in uploaded_file.name else ''
            if file_extension not in allowed_extensions:
                return JsonResponse({'success': False, 'message': f'Invalid file format. Allowed formats are: {", ".join(allowed_extensions)}'}, status=400)

            binary_data = uploaded_file.read()
            b64 = base64.b64encode(binary_data).decode('utf-8')

            doc = EmployeeDocument.objects.create(
                employee=employee,
                file_name=uploaded_file.name,
                file_data=b64,
                file_type=uploaded_file.content_type or 'application/octet-stream',
                document_type=request.POST.get('document_type', 'Other'),
                uploaded_by=request.user.username if request.user.is_authenticated else 'admin',
            )

            log_activity('uploaded', f'Document uploaded for {employee.full_name}: {doc.file_name}',
                         user=request.user.username if request.user.is_authenticated else 'admin',
                         entity_type='EmployeeDocument', entity_id=doc.id)

            messages.success(request, f'Document "{doc.file_name}" uploaded.')
            return JsonResponse({'success': True, 'doc_id': doc.id, 'file_name': doc.file_name})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)


@login_required
def download_employee_document(request, emp_id, doc_id):
    doc = get_object_or_404(EmployeeDocument, id=doc_id, employee_id=emp_id)
    import io
    file_bytes = base64.b64decode(doc.file_data)
    response = HttpResponse(file_bytes, content_type=doc.file_type)
    response['Content-Disposition'] = f'attachment; filename="{doc.file_name}"'
    return response

@login_required
def view_employee_document(request, emp_id, doc_id):
    doc = get_object_or_404(EmployeeDocument, id=doc_id, employee_id=emp_id)
    file_bytes = base64.b64decode(doc.file_data)
    response = HttpResponse(file_bytes, content_type=doc.file_type)
    response['Content-Disposition'] = f'inline; filename="{doc.file_name}"'
    return response


@csrf_exempt
@login_required
def delete_employee_document(request, emp_id, doc_id):
    doc = get_object_or_404(EmployeeDocument, id=doc_id, employee_id=emp_id)
    if request.method == 'POST':
        fname = doc.file_name
        doc.delete()
        messages.success(request, f'Document "{fname}" deleted.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def add_employee_education(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        try:
            entry_type = request.POST.get('entry_type', 'education')
            degree = request.POST.get('degree', '')
            institution = request.POST.get('institution', '')
            year_completed = request.POST.get('year_completed')
            expiry_date = request.POST.get('expiry_date')

            if year_completed:
                year_completed = int(year_completed)
            else:
                year_completed = None

            if not expiry_date:
                expiry_date = None

            EmployeeEducation.objects.create(
                employee=employee,
                entry_type=entry_type,
                degree=degree,
                institution=institution,
                year_completed=year_completed,
                expiry_date=expiry_date
            )
            messages.success(request, f'Success: Added {degree}.')
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def delete_employee_education(request, emp_id, edu_id):
    edu = get_object_or_404(EmployeeEducation, id=edu_id, employee_id=emp_id)
    if request.method == 'POST':
        edu.delete()
        messages.success(request, 'Education/Certification deleted.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def add_employee_skill(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            if name:
                EmployeeSkill.objects.create(employee=employee, name=name)
                messages.success(request, f'Skill "{name}" added.')
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'message': 'Skill name is required.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def delete_employee_skill(request, emp_id, skill_id):
    skill = get_object_or_404(EmployeeSkill, id=skill_id, employee_id=emp_id)
    if request.method == 'POST':
        skill.delete()
        messages.success(request, 'Skill deleted.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def add_employee_employment_history(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        try:
            company_name = request.POST.get('company_name', '').strip()
            role = request.POST.get('role', '').strip()
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            responsibilities = request.POST.get('responsibilities', '').strip()

            if not company_name:
                return JsonResponse({'success': False, 'message': 'Company name is required.'})

            EmploymentHistory.objects.create(
                employee=employee,
                company_name=company_name,
                role=role,
                start_date=start_date if start_date else None,
                end_date=end_date if end_date else None,
                responsibilities=responsibilities
            )
            messages.success(request, f'Employment history at {company_name} added.')
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def delete_employee_employment_history(request, emp_id, history_id):
    history = get_object_or_404(EmploymentHistory, id=history_id, employee_id=emp_id)
    if request.method == 'POST':
        history.delete()
        messages.success(request, 'Employment history deleted.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

@login_required
def export_employee_pdf(request, emp_id):
    """Generate a comprehensive HTML-based PDF of employee profile for printing."""
    employee = get_object_or_404(Employee, id=emp_id)
    from datetime import date
    
    # Fetch related data
    education = employee.education_records.all()
    skills = employee.skills.all()
    history = employee.employment_history.all()
    
    # Profile image logic
    avatar_html = ""
    if employee.avatar:
        avatar_html = f'<img src="{employee.avatar}" class="profile-img" alt="Profile Picture">'
    else:
        initials = f"{employee.first_name[0]}{employee.last_name[0]}" if employee.first_name and employee.last_name else "EP"
        avatar_html = f'<div class="profile-placeholder">{initials}</div>'

    # Build education list
    edu_list = ""
    if education:
        for edu in education:
            edu_list += f"""
            <div class="item">
                <div class="item-title">{edu.degree}</div>
                <div class="item-subtitle">{edu.institution} | {edu.year_completed or ''}</div>
            </div>"""
    else:
        edu_list = "<p class='text-muted'>No education records found.</p>"

    # Build history list
    hist_list = ""
    if history:
        for h in history:
            hist_list += f"""
            <div class="item">
                <div class="item-title">{h.role}</div>
                <div class="item-subtitle">{h.company_name} ({h.start_date or 'N/A'} - {h.end_date or 'Present'})</div>
                <div class="item-desc">{h.responsibilities or ''}</div>
            </div>"""
    else:
        hist_list = "<p class='text-muted'>No work history found.</p>"

    # Build skills list
    skills_text = ", ".join([s.name for s in skills]) if skills else "None listed"

    # Build a sophisticated HTML string for the PDF
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ 
                margin: 0; /* Removing margins often hides default headers/footers in many browsers */
                size: A4 portrait;
            }}
            @media print {{
                html, body {{
                    width: 210mm;
                    height: 297mm;
                }}
                body {{ 
                    -webkit-print-color-adjust: exact; 
                    print-color-adjust: exact; 
                    margin: 0;
                    padding: 1.5cm; /* Ensure content isn't flush with edge since @page margin is 0 */
                }}
                .no-print {{ display: none; }}
                /* Forces page break before these sections to prevent ugly splits */
                .page-break {{ page-break-before: always; }}
                /* Prevent elements from being split across PDF pages */
                .section, .item {{ page-break-inside: avoid; }}
            }}
            
            body {{ font-family: 'Segoe UI', Roboto, Arial, sans-serif; line-height: 1.6; color: #334155; margin: 0; padding: 1.5cm; background: #fff; box-sizing: border-box; }}
            .header {{ display: flex; align-items: center; border-bottom: 3px solid #ec4899; padding-bottom: 20px; margin-bottom: 30px; }}
            .profile-img {{ width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 4px solid #fce7f3; margin-right: 25px; }}
            .profile-placeholder {{ width: 120px; height: 120px; border-radius: 50%; background: #fce7f3; color: #db2777; display: flex; align-items: center; justify-content: center; font-size: 40px; font-weight: bold; margin-right: 25px; border: 4px solid #fce7f3; }}
            .header-info h1 {{ font-size: 28px; color: #be185d; margin: 0; text-transform: uppercase; letter-spacing: 1px; }}
            .header-info p {{ font-size: 16px; color: #64748b; margin: 5px 0 0 0; font-weight: 500; }}
            
            .section {{ margin-bottom: 25px; }}
            .section-title {{ font-size: 18px; color: #be185d; border-bottom: 1px solid #fce7f3; padding-bottom: 5px; margin-bottom: 15px; font-weight: 600; text-transform: uppercase; }}
            
            .row {{ display: flex; flex-wrap: wrap; margin: 0 -15px; }}
            .col {{ flex: 1; padding: 0 15px; min-width: 250px; }}
            
            .field {{ margin-bottom: 10px; display: flex; }}
            .label {{ font-weight: 600; color: #475569; width: 140px; flex-shrink: 0; font-size: 13px; }}
            .value {{ color: #1e293b; font-size: 14px; }}
            
            .item {{ margin-bottom: 12px; }}
            .item-title {{ font-weight: 600; color: #1e293b; font-size: 15px; }}
            .item-subtitle {{ font-size: 13px; color: #64748b; }}
            .item-desc {{ font-size: 13px; color: #475569; margin-top: 3px; font-style: italic; }}
            
            .text-muted {{ color: #94a3b8; font-style: italic; font-size: 13px; }}
            
            @media print {{
                body {{ -webkit-print-color-adjust: exact; }}
                .no-print {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            {avatar_html}
            <div class="header-info">
                <h1>{employee.full_name}</h1>
                <p>Employee ID: {employee.employee_id} | {employee.position or 'No Position'}</p>
                <p>{employee.department or 'No Department'}</p>
            </div>
        </div>

        <div class="row">
            <div class="col">
                <div class="section">
                    <div class="section-title">Personal Information</div>
                    <div class="field"><span class="label">Date of Birth:</span><span class="value">{employee.date_of_birth or 'N/A'}</span></div>
                    <div class="field"><span class="label">Age:</span><span class="value">{employee.age}</span></div>
                    <div class="field"><span class="label">Gender:</span><span class="value">{employee.gender}</span></div>
                    <div class="field"><span class="label">Marital Status:</span><span class="value">{employee.marital_status or 'N/A'}</span></div>
                    <div class="field"><span class="label">Nationality:</span><span class="value">{employee.nationality or 'N/A'}</span></div>
                </div>
            </div>
            <div class="col">
                <div class="section">
                    <div class="section-title">Contact Details</div>
                    <div class="field"><span class="label">Work Email:</span><span class="value">{employee.work_email or 'N/A'}</span></div>
                    <div class="field"><span class="label">Personal Email:</span><span class="value">{employee.personal_email or 'N/A'}</span></div>
                    <div class="field"><span class="label">Phone:</span><span class="value">{employee.phone or 'N/A'}</span></div>
                    <div class="field"><span class="label">Home Address:</span><span class="value">{employee.home_address or 'N/A'}</span></div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col">
                <div class="section">
                    <div class="section-title">Employment Details</div>
                    <div class="field"><span class="label">Status:</span><span class="value">{employee.status}</span></div>
                    <div class="field"><span class="label">Date Hired:</span><span class="value">{employee.date_hired or 'N/A'}</span></div>
                    <div class="field"><span class="label">Probation End:</span><span class="value">{employee.probation_end_date or 'N/A'}</span></div>
                    <div class="field"><span class="label">Contract Type:</span><span class="value">{employee.contract_type}</span></div>
                    <div class="field"><span class="label">Contract Renewal:</span><span class="value">{employee.contract_renewal_date or 'N/A'}</span></div>
                    <div class="field"><span class="label">Reporting Manager:</span><span class="value">{employee.reporting_manager or 'N/A'}</span></div>
                    <div class="field"><span class="label">Salary:</span><span class="value">₱{employee.salary:,.2f}</span></div>
                    <div class="field"><span class="label">Pay Grade:</span><span class="value">{employee.pay_grade or 'N/A'}</span></div>
                </div>
            </div>
            <div class="col">
                <div class="section">
                    <div class="section-title">Emergency Contact</div>
                    <div class="field"><span class="label">Name:</span><span class="value">{employee.emergency_contact_name or 'N/A'}</span></div>
                    <div class="field"><span class="label">Phone:</span><span class="value">{employee.emergency_contact_phone or 'N/A'}</span></div>
                    <div class="field"><span class="label">Relationship:</span><span class="value">{employee.emergency_contact_relationship or 'N/A'}</span></div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col">
                <div class="section">
                    <div class="section-title">Education & Certifications</div>
                    {edu_list}
                </div>
                <div class="section">
                    <div class="section-title">Skills</div>
                    <div class="value">{skills_text}</div>
                </div>
            </div>
            <div class="col">
                <div class="section">
                    <div class="section-title">Work Experience</div>
                    {hist_list}
                </div>
            </div>
        </div>
        
        <div style="margin-top: 50px; text-align: center; color: #94a3b8; font-size: 11px; border-top: 1px solid #f1f5f9; padding-top: 10px;">
        </div>
    </body>
    </html>
    """

    from django.http import HttpResponse
    response = HttpResponse(html_content, content_type='text/html')
    return response

@login_required
def cgs_view(request):
    items = JobOrderProduct.objects.all().select_related('job_order', 'job_order__client', 'product')
    
    # Filter logic
    pid = request.GET.get('pid')
    wip = request.GET.get('wip')
    client_name = request.GET.get('name')
    product_name = request.GET.get('product_name')
    is_fully_paid = request.GET.get('is_fully_paid')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    sort_by = request.GET.get('sort', '-transaction_date')
    
    if pid:
        items = items.filter(pid__icontains=pid)
    if wip:
        items = items.filter(job_order__wip__icontains=wip)
    if client_name:
        items = items.filter(
            Q(name__icontains=client_name) | 
            Q(job_order__client__first_name__icontains=client_name) | 
            Q(job_order__client__last_name__icontains=client_name) |
            Q(job_order__client__business_name__icontains=client_name)
        )
    if product_name:
        items = items.filter(product_name__icontains=product_name)
    if is_fully_paid:
        items = items.filter(job_order__is_fully_paid=(is_fully_paid == 'Yes'))
    if start_date:
        items = items.filter(transaction_date__gte=start_date)
    if end_date:
        items = items.filter(transaction_date__lte=end_date)
        
    # Apply sorting (default to newest first)
    items = items.order_by(sort_by if sort_by else '-transaction_date')
    
    # Pre-sync missing costs and names for the report (Audit loop)
    # This ensures report accuracy even if records weren't fully initialized
    for item in items:
        updated = False
        # Sync Client Name
        if not item.name and item.job_order and item.job_order.client:
            item.name = item.job_order.client.full_name
            updated = True
        
        # Sync Materials Cost
        if item.materials_cost == 0:
            total_m = item.jop_materials.aggregate(total=Sum('total_cost'))['total'] or 0.0
            if total_m > 0:
                item.materials_cost = total_m
                updated = True
        
        # Sync Labor Cost
        if item.labor_cost == 0:
            total_l = item.labor_outputs.aggregate(total=Sum('total'))['total'] or 0.0
            if total_l > 0:
                item.labor_cost = total_l
                updated = True
                
        # Sync Overhead and Markup from base Product if still zero
        if item.product:
            if item.overhead_cost == 0 and item.product.overhead > 0:
                item.overhead_cost = item.product.overhead
                updated = True
            if item.markup_cost == 0 and item.product.markup > 0:
                item.markup_cost = item.product.markup
                updated = True
        
        if updated:
            item.save(update_fields=['name', 'materials_cost', 'labor_cost', 'overhead_cost', 'markup_cost'])

    # Summary Totals (calculated from filtered items)
    totals = items.aggregate(
        total_materials=Sum('materials_cost'),
        total_labor=Sum('labor_cost'),
        total_overhead=Sum('overhead_cost'),
        total_markup=Sum('markup_cost'),
    )
    
    # Pagination
    show_all = request.GET.get('all') == 'true'
    if not show_all:
        paginator = Paginator(items, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        display_items = page_obj
    else:
        page_obj = None
        display_items = items

    context = {
        'items': display_items,
        'page_obj': page_obj,
        'show_all': show_all,
        'totals': totals,
        'now': timezone.now(),
        'active_page': 'jo_products_cgs'
    }
    return render(request, 'reports/cgs_report.html', context)

@login_required
def employee_salary_view(request):
    log_date_start = request.GET.get('log_date_start', '')
    log_date_end = request.GET.get('log_date_end', '')

    if request.method == 'POST':
        action = request.POST.get('action')
        user_name = request.user.username if request.user.is_authenticated else 'admin'
        
        if action == 'delete':
            salary_id = request.POST.get('salary_id')
            salary = get_object_or_404(EmployeeSalary, id=salary_id)
            emp = salary.employee
            emp.salary = 0
            emp.save()
            
            # Log deletion
            log_activity('deleted', f"Salary record removed for {emp.full_name}", 
                         user=user_name, entity_type='EmployeeSalary', entity_id=salary_id)
            
            salary.delete()
            messages.success(request, f"Salary removed for {emp.full_name}")
            return redirect('employee_salary')

        employee_id = request.POST.get('employee_id')
        amount = float(request.POST.get('amount', 0))
        employee = get_object_or_404(Employee, id=employee_id)
        
        # Check if record exists for logging purposes
        existing_salary = EmployeeSalary.objects.filter(employee=employee).first()
        old_amount = existing_salary.amount if existing_salary else 0
        
        salary, created = EmployeeSalary.objects.update_or_create(
            employee=employee,
            defaults={'amount': amount, 'updated_by': user_name}
        )
        
        # Prepare log description
        if created:
            log_action = 'created'
            desc = f"Added new salary record for {employee.full_name}: ₱{amount:,.2f}"
        else:
            log_action = 'updated'
            if old_amount != amount:
                desc = f"Updated salary for {employee.full_name}:\n• Amount: ₱{old_amount:,.2f} → ₱{amount:,.2f}"
            else:
                desc = f"Updated salary record for {employee.full_name} (No amount change)"

        log_activity(log_action, desc, user=user_name, entity_type='EmployeeSalary', entity_id=salary.id)

        # Also update the main Employee model's salary field for consistency
        employee.salary = amount
        employee.save()
        
        messages.success(request, f"Salary updated for {employee.full_name}")
        return redirect('employee_salary')

    items = EmployeeSalary.objects.filter(
        employee__is_archived=False
    ).exclude(
        employee__status='Terminated'
    ).order_by('employee__first_name')
    
    employees = Employee.objects.filter(
        is_archived=False
    ).exclude(
        status='Terminated'
    )
    
    # Fetch Activity Logs for Salaries
    salary_logs_query = ActivityLog.objects.filter(entity_type='EmployeeSalary').order_by('-timestamp')
    
    if log_date_start:
        try:
            start_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_start, '%Y-%m-%d'), time.min))
            salary_logs_query = salary_logs_query.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    if log_date_end:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(log_date_end, '%Y-%m-%d'), time.max))
            salary_logs_query = salary_logs_query.filter(timestamp__lte=end_dt)
        except ValueError:
            pass
            
    salary_logs = salary_logs_query[:100] # Limit to latest 100 for safety, frontend handles pagination
    
    context = {
        'items': items,
        'employees': employees,
        'salary_logs': salary_logs,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end,
        'active_page': 'employee_salary'
    }
    return render(request, 'employees/employee_salary.html', context)

@login_required
def payroll_view(request):
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        payroll = Payroll.objects.create(
            start_date=start_date,
            end_date=end_date,
            created_by=request.user.username
        )
        
        # Pre-populate records
        employees = Employee.objects.filter(is_archived=False, status='Active')
        for emp in employees:
            # Get latest salary
            salary_obj = EmployeeSalary.objects.filter(employee=emp).last()
            salary_rate = salary_obj.amount if salary_obj else emp.salary
            
            # Sum labor from LaborOutput in this period
            total_labor = LaborOutput.objects.filter(
                employee=emp,
                date_accomplished__range=[start_date, end_date],
                approved_by__isnull=False # only approved
            ).aggregate(Sum('total'))['total__sum'] or 0.0
            
            PayrollRecord.objects.create(
                payroll=payroll,
                employee=emp,
                salary_rate=salary_rate,
                total_labor=total_labor,
                # All deductions start at 0
            )
            
        # Log activity
        log_activity(
            user=request.user.username,
            action="created",
            entity_type="Payroll",
            entity_id=str(payroll.id),
            description=f"Created new payroll period: {start_date} to {end_date}"
        )
        
        messages.success(request, "Payroll period created successfully.")
        return redirect('payroll')

    # Activity Logs with filtering
    log_date_start = request.GET.get('log_date_start')
    log_date_end = request.GET.get('log_date_end')
    
    logs = ActivityLog.objects.filter(
        Q(entity_type='Payroll') | Q(entity_type='PayrollRecord')
    )
    
    if log_date_start:
        logs = logs.filter(timestamp__date__gte=log_date_start)
    if log_date_end:
        logs = logs.filter(timestamp__date__lte=log_date_end)
        
    items = Payroll.objects.all().order_by('-start_date')
    context = {
        'items': items,
        'payroll_logs': logs,
        'log_date_start': log_date_start,
        'log_date_end': log_date_end,
        'active_page': 'payroll'
    }
    return render(request, 'payroll/payroll_list.html', context)

@login_required
def payroll_detail_view(request, payroll_id):
    payroll = get_object_or_404(Payroll, id=payroll_id)
    records = payroll.records.all().order_by('employee__first_name')
    
    # Recalculate grand total from net totals
    total_amount = sum(r.total_amount for r in records)
    
    context = {
        'payroll': payroll,
        'records': records,
        'total_amount': total_amount,
        'active_page': 'payroll'
    }
    return render(request, 'payroll/payroll_detail.html', context)

@login_required
@require_POST
def update_payroll_record(request):
    record_id = request.POST.get('record_id')
    record = get_object_or_404(PayrollRecord, id=record_id)
    
    try:
        record.salary_rate = float(request.POST.get('salary_rate', record.salary_rate))
        record.total_labor = float(request.POST.get('total_labor', record.total_labor))
        record.cash_advance = float(request.POST.get('cash_advance', 0))
        record.incident_report = float(request.POST.get('incident_report', 0))
        record.benefits = float(request.POST.get('benefits', 0))
        record.absences = float(request.POST.get('absences', 0))
        record.tardiness = float(request.POST.get('tardiness', 0))
        
        record.save()
        
        # Log activity
        log_activity(
            user=request.user.username,
            action="updated",
            entity_type="PayrollRecord",
            entity_id=str(record.id),
            description=f"Updated payroll row for {record.employee.full_name} in period {record.payroll.start_date} to {record.payroll.end_date}"
        )
        
        return JsonResponse({
            'status': 'success', 
            'net_total': record.total_amount,
            'total_deductions': record.total_deductions,
            'gross_total': record.gross_total
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def withdrawal_slip_detail_view(request, slip_id):
    slip = get_object_or_404(WithdrawalSlip, id=slip_id)
    # Check if linked to JO via wip
    jo = JobOrder.objects.filter(wip=slip.wip).first()
    inventory_items = InventoryItem.objects.filter(is_archived=False).order_by('name')
    
    items = slip.items.all().order_by('id')
    
    # Backfill product_name if empty for legacy records
    if jo:
        for item in items:
            if not item.product_name:
                # Try to find which product this material belongs to
                potential_mat = JobOrderProductMaterial.objects.filter(
                    job_order_product__job_order=jo,
                    item_name=item.item_name
                ).first()
                if potential_mat:
                    item.product_name = potential_mat.job_order_product.product_name
                    item.jop_material = potential_mat # Also link it if empty
                    item.save()
                    
    context = {
        'slip': slip,
        'items': items,
        'jo': jo,
        'inventory_items': inventory_items,
        'active_page': 'withdrawal_slips'
    }
    return render(request, 'withdrawal/withdrawal_slip_detail.html', context)

@login_required
@require_POST
def create_withdrawal_slip_ajax(request):
    try:
        data = json.loads(request.body)
        wip = data.get('wip', '')
        name = data.get('name', '')
        
        slip = WithdrawalSlip.objects.create(
            wip=wip,
            name=name,
            status='Pending',
            created_by=request.user.username if request.user.is_authenticated else 'Stephen'
        )
        
        ActivityLog.objects.create(
            user=request.user.username if request.user.is_authenticated else 'Stephen',
            action="created",
            entity_type='WithdrawalSlip',
            entity_id=slip.id,
            description=f"Manually created Withdrawal Slip WS-{slip.id} for WIP {wip}"
        )
        
        return JsonResponse({'success': True, 'id': slip.id})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@require_POST
def add_withdrawal_slip_item_ajax(request, slip_id):
    try:
        data = json.loads(request.body)
        inv_item_id = data.get('inventory_item_id')
        prod_name = data.get('product_name', '')
        qty = float(data.get('quantity', 0))
        
        slip = get_object_or_404(WithdrawalSlip, id=slip_id)
        inv_item = get_object_or_404(InventoryItem, id=inv_item_id) if inv_item_id else None
        
        WithdrawalSlipItem.objects.create(
            withdrawal_slip=slip,
            inventory_item=inv_item,
            product_name=prod_name,
            item_name=inv_item.name if inv_item else "Unknown Item",
            quantity=qty,
            withdrawal_slip_number=f"WS-{slip.id}"
        )
        
        ActivityLog.objects.create(
            user=request.user.username if request.user.is_authenticated else 'Stephen',
            action="added_material",
            entity_type='WithdrawalSlip',
            entity_id=slip.id,
            description=f"Added material '{inv_item.name if inv_item else prod_name}' (Qty: {qty}) to WS-{slip.id}"
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@require_POST
def delete_withdrawal_slip_item_ajax(request, item_id):
    try:
        item = get_object_or_404(WithdrawalSlipItem, id=item_id)
        if item.withdrawal_slip.status != 'Pending':
            return JsonResponse({'success': False, 'message': 'Cannot delete items from a completed slip.'})
        
        slip_id = item.withdrawal_slip.id
        item_name = item.item_name
        item.delete()
        
        ActivityLog.objects.create(
            user=request.user.username if request.user.is_authenticated else 'Stephen',
            action="deleted",
            entity_type='WithdrawalSlip',
            entity_id=slip_id,
            description=f"Deleted item '{item_name}' from WS-{slip_id}"
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@require_POST
def release_withdrawal_slip_item_ajax(request, item_id):
    try:
        data = json.loads(request.body)
        release_qty = float(data.get('quantity', 0))
        remarks = data.get('remarks', '')
        
        item = get_object_or_404(WithdrawalSlipItem, id=item_id)
        
        if release_qty <= 0:
            return JsonResponse({'success': False, 'message': 'Quantity must be greater than 0.'})
            
        # Inventory Sync
        if item.inventory_item:
            inv = item.inventory_item
            inv.total_withdrawal = (inv.total_withdrawal or 0) + release_qty
            inv.total_balance = (inv.total_balance or 0) - release_qty
            inv.is_negative = 'yes' if inv.total_balance < 0 else 'no'
            inv.datetime_updated = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            inv.save()
            
            InventoryLog.objects.create(
                inventory_item=inv,
                user=request.user.username if request.user.is_authenticated else 'Stephen',
                transaction_type='withdrawal',
                quantity=str(release_qty),
                notes=f"Released via WS-{item.withdrawal_slip.id}. {remarks}"
            )
            
        if item.jop_material:
            jop_mat = item.jop_material
            jop_mat.quantity_released = (jop_mat.quantity_released or 0) + release_qty
            jop_mat.save()
            
        item.quantity_approved = (item.quantity_approved or 0) + release_qty
        item.remarks = remarks
        item.released_by = request.user.username if request.user.is_authenticated else 'Stephen'
        item.save()
        
        ActivityLog.objects.create(
            user=request.user.username if request.user.is_authenticated else 'Stephen',
            action="released",
            entity_type='WithdrawalSlip',
            entity_id=item.withdrawal_slip.id,
            description=f"Released {release_qty} for {item.item_name} in WS-{item.withdrawal_slip.id}"
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@require_POST
def complete_withdrawal_slip_ajax(request, slip_id):
    try:
        slip = get_object_or_404(WithdrawalSlip, id=slip_id)
        slip.status = 'Completed'
        slip.save()
        
        ActivityLog.objects.create(
            user=request.user.username if request.user.is_authenticated else 'Stephen',
            action="status_change",
            entity_type='WithdrawalSlip',
            entity_id=slip.id,
            description=f"Marked WS-{slip.id} as Completed"
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
# --- User Management & RBAC ---

def check_auth_perm(user, perm_name):
    """Helper to check custom AuthAssignment permissions."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.auth_assignments.filter(item__name=perm_name).exists()

@login_required
def user_index_view(request):
    """Main users page with list and sync form."""
    if not check_auth_perm(request.user, 'access-user-management'):
        messages.error(request, "Access Denied: You do not have permission to view User Management.")
        return redirect('dashboard_index')  # Adjust to actual dashboard URL
    
    if request.method == 'POST':
        # Signup logic
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        employee_id = request.POST.get('employee_id')
        dashboard = request.POST.get('dashboard', 'admin')

        if User.objects.filter(username=username).exists():
            messages.error(request, f"User '{username}' already exists.")
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            
            # Create/Update profile
            employee = None
            if employee_id:
                employee = Employee.objects.get(id=employee_id)
            
            UserProfile.objects.get_or_create(user=user, defaults={'dashboard_type': dashboard, 'employee': employee})
            
            log_activity(
                user=request.user.username,
                action="created",
                entity_type="User",
                entity_id=str(user.id),
                description=f"Created new user: {username}"
            )
            messages.success(request, f"User '{username}' created successfully.")
        return redirect('user_index')

    users = User.objects.all().select_related('profile', 'profile__employee').order_by('-date_joined')
    employees = Employee.objects.all().order_by('first_name')
    
    context = {
        'users': users,
        'employees': employees,
        'active_page': 'user_management'
    }
    return render(request, 'user/user_index.html', context)

@login_required
def user_matrix_view(request):
    """Permissions grid for bulk management."""
    if not check_auth_perm(request.user, 'access-user-matrix'):
        messages.error(request, "Access Denied: You do not have permission to view User Access Matrix.")
        return redirect('user_index')
    
    users = User.objects.all().select_related('profile').order_by('username')
    
    # Essential items from production
    essential_items = [
        # Section 1: System Permissions
        ('access-admin', 'Full system administration'),
        ('access-dashboard', 'Access to main dashboard/MyProduction'),
        ('access-all-labor-output', 'View all labor output'),
        ('access-areas-advanced', 'Advanced areas management'),
        ('access-clients', 'Manage clients'),
        ('access-dr', 'Manage Delivery Receipts'),
        ('access-expenses', 'Manage expenses'),
        ('access-inventory', 'Standard inventory access'),
        ('access-inventory-advanced', 'Advanced inventory features'),
        ('access-user-management', 'View Users list'),
        ('access-assignments', 'Manage User Assignments tab'),
        ('access-roles-permissions', 'Manage Roles & Permissions tab'),
        ('access-user-matrix', 'View User Access Matrix grid'),
        ('create-user', 'Permission to create new system users'),
        ('update-user', 'Permission to edit user details and passwords'),
        ('toggle-user-status', 'Permission to activate/deactivate accounts'),
        ('manage-assignments', 'Permission to toggle specific granular assignments'),
        ('access-job-orders', 'Standard Job Orders access'),
        ('access-job-orders-advanced', 'Advanced Job Orders features'),
        ('access-job-orders-void', 'Void Job Orders'),
        ('access-payments', 'Manage payments'),
        ('access-payments-advanced', 'Advanced payment features'),
        ('access-po', 'Manage Purchase Orders'),
        ('access-po-advanced', 'Advanced PO features'),
        ('access-pr', 'Manage Purchase Requests'),
        ('access-production', 'Production management'),
        ('access-products', 'Manage products'),
        ('access-prototype', 'Prototype management'),
        ('access-quick-counts', 'Quick inventory counts'),
        ('access-releasing', 'Product releasing'),
        ('access-reports', 'View system reports'),
        ('access-settings', 'System settings'),
        ('access-user-management', 'Manage system users and RBAC'),
        ('access-withdrawal-slips', 'Manage withdrawal slips'),
        ('access-inventory-logs', 'Access to system inventory logs'),
        ('access-employees', 'Access to employee information'),
        
        # Section: Production Roles / Services
        ('Production Head', 'Production oversight'),
        ('Layout Artist A', 'Design and layout A'),
        ('Layout Artist B', 'Design and layout B'),
        ('Packaging', 'Packaging operations'),
        ('Invitation', 'Invitation specialty'),
        ('Customization', 'Product customization'),
        ('Assembly', 'Product assembly'),
        ('Marketing', 'Marketing and sales'),
        ('Releasing', 'Product releasing role'),
        ('Photobooth', 'Photobooth operations'),
        ('Job Out Printing', 'External printing management'),
    ]
    for name, desc in essential_items:
        AuthItem.objects.get_or_create(name=name, defaults={'description': desc, 'type': 0})

    auth_items = AuthItem.objects.all().order_by('name')
    
    # Explicit Grouping to match "Section 1" and "Section" labels
    section1_names = [
        'access-admin', 'access-all-labor-output', 'access-areas-advanced', 
        'access-clients', 'access-dr', 'access-expenses', 'access-inventory', 
        'access-inventory-advanced', 'access-job-orders', 'access-job-orders-advanced', 
        'access-job-orders-void', 'access-payments', 'access-payments-advanced', 
        'access-po', 'access-po-advanced', 'access-pr', 'access-production', 
        'access-products', 'access-prototype', 'access-quick-counts', 
        'access-releasing', 'access-reports', 'access-settings', 'access-inventory-logs', 'access-employees',
        'access-user-management', 'access-withdrawal-slips'
    ]
    
    section_names = [
        'Production Head', 'Layout Artist A', 'Packaging', 'Invitation', 
        'Customization', 'Assembly', 'Marketing', 'Releasing', 
        'Photobooth', 'Layout Artist B', 'Job Out Printing'
    ]
    
    system_permissions = AuthItem.objects.filter(name__in=section1_names).order_by('name')
    role_permissions = AuthItem.objects.filter(name__in=section_names).order_by('name')
    
    # Pre-fetch assignments
    assignments = AuthAssignment.objects.all()
    matrix_data = {} # {user_id: [item_ids]}
    for ass in assignments:
        if ass.user_id not in matrix_data:
            matrix_data[ass.user_id] = set()
        matrix_data[ass.user_id].add(ass.item_id)

    context = {
        'system_permissions': system_permissions,
        'role_permissions': role_permissions,
        'users': users,
        'matrix_data': matrix_data,
        'active_page': 'user_management_matrix'
    }
    return render(request, 'user/user_matrix.html', context)

@login_required
def auth_assignment_view(request):
    """Individual user assignment page."""
    if not check_auth_perm(request.user, 'access-assignments'):
        messages.error(request, "Access Denied: You do not have permission to manage User Assignments.")
        return redirect('user_index')
    
    user_id = request.GET.get('user_id')
    selected_user = None
    user_permissions = set()
    
    if user_id:
        selected_user = get_object_or_404(User, id=user_id)
        user_permissions = set(AuthAssignment.objects.filter(user=selected_user).values_list('item_id', flat=True))

    users = User.objects.all().order_by('username')
    auth_items = AuthItem.objects.all().order_by('name')
    employees = Employee.objects.all().order_by('first_name')

    context = {
        'users': users,
        'selected_user': selected_user,
        'auth_items': auth_items,
        'user_permissions': user_permissions,
        'employees': employees,
        'active_page': 'user_management_assignment'
    }
    return render(request, 'user/auth_assignment.html', context)

@login_required
def auth_item_view(request):
    """Manage roles and permissions dictionary."""
    if not check_auth_perm(request.user, 'access-roles-permissions'):
        messages.error(request, "Access Denied: You do not have permission to manage Roles & Permissions.")
        return redirect('user_index')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        item_type = request.POST.get('type', 0)
        desc = request.POST.get('description', '')
        
        item, created = AuthItem.objects.get_or_create(
            name=name, 
            defaults={'type': item_type, 'description': desc}
        )
        if created:
            messages.success(request, f"Permission '{name}' created.")
        else:
            messages.info(request, f"Permission '{name}' already exists.")
        return redirect('auth_item')

    items = AuthItem.objects.all().order_by('name')
    context = {
        'items': items,
        'active_page': 'user_management_items'
    }
    return render(request, 'user/auth_item.html', context)

@csrf_exempt
@require_POST
def api_toggle_auth_item(request):
    """AJAX toggle for AuthAssignment."""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        item_id = data.get('item_id')
        
        user = User.objects.get(id=user_id)
        item = AuthItem.objects.get(id=item_id)
        
        assignment, created = AuthAssignment.objects.get_or_create(user=user, item=item)
        if not created:
            assignment.delete()
            status = 'removed'
        else:
            status = 'assigned'
            
        log_activity(
            user=request.user.username,
            action="updated",
            entity_type="AuthAssignment",
            entity_id=user.id,
            description=f"{status.capitalize()} permission '{item.name}' for user '{user.username}'"
        )
        return JsonResponse({'status': 'success', 'assignment_status': status})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@require_POST
def api_update_user(request):
    """Update user details and profile."""
    if not check_auth_perm(request.user, 'update-user'):
         return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        user = get_object_or_404(User, id=user_id)
        
        user.username = data.get('username', user.username)
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        
        # Update password if provided
        password = data.get('password')
        if password:
            user.set_password(password)
            
        user.save()
        
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.dashboard_type = data.get('dashboard', profile.dashboard_type)
        profile.save()
        
        log_activity(request.user, f"Updated user profile: {user.username}")
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@require_POST
def api_toggle_user_status(request):
    """AJAX toggle for user.is_active."""
    if not check_auth_perm(request.user, 'toggle-user-status'):
         return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
         
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        user = User.objects.get(id=user_id)
        
        user.is_active = not user.is_active
        user.save()
        
        log_activity(
            user=request.user.username,
            action="updated",
            entity_type="User",
            entity_id=user.id,
            description=f"Toggled status for user '{user.username}' to {'Active' if user.is_active else 'Inactive'}"
        )
        return JsonResponse({'status': 'success', 'is_active': user.is_active})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@require_POST
def api_link_user_employee(request):
    """AJAX link User to Employee profile."""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        employee_id = data.get('employee_id')
        
        user = User.objects.get(id=user_id)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        
        if employee_id:
            employee = Employee.objects.get(id=employee_id)
            profile.employee = employee
            msg = f"Linked user '{user.username}' to employee '{employee.full_name}'"
        else:
            profile.employee = None
            msg = f"Unlinked employee from user '{user.username}'"
            
        profile.save()
        
        log_activity(
            user=request.user.username,
            action="updated",
            entity_type="User",
            entity_id=user.id,
            description=msg
        )
        return JsonResponse({'status': 'success', 'message': msg})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@require_POST
def api_delete_auth_item(request):
    """AJAX delete AuthItem."""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        item = AuthItem.objects.get(id=item_id)
        
        # Security: Don't delete essentials
        if item.name in ['access-admin', 'access-user-management']:
            return JsonResponse({'status': 'error', 'message': 'Cannot delete essential system permissions.'})
            
        item_name = item.name
        item.delete()
        
        log_activity(
            user=request.user.username if request.user.is_authenticated else 'Stephen',
            action="deleted",
            entity_type="AuthItem",
            entity_id=item_id,
            description=f"Deleted RBAC item: {item_name}"
        )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
