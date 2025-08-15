# parameter/admin.py
from django.contrib import admin
from django.db import models
from django.db.models import Sum, Count
from django.utils.html import format_html
from django.contrib import messages
from core.models import Master1, ItemParamDet
from .models import StockReportView, ParameterStockView

@admin.register(StockReportView)
class StockReportAdmin(admin.ModelAdmin):
    list_display = (
        'Code', 'Name', 'display_opening_stock', 
        'display_closing_stock', 'display_movement', 'display_stock_status'
    )
    search_fields = ('Code', 'Name')
    list_filter = ('MasterType',)
    ordering = ('Code',)
    actions = ['export_stock_csv']
    
    def get_queryset(self, request):
        """Filter to show only item masters (MasterType = 6)"""
        qs = super().get_queryset(request)
        return qs.filter(MasterType=6)
    
    # Remove add/edit/delete permissions
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

    def display_opening_stock(self, obj):
        """Display opening stock with formatting including voucher type 1"""
        try:
            from core.models import ItemParamDet
            
            # Calculate opening stock including voucher type 1
            opening_stock = ItemParamDet.objects.filter(
                ItemCode__Code=obj.Code,
                VchType=1  # Opening voucher type
            ).aggregate(
                total=models.Sum('Value1')
            )['total'] or 0.0
            
            return "{:.2f}".format(float(opening_stock))
        except (ValueError, TypeError, Exception):
            return "0.00"
    display_opening_stock.short_description = "Opening Stock"
    display_opening_stock.admin_order_field = 'Code'

    def display_closing_stock(self, obj):
        """Display closing stock with formatting"""
        try:
            from core.models import ItemParamDet
            
            # Calculate total stock from all transactions
            closing_stock = ItemParamDet.objects.filter(
                ItemCode__Code=obj.Code
            ).aggregate(
                total=models.Sum('Value1')
            )['total'] or 0.0
            
            stock_value = float(closing_stock)
            
            if stock_value > 0:
                color = "green"
            elif stock_value == 0:
                color = "orange"
            else:
                color = "red"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
                color, stock_value
            )
        except (ValueError, TypeError, Exception):
            return "0.00"
    display_closing_stock.short_description = "Closing Stock"

    def display_movement(self, obj):
        """Display movement with color coding (excluding opening stock)"""
        try:
            from core.models import ItemParamDet
            
            # Calculate movement excluding opening voucher type 1
            movement = ItemParamDet.objects.filter(
                ItemCode__Code=obj.Code
            ).exclude(
                VchType=1  # Exclude opening entries
            ).aggregate(
                total=models.Sum('Value1')
            )['total'] or 0.0
            
            movement_value = float(movement)
            
            if movement_value > 0:
                color = "green"
                arrow = "↗"
            elif movement_value < 0:
                color = "red"
                arrow = "↘"
            else:
                color = "gray"
                arrow = "→"
            
            return format_html(
                '<span style="color: {};">{} {:.2f}</span>',
                color, arrow, movement_value
            )
        except (ValueError, TypeError, Exception):
            return "→ 0.00"
    display_movement.short_description = "Movement"

    def display_stock_status(self, obj):
        """Display stock status"""
        return obj.get_stock_status()
    display_stock_status.short_description = "Status"

    def export_stock_csv(self, request, queryset):
        """Export selected items to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="stock_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Item Code', 'Item Name', 'Opening Stock', 'Closing Stock', 'Movement', 'Status'])
        
        for obj in queryset:
            try:
                # Handle potential SafeString or type conversion issues
                opening_stock = obj.get_opening_stock()
                closing_stock = obj.get_closing_stock()
                movement = obj.get_movement()
                
                opening_value = float(opening_stock) if opening_stock is not None else 0.0
                closing_value = float(closing_stock) if closing_stock is not None else 0.0
                movement_value = float(movement) if movement is not None else 0.0
                
                writer.writerow([
                    obj.Code,
                    obj.Name,
                    opening_value,
                    closing_value,
                    movement_value,
                    obj.get_stock_status()
                ])
            except (ValueError, TypeError):
                # If conversion fails, use string representation
                writer.writerow([
                    obj.Code,
                    obj.Name,
                    str(opening_stock) if opening_stock is not None else "0.00",
                    str(closing_stock) if closing_stock is not None else "0.00",
                    str(movement) if movement is not None else "0.00",
                    obj.get_stock_status()
                ])
        
        self.message_user(request, f"Exported {queryset.count()} items to CSV", messages.SUCCESS)
        return response
    
    export_stock_csv.short_description = "📊 Export selected to CSV"

    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to changelist"""
        # Calculate summary stats
        total_items = self.get_queryset(request).count()
        
        # Get items with stock calculations
        items_with_stock = []
        zero_stock_count = 0
        negative_stock_count = 0
        positive_stock_count = 0
        
        for item in self.get_queryset(request):
            try:
                closing_stock = item.get_closing_stock()
                # Convert to float to handle SafeString or other types
                stock_value = float(closing_stock) if closing_stock is not None else 0.0
                
                if stock_value > 0:
                    positive_stock_count += 1
                elif stock_value == 0:
                    zero_stock_count += 1
                else:
                    negative_stock_count += 1
            except (ValueError, TypeError):
                # If conversion fails, count as zero stock
                zero_stock_count += 1
        
        extra_context = extra_context or {}
        extra_context.update({
            'summary_stats': {
                'total_items': total_items,
                'positive_stock': positive_stock_count,
                'zero_stock': zero_stock_count,
                'negative_stock': negative_stock_count,
            }
        })
        
        return super().changelist_view(request, extra_context)

@admin.register(ParameterStockView)
class ParameterStockAdmin(admin.ModelAdmin):
    list_display = (
        'get_item_code', 'get_item_name', 'get_parameter_string', 
        'display_value', 'Date', 'VchNo'
    )
    search_fields = ('ItemCode__Code', 'ItemCode__Name', 'C1', 'C2', 'C3', 'C4', 'C5')
    list_filter = ('Date', 'ItemCode__Code', 'C1', 'C2')
    ordering = ('ItemCode__Code', '-Value1')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

    def get_item_code(self, obj):
        """Get item code from related Master1"""
        return obj.ItemCode.Code if obj.ItemCode else "N/A"
    get_item_code.short_description = "Item Code"
    get_item_code.admin_order_field = 'ItemCode__Code'

    def get_item_name(self, obj):
        """Get item name from related Master1"""
        return obj.ItemCode.Name if obj.ItemCode else "N/A"
    get_item_name.short_description = "Item Name"
    get_item_name.admin_order_field = 'ItemCode__Name'

    def display_value(self, obj):
        """Display Value1 with formatting"""
        try:
            # Convert Value1 to float to handle any type issues
            value = float(obj.Value1) if obj.Value1 is not None else 0.0
            
            if value > 0:
                color = "green"
            elif value < 0:
                color = "red"
            else:
                color = "gray"
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
                color, value
            )
        except (ValueError, TypeError):
            # If conversion fails, return the raw value
            return str(obj.Value1) if obj.Value1 is not None else "0.00"
    
    display_value.short_description = "Quantity"
    display_value.admin_order_field = 'Value1'

    def get_parameter_string(self, obj):
        """Get parameter string combination"""
        params = []
        for param in [obj.C1, obj.C2, obj.C3, obj.C4, obj.C5]:
            if param:
                params.append(str(param))
        return " | ".join(params) if params else "No Parameters"
    get_parameter_string.short_description = "Parameters"

# parameter/apps.py
from django.apps import AppConfig

class ParameterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parameter'
    verbose_name = "📊 Stock Reports"

# Optional: Create a summary admin for quick overview
class StockSummary:
    """Virtual class for stock summary display"""
    def __init__(self, total_items, positive_stock, zero_stock, negative_stock, total_value):
        self.total_items = total_items
        self.positive_stock = positive_stock
        self.zero_stock = zero_stock
        self.negative_stock = negative_stock
        self.total_value = total_value