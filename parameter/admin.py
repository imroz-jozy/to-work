from django.contrib import admin
from django.db import models
from django.db.models import Sum, Count
from django.utils.html import format_html
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from rangefilter.filters import DateRangeFilter
import csv
import datetime
from core.models import Master1, ItemParamDet
from .models import StockReportView, ParameterStockView, BCNStockSummary

class DateRangeFilter(admin.SimpleListFilter):
    title = 'Date Range'
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('this_year', 'This Year'),
            ('custom', 'Custom Range'),
        )
    
    def queryset(self, request, queryset):
        # This filter doesn't modify the queryset directly
        # It's used by the admin view to filter stock calculations
        return queryset


@admin.register(BCNStockSummary)
class BCNStockSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'bcn', 'item_code', 'item_name', 'parameters',
        'display_opening_stock', 'display_closing_stock', 'display_movement', 'display_stock_status'
    )
    search_fields = ('bcn', 'item_code', 'item_name', 'parameters')
    list_filter = (DateRangeFilter,)
    ordering = ('bcn',)
    list_per_page = 50
    actions = ['export_bcn_stock_csv']
    
    def has_add_permission(self, request):
        return False
        
    def has_change_permission(self, request, obj=None):
        return False
        
    def has_delete_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        # Get date range from request if available
        start_date = getattr(request, 'start_date', None)
        end_date = getattr(request, 'end_date', None)
        
        # Generate the queryset using our custom method
        return BCNStockSummary.get_queryset(start_date, end_date)
    
    def display_opening_stock(self, obj):
        """Display opening stock with formatting"""
        if obj.opening_stock > 0:
            return format_html('<span style="color: green;">{:.2f}</span>', obj.opening_stock)
        elif obj.opening_stock < 0:
            return format_html('<span style="color: red;">{:.2f}</span>', obj.opening_stock)
        else:
            return format_html('<span style="color: gray;">0.00</span>')
    display_opening_stock.short_description = "Opening Stock"
    
    def display_closing_stock(self, obj):
        """Display closing stock with formatting"""
        if obj.closing_stock > 0:
            return format_html('<span style="color: green;">{:.2f}</span>', obj.closing_stock)
        elif obj.closing_stock < 0:
            return format_html('<span style="color: red;">{:.2f}</span>', obj.closing_stock)
        else:
            return format_html('<span style="color: gray;">0.00</span>')
    display_closing_stock.short_description = "Closing Stock"
    
    def display_movement(self, obj):
        """Display movement with arrow indicators"""
        if obj.movement > 0:
            return format_html('<span style="color: green;">↑ {:.2f}</span>', obj.movement)
        elif obj.movement < 0:
            return format_html('<span style="color: red;">↓ {:.2f}</span>', abs(obj.movement))
        else:
            return format_html('<span style="color: gray;">0.00</span>')
    display_movement.short_description = "Movement"
    
    def display_stock_status(self, obj):
        """Display stock status indicator"""
        if obj.closing_stock > 0:
            return format_html('<span style="color: green; font-weight: bold;">✓ In Stock</span>')
        elif obj.closing_stock == 0:
            return format_html('<span style="color: orange; font-weight: bold;">⚠ Out of Stock</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">❌ Negative Stock</span>')
    display_stock_status.short_description = "Stock Status"
    
    def export_bcn_stock_csv(self, request, queryset):
        """Export selected BCN stock items to CSV"""
        response = HttpResponse(content_type='text/csv')
        
        # Get date range for filename
        start_date = getattr(request, 'start_date', None)
        end_date = getattr(request, 'end_date', None)
        
        # Create filename with date range if available
        if start_date and end_date:
            filename = f"bcn_stock_report_{start_date}_to_{end_date}.csv"
        else:
            filename = f"bcn_stock_report_{timezone.now().strftime('%Y%m%d')}.csv"
            
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['BCN', 'Item Code', 'Item Name', 'Parameters', 'Opening Stock', 'Closing Stock', 'Movement', 'Stock Status'])
        
        for obj in queryset:
            try:
                # Determine stock status
                if obj.closing_stock > 0:
                    stock_status = "In Stock"
                elif obj.closing_stock == 0:
                    stock_status = "Out of Stock"
                else:
                    stock_status = "Negative Stock"
                    
                writer.writerow([
                    obj.bcn,
                    obj.item_code,
                    obj.item_name,
                    obj.parameters,
                    f"{obj.opening_stock:.2f}",
                    f"{obj.closing_stock:.2f}",
                    f"{obj.movement:.2f}",
                    stock_status
                ])
            except Exception as e:
                # If any error occurs, use safe defaults
                writer.writerow([
                    obj.bcn or "N/A",
                    "N/A",
                    "N/A",
                    "N/A",
                    "0.00",
                    "0.00",
                    "0.00",
                    "❓ Error"
                ])
        
        self.message_user(request, f"Exported {queryset.count()} BCN stock items to CSV", messages.SUCCESS)
        return response
    
    export_bcn_stock_csv.short_description = "📊 Export selected to CSV"
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist view to add summary statistics"""
        response = super().changelist_view(request, extra_context=extra_context)
        
        # Only add summary if the response has a context_data attribute
        if hasattr(response, 'context_data'):
            queryset = self.get_queryset(request)
            
            # Calculate summary statistics
            total_items = len(queryset)
            positive_stock = sum(1 for item in queryset if item.closing_stock > 0)
            zero_stock = sum(1 for item in queryset if item.closing_stock == 0)
            negative_stock = sum(1 for item in queryset if item.closing_stock < 0)
            
            # Get date range for display
            start_date = getattr(request, 'start_date', None)
            end_date = getattr(request, 'end_date', None)
            date_range_display = ""
            if start_date and end_date:
                if start_date == end_date:
                    date_range_display = f"for {start_date}"
                else:
                    date_range_display = f"from {start_date} to {end_date}"
            
            # Add summary to context
            response.context_data['summary'] = {
                'total_items': total_items,
                'positive_stock': positive_stock,
                'zero_stock': zero_stock,
                'negative_stock': negative_stock,
                'date_range': date_range_display
            }
            
        return response

@admin.register(StockReportView)
class StockReportAdmin(admin.ModelAdmin):
    list_display = (
        'Code', 'Name', 'display_opening_stock', 
        'display_closing_stock', 'display_movement', 'display_stock_status'
    )
    search_fields = ('Code', 'Name')
    list_filter = ('MasterType', DateRangeFilter)
    ordering = ('Code',)
    actions = ['export_stock_csv']
    
    # Store date range in admin class
    start_date = None
    end_date = None
    
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

    def get_date_range(self, request):
        """Get date range from request or session"""
        from datetime import datetime, timedelta, date
        import calendar
        
        # Check if date range is in request
        date_range = request.GET.get('date_range')
        
        # If custom range is selected, get start and end dates from request
        if date_range == 'custom':
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            
            if start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    return start_date, end_date
                except ValueError:
                    pass
        
        # Calculate date range based on selection
        today = date.today()
        
        if date_range == 'today':
            return today, today
        elif date_range == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif date_range == 'this_week':
            start_of_week = today - timedelta(days=today.weekday())
            return start_of_week, today
        elif date_range == 'last_week':
            start_of_last_week = today - timedelta(days=today.weekday() + 7)
            end_of_last_week = start_of_last_week + timedelta(days=6)
            return start_of_last_week, end_of_last_week
        elif date_range == 'this_month':
            start_of_month = date(today.year, today.month, 1)
            return start_of_month, today
        elif date_range == 'last_month':
            if today.month == 1:
                last_month = 12
                last_month_year = today.year - 1
            else:
                last_month = today.month - 1
                last_month_year = today.year
            
            start_of_last_month = date(last_month_year, last_month, 1)
            last_day_of_last_month = calendar.monthrange(last_month_year, last_month)[1]
            end_of_last_month = date(last_month_year, last_month, last_day_of_last_month)
            
            return start_of_last_month, end_of_last_month
        elif date_range == 'this_year':
            start_of_year = date(today.year, 1, 1)
            return start_of_year, today
        
        # Default: no date filtering
        return None, None
    
    def changelist_view(self, request, extra_context=None):
        """Add date range to changelist view"""
        # Get date range
        self.start_date, self.end_date = self.get_date_range(request)
        
        # Add date range to context
        extra_context = extra_context or {}
        if self.start_date and self.end_date:
            extra_context['date_range'] = {
                'start_date': self.start_date,
                'end_date': self.end_date,
            }
        
        return super().changelist_view(request, extra_context)
    
    def display_opening_stock(self, obj):
        """Display opening stock with formatting including voucher type 1"""
        try:
            opening_stock = obj.get_opening_stock(self.start_date, self.end_date)
            return "{:.2f}".format(opening_stock)
        except (ValueError, TypeError, Exception):
            return "0.00"
    display_opening_stock.short_description = "Opening Stock"
    display_opening_stock.admin_order_field = 'Code'

    def display_closing_stock(self, obj):
        """Display closing stock with formatting"""
        try:
            stock_value = obj.get_closing_stock(self.start_date, self.end_date)
            
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
            return format_html('<span style="color: gray;">0.00</span>')
    display_closing_stock.short_description = "Closing Stock"

    def display_movement(self, obj):
        """Display movement with color coding (excluding opening stock)"""
        try:
            movement_value = obj.get_movement(self.start_date, self.end_date)
            
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
                '<span style="color: {};"> {} {:.2f}</span>',
                color, arrow, movement_value
            )
        except (ValueError, TypeError, Exception):
            return format_html('<span style="color: gray;">→ 0.00</span>')
    display_movement.short_description = "Movement"

    def display_stock_status(self, obj):
        """Display stock status"""
        return obj.get_stock_status(self.start_date, self.end_date)
    display_stock_status.short_description = "Status"

    def export_stock_csv(self, request, queryset):
        """Export selected items to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="stock_report.csv"'
        
        # Get date range for export
        start_date, end_date = self.get_date_range(request)
        
        # Add date range to filename if applicable
        if start_date and end_date:
            filename = f"stock_report_{start_date}_to_{end_date}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        header = ['Item Code', 'Item Name', 'Opening Stock', 'Closing Stock', 'Movement', 'Status']
        
        # Add date range to header if applicable
        if start_date and end_date:
            date_range_str = f"Date Range: {start_date} to {end_date}"
            writer.writerow([date_range_str])
        
        writer.writerow(header)
        
        for obj in queryset:
            try:
                opening_stock = obj.get_opening_stock(start_date, end_date)
                closing_stock = obj.get_closing_stock(start_date, end_date)
                movement = obj.get_movement(start_date, end_date)
                
                writer.writerow([
                    obj.Code,
                    obj.Name,
                    f"{opening_stock:.2f}",
                    f"{closing_stock:.2f}",
                    f"{movement:.2f}",
                    obj.get_stock_status(start_date, end_date)
                ])
            except (ValueError, TypeError, Exception) as e:
                # If any error occurs, use safe defaults
                writer.writerow([
                    obj.Code or "N/A",
                    obj.Name or "N/A",
                    "0.00",
                    "0.00",
                    "0.00",
                    "❓ Error"
                ])
        
        self.message_user(request, f"Exported {queryset.count()} items to CSV", messages.SUCCESS)
        return response
    
    export_stock_csv.short_description = "📊 Export selected to CSV"

    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to changelist"""
        total_items = self.get_queryset(request).count()
        
        # Calculate stock status counts
        positive_stock_count = 0
        zero_stock_count = 0
        negative_stock_count = 0
        
        for item in self.get_queryset(request):
            try:
                stock_value = item.get_closing_stock()
                
                if stock_value > 0:
                    positive_stock_count += 1
                elif stock_value == 0:
                    zero_stock_count += 1
                else:
                    negative_stock_count += 1
            except (ValueError, TypeError, Exception):
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
        'display_value', 'Date', 'VchNo', 'BCN', 'display_vch_type'
    )
    search_fields = ('ItemCode__Code', 'ItemCode__Name', 'C1', 'C2', 'C3', 'C4', 'C5', 'VchNo', 'BCN')
    list_filter = ('Date', 'VchType', 'ItemCode__Code', 'C1', 'C2', 'BCN')
    ordering = ('ItemCode__Code', '-Date', '-Value1')
    date_hierarchy = 'Date'
    list_per_page = 50
    actions = ['export_parameter_stock_csv']
    
    def get_queryset(self, request):
        """Get all parameter stock details with related data"""
        return super().get_queryset(request).select_related('ItemCode')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

    def get_item_code(self, obj):
        """Get item code from related Master1"""
        return obj.get_item_code_display()
    get_item_code.short_description = "Item Code"
    get_item_code.admin_order_field = 'ItemCode__Code'

    def get_item_name(self, obj):
        """Get item name from related Master1"""
        return obj.get_item_name_display()
    get_item_name.short_description = "Item Name"
    get_item_name.admin_order_field = 'ItemCode__Name'

    def display_value(self, obj):
        """Display Value1 with formatting"""
        try:
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
            return format_html('<span style="color: gray;">0.00</span>')
    
    display_value.short_description = "Quantity"
    display_value.admin_order_field = 'Value1'

    def get_parameter_string(self, obj):
        """Get parameter string combination"""
        params = obj.get_parameter_string()
        if obj.BCN and obj.BCN.strip():
            return format_html('<span title="BCN: {}"><strong>{}</strong></span>', obj.BCN, params)
        return params
    get_parameter_string.short_description = "Parameters"

    def display_vch_type(self, obj):
        """Display voucher type with description"""
        vch_type_map = {
            1: "Opening",
            2: "Receipt", 
            3: "Issue",
            4: "Transfer In",
            5: "Transfer Out",
            6: "Adjustment",
            9: "Sale",
            # Add more mappings as needed
        }
        
        vch_type = getattr(obj, 'VchType', None)
        if vch_type:
            description = vch_type_map.get(vch_type, f"Type {vch_type}")
            
            # Color code by voucher type
            if vch_type == 1:  # Opening
                color = "blue"
            elif vch_type == 2:  # Receipt/Purchase
                color = "green"
            elif vch_type in [3, 5, 9]:  # Issue/Transfer Out/Sale
                color = "red"
            elif vch_type == 4:  # Transfer In
                color = "purple"
            else:
                color = "gray"
                
            return format_html(
                '<span title="Voucher Type {}" style="color: {}; font-weight: bold;">{}</span>',
                vch_type, color, description
            )
        return "N/A"
    
    display_vch_type.short_description = "Voucher Type"
    display_vch_type.admin_order_field = 'VchType'
    
    def export_parameter_stock_csv(self, request, queryset):
        """Export selected parameter stock items to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="parameter_stock_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Item Code', 'Item Name', 'Parameters', 'BCN', 'Quantity', 'Date', 'Voucher No', 'Voucher Type'])
        
        vch_type_map = {
            1: "Opening",
            2: "Receipt", 
            3: "Issue",
            4: "Transfer In",
            5: "Transfer Out",
            6: "Adjustment",
            9: "Sale",
        }
        
        for obj in queryset:
            try:
                # Get voucher type description
                vch_type = getattr(obj, 'VchType', None)
                vch_description = vch_type_map.get(vch_type, f"Type {vch_type}") if vch_type else "N/A"
                
                writer.writerow([
                    obj.get_item_code_display(),
                    obj.get_item_name_display(),
                    obj.get_parameter_string(),
                    obj.BCN or "",
                    f"{obj.Value1:.2f}",
                    obj.Date,
                    obj.VchNo,
                    vch_description
                ])
            except Exception as e:
                # If any error occurs, use safe defaults
                writer.writerow([
                    "N/A",
                    "N/A",
                    "N/A",
                    "N/A",
                    "0.00",
                    "N/A",
                    "N/A",
                    "❓ Error"
                ])
        
        self.message_user(request, f"Exported {queryset.count()} parameter stock items to CSV", messages.SUCCESS)
        return response
    
    export_parameter_stock_csv.short_description = "📊 Export selected to CSV"