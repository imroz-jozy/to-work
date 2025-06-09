from django.db import models
from django.db.models import Sum
from collections import defaultdict

class APIConfig(models.Model):
    url = models.URLField(max_length=200, help_text="API endpoint URL")
    username = models.CharField(max_length=100, help_text="API username")
    password = models.CharField(max_length=100, help_text="API password")
    is_active = models.BooleanField(default=True, help_text="Only one configuration can be active at a time")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "API Configuration"
        verbose_name_plural = "API Configurations"

    def save(self, *args, **kwargs):
        if self.is_active:
            # Set all other configurations to inactive
            APIConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active_config(cls):
        return cls.objects.filter(is_active=True).first()

    def __str__(self):
        return f"API Config ({self.url})"

class Master1(models.Model):
    Code = models.CharField(max_length=20, unique=True)
    MasterType = models.CharField(max_length=10)
    Name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.Code} - {self.Name}"
    
    class Meta:
        verbose_name = "Master Item"
        verbose_name_plural = "Master Items"

    def closing_stock(self):
        """Calculate total closing stock"""
        _, total_qty = self.parameter_wise_closing_stock()
        return total_qty

    def parameter_wise_closing_stock(self):
        """
        Returns parameter-wise closing stock details
        Tracks each BCN number separately
        """
        # Get all transactions for this item
        transactions = self.itemparamdet_set.all().order_by('Date')
        
        # Dictionary to store stock by BCN number
        bcn_stock = {}
        
        for transaction in transactions:
            # Create a key from parameter combination
            param_key = (transaction.C1 or '', transaction.C2 or '', transaction.C3 or '')
            
            if transaction.VchType == '1':  # Opening Balance
                # Initialize BCN entry if not exists
                if transaction.BCN not in bcn_stock:
                    bcn_stock[transaction.BCN] = {
                        'C1': param_key[0],
                        'C2': param_key[1],
                        'C3': param_key[2],
                        'qty': 0
                    }
                
                # Add to stock
                bcn_stock[transaction.BCN]['qty'] += transaction.Value1
                
            elif transaction.VchType == '2':  # Purchase
                # Initialize BCN entry if not exists
                if transaction.BCN not in bcn_stock:
                    bcn_stock[transaction.BCN] = {
                        'C1': param_key[0],
                        'C2': param_key[1],
                        'C3': param_key[2],
                        'qty': 0
                    }
                
                # Add to stock
                bcn_stock[transaction.BCN]['qty'] += transaction.Value1
                
            elif transaction.VchType == '9':  # Sale
                # For sales, we need to find the matching BCN to sell from
                # First try exact BCN match
                if transaction.BCN in bcn_stock:
                    # Reduce stock from this BCN
                    bcn_stock[transaction.BCN]['qty'] -= abs(transaction.Value1)  # Use absolute value for sale
                    
                    # Remove BCN if stock is 0 or negative
                    if bcn_stock[transaction.BCN]['qty'] <= 0:
                        del bcn_stock[transaction.BCN]
                else:
                    # If no exact BCN match, find any BCN with matching parameters
                    for bcn, stock in list(bcn_stock.items()):
                        if (stock['C1'] == param_key[0] and 
                            stock['C2'] == param_key[1] and 
                            stock['C3'] == param_key[2]):
                            
                            # Reduce stock from this BCN
                            stock['qty'] -= abs(transaction.Value1)  # Use absolute value for sale
                            
                            # Remove BCN if stock is 0 or negative
                            if stock['qty'] <= 0:
                                del bcn_stock[bcn]
                            break
        
        # Convert to list and only include positive stock
        result = []
        total_qty = 0
        for bcn, stock_data in bcn_stock.items():
            if stock_data['qty'] > 0:
                stock_data['bcn'] = bcn
                result.append(stock_data)
                total_qty += stock_data['qty']
        
        return result, total_qty

    def get_total_amount(self):
        """Calculate total amount for all stock"""
        stock_data = self.parameter_wise_closing_stock()
        return sum(item['amount'] for item in stock_data)

    def get_parameter_stock_summary(self):
        """
        Returns a formatted summary of parameter-wise stock
        """
        param_stock = self.parameter_wise_closing_stock()
        
        if not param_stock:
            return "No stock data available"
        
        summary = []
        for item in param_stock:
            param_str = f"C1: {item['C1']}, C2: {item['C2']}, C3: {item['C3']}"
            stock = f"Qty: {item['qty']}, Amount: {item['amount']}"
            summary.append(f"{param_str} → {stock}")
        
        return "\n".join(summary)

    closing_stock.short_description = 'Total Closing Stock'


class ItemParamDet(models.Model):
    Date = models.CharField(max_length=20)
    VchType = models.CharField(max_length=10)  # 2 = Purchase, 9 = Sale
    VchNo = models.CharField(max_length=10)
    Item = models.ForeignKey(Master1, on_delete=models.CASCADE)
    C1 = models.CharField(max_length=50, blank=True)
    C2 = models.CharField(max_length=50, blank=True)
    C3 = models.CharField(max_length=50, blank=True)
    C4 = models.CharField(max_length=50, blank=True)
    C5 = models.CharField(max_length=50, blank=True)
    BCN = models.CharField(max_length=50, blank=True)
    Value1 = models.FloatField(default=0)

    def __str__(self):
        return f"{self.Date} - {self.Item.Code} - Qty: {self.Value1}"
    
    def get_parameter_string(self):
        """Returns a formatted string of all parameters"""
        params = []
        for i, param in enumerate([self.C1, self.C2, self.C3, self.C4, self.C5], 1):
            if param:
                params.append(f"C{i}: {param}")
        return " | ".join(params) if params else "No Parameters"
    
    class Meta:
        verbose_name = "Item Parameter Detail"
        verbose_name_plural = "Item Parameter Details"