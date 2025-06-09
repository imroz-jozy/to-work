# Add this to a new file: utils.py or add to your existing utils

from .models import Master1, ItemParamDet
from django.db.models import Sum

def get_item_parameter_stock(item_code):
    """
    Get parameter-wise closing stock for a specific item by code
    
    Args:
        item_code (str): The item code to lookup
        
    Returns:
        dict: Contains item details and parameter-wise stock data
    """
    try:
        item = Master1.objects.get(Code=item_code)
        parameter_stock = item.parameter_wise_closing_stock()
        
        return {
            'success': True,
            'item': {
                'code': item.Code,
                'name': item.Name,
                'master_type': item.MasterType,
                'total_closing_stock': item.closing_stock()
            },
            'parameter_stock': parameter_stock
        }
    except Master1.DoesNotExist:
        return {
            'success': False,
            'error': f'Item with code {item_code} not found'
        }

def get_all_items_with_stock():
    """
    Get a summary of all items with their closing stock
    
    Returns:
        list: List of items with basic stock information
    """
    items = Master1.objects.all()
    result = []
    
    for item in items:
        result.append({
            'code': item.Code,
            'name': item.Name,
            'master_type': item.MasterType,
            'closing_stock': item.closing_stock(),
            'has_parameters': item.itemparamdet_set.exclude(
                C1='', C2='', C3='', C4='', C5=''
            ).exists()
        })
    
    return result

def get_low_stock_items(threshold=0):
    """
    Get items with closing stock below threshold
    
    Args:
        threshold (float): Stock threshold (default: 0)
        
    Returns:
        list: Items with stock below threshold
    """
    items = Master1.objects.all()
    low_stock_items = []
    
    for item in items:
        closing_stock = item.closing_stock()
        if closing_stock <= threshold:
            low_stock_items.append({
                'code': item.Code,
                'name': item.Name,
                'closing_stock': closing_stock
            })
    
    return sorted(low_stock_items, key=lambda x: x['closing_stock'])

# Example usage:
"""
# Get parameter-wise stock for a specific item
stock_data = get_item_parameter_stock('ITEM001')
if stock_data['success']:
    print(f"Item: {stock_data['item']['name']}")
    print(f"Total Stock: {stock_data['item']['total_closing_stock']}")
    
    for param_stock in stock_data['parameter_stock']:
        print(f"Parameters: C1={param_stock['C1']}, C2={param_stock['C2']}")
        print(f"Closing Stock: {param_stock['closing_stock']}")

# Get all items with stock summary
all_items = get_all_items_with_stock()
for item in all_items:
    print(f"{item['code']}: {item['closing_stock']} units")

# Get low stock items
low_stock = get_low_stock_items(threshold=10)
for item in low_stock:
    print(f"Low stock: {item['code']} - {item['closing_stock']} units")
"""