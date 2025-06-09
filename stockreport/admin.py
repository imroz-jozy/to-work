from django.contrib import admin
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse
from django.contrib import messages
from django.shortcuts import render, get_object_or_404
from django.utils.html import format_html
from .models import Master1, ItemParamDet, APIConfig
import requests
import xml.etree.ElementTree as ET

def execute_query(query_type='itemparamdet'):
    # Get the active API configuration
    api_config = APIConfig.get_active_config()
    if not api_config:
        raise ValueError("No active API configuration found")
    
    # Define queries based on type
    queries = {
        'itemparamdet': "SELECT Date, VchType, VchNo, ItemCode, C1, C2, C3, C4, C5, BCN, Value1 FROM itemParamDet",
        'master1': "SELECT Code, MasterType, Name FROM Master1 WHERE MasterType = 6"
    }
    
    headers = {
        "SC": "1",
        "Qry": queries[query_type],
        "UserName": api_config.username,
        "Pwd": api_config.password
    }
    
    # Try both GET and POST methods
    methods_to_try = ['GET', 'POST']
    for method in methods_to_try:
        try:
            if method == 'GET':
                response = requests.get(api_config.url, headers=headers)
            else:
                response = requests.post(api_config.url, headers=headers)
            
            if response.status_code == 200:
                return response.text
        except requests.RequestException:
            continue
    
    return None

def parse_xml_to_list(xml_data, query_type='itemparamdet'):
    try:
        namespaces = {'z': '#RowsetSchema'}
        root = ET.fromstring(xml_data)
        result = []
        
        for row in root.findall(".//z:row", namespaces=namespaces):
            if query_type == 'itemparamdet':
                entry = {
                    "Date": row.attrib.get("Date", ""),
                    "VchType": row.attrib.get("VchType", ""),
                    "VchNo": row.attrib.get("VchNo", ""),
                    "ItemCode": row.attrib.get("ItemCode", ""),
                    "C1": row.attrib.get("C1", ""),
                    "C2": row.attrib.get("C2", ""),
                    "C3": row.attrib.get("C3", ""),
                    "C4": row.attrib.get("C4", ""),
                    "C5": row.attrib.get("C5", ""),
                    "BCN": row.attrib.get("BCN", ""),
                    "Value1": float(row.attrib.get("Value1", 0)) if row.attrib.get("Value1") else 0
                }
            else:  # master1 query
                entry = {
                    "Code": row.attrib.get("Code", ""),
                    "MasterType": row.attrib.get("MasterType", ""),
                    "Name": row.attrib.get("Name", "")
                }
            result.append(entry)
        
        return result
        
    except ET.ParseError as e:
        return []

class ItemParamDetInline(admin.TabularInline):
    model = ItemParamDet
    extra = 1
    fields = ('Date', 'VchType', 'VchNo', 'C1', 'C2', 'C3', 'C4', 'C5', 'BCN', 'Value1')
    readonly_fields = ('Date', 'VchType', 'VchNo', 'BCN', 'Value1')

@admin.register(Master1)
class Master1Admin(admin.ModelAdmin):
    list_display = ('Code', 'Name', 'MasterType', 'closing_stock', 'view_parameter_stock')
    search_fields = ('Name',)
    list_filter = ('MasterType',)
    inlines = [ItemParamDetInline]
    change_list_template = "admin/master1_changelist.html"
    
    def view_parameter_stock(self, obj):
        """Display a link to view parameter-wise stock details"""
        url = reverse('admin:view_parameter_stock', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">View Details</a>', url)
    view_parameter_stock.short_description = 'Parameter Stock'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-data/', self.import_data_view, name='master1_import_data'),
            path('<int:item_id>/parameter-stock/', self.parameter_stock_view, name='view_parameter_stock'),
            path('<int:item_id>/parameter-stock-json/', self.parameter_stock_json, name='parameter_stock_json'),
            path('autocomplete/', self.autocomplete_view, name='master1_autocomplete'),
        ]
        return custom_urls + urls
    
    def parameter_stock_view(self, request, item_id):
        """Display parameter-wise stock details for a specific item"""
        item = get_object_or_404(Master1, pk=item_id)
        parameter_stock, total_qty = item.parameter_wise_closing_stock()
        
        context = {
            'title': f'Parameter-wise Stock for {item.Code} - {item.Name}',
            'item': item,
            'parameter_stock': parameter_stock,
            'total_stock': total_qty,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/parameter_stock_detail.html', context)
    
    def parameter_stock_json(self, request, item_id):
        """Return parameter-wise stock data as JSON"""
        item = get_object_or_404(Master1, pk=item_id)
        parameter_stock, total_qty = item.parameter_wise_closing_stock()
        
        return JsonResponse({
            'item_code': item.Code,
            'item_name': item.Name,
            'total_stock': total_qty,
            'parameter_stock': parameter_stock
        })
    
    def import_data_view(self, request):
        if request.method == 'POST':
            try:
                # First import Master1 data
                master_xml_response = execute_query(query_type='master1')
                if not master_xml_response:
                    messages.error(request, "Failed to fetch Master1 data from external source.")
                    return HttpResponseRedirect("../")
                
                # Parse Master1 XML data
                master_parsed_data = parse_xml_to_list(master_xml_response, query_type='master1')
                if not master_parsed_data:
                    messages.error(request, "No Master1 data found or failed to parse XML response.")
                    return HttpResponseRedirect("../")
                
                # Clear existing Master1 data
                old_master1_count = Master1.objects.count()
                Master1.objects.all().delete()
                messages.info(request, f"Cleared {old_master1_count} Master1 records")
                
                # Import Master1 data
                master_imported_count = 0
                for entry in master_parsed_data:
                    try:
                        Master1.objects.create(
                            Code=entry['Code'],
                            Name=entry['Name'],
                            MasterType=entry['MasterType']
                        )
                        master_imported_count += 1
                    except Exception as e:
                        messages.warning(request, f"Error importing Master1 record: {str(e)}")
                
                messages.success(request, f"Successfully imported {master_imported_count} Master1 records")
                
                # Now import ItemParamDet data
                xml_response = execute_query(query_type='itemparamdet')
                if not xml_response:
                    messages.error(request, "Failed to fetch ItemParamDet data from external source.")
                    return HttpResponseRedirect("../")
                
                parsed_data = parse_xml_to_list(xml_response, query_type='itemparamdet')
                if not parsed_data:
                    messages.error(request, "No ItemParamDet data found or failed to parse XML response.")
                    return HttpResponseRedirect("../")
                
                # Clear existing ItemParamDet data
                old_itemparamdet_count = ItemParamDet.objects.count()
                ItemParamDet.objects.all().delete()
                messages.info(request, f"Cleared {old_itemparamdet_count} ItemParamDet records")
                
                # Import ItemParamDet data
                imported_count = 0
                error_count = 0
                
                for entry in parsed_data:
                    try:
                        # Get or create Master1 record
                        item, created = Master1.objects.get_or_create(
                            Code=entry['ItemCode'],
                            defaults={
                                'Name': f"Item {entry['ItemCode']}",
                                'MasterType': 'ITEM'
                            }
                        )
                        
                        # Create ItemParamDet record
                        ItemParamDet.objects.create(
                            Date=entry['Date'],
                            VchType=entry['VchType'],
                            VchNo=entry['VchNo'],
                            Item=item,
                            C1=entry['C1'],
                            C2=entry['C2'],
                            C3=entry['C3'],
                            C4=entry['C4'],
                            C5=entry['C5'],
                            BCN=entry['BCN'],
                            Value1=entry['Value1']
                        )
                        
                        imported_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        messages.warning(request, f"Error importing ItemParamDet record: {str(e)}")
                
                messages.success(request, f"Successfully imported {imported_count} ItemParamDet records")
                    
                if error_count > 0:
                    messages.warning(request, f"{error_count} ItemParamDet records had errors during import.")
                    
            except Exception as e:
                messages.error(request, f"Import failed: {str(e)}")
            
            return HttpResponseRedirect("../")
        
        # GET request - show confirmation page
        return render(request, 'admin/import_data_confirm.html', {
            'title': 'Import Data from External Source',
            'opts': self.model._meta,
        })

    def autocomplete_view(self, request):
        term = request.GET.get('term', '')
        if term:
            items = Master1.objects.filter(Name__icontains=term)[:10]
            results = [{'id': item.id, 'text': item.Name} for item in items]
        else:
            results = []
        return JsonResponse({'results': results})

@admin.register(ItemParamDet)
class ItemParamDetAdmin(admin.ModelAdmin):
    list_display = ('Date', 'VchType', 'VchNo', 'Item', 'get_parameter_string', 'BCN', 'Value1')
    search_fields = ('VchNo', 'Item__Code', 'Item__Name', 'BCN', 'C1', 'C2', 'C3', 'C4', 'C5')
    list_filter = ('VchType', 'Date', 'C1', 'C2')
    
    change_list_template = "admin/itemparamdet_changelist.html"
    
    def get_parameter_string(self, obj):
        return obj.get_parameter_string()
    get_parameter_string.short_description = 'Parameters'
    
@admin.register(APIConfig)
class APIConfigAdmin(admin.ModelAdmin):
    list_display = ('url', 'username', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('url', 'username')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('API Configuration', {
            'fields': ('url', 'username', 'password', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # If this config is being set as active, deactivate all others
        if obj.is_active:
            APIConfig.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)
    