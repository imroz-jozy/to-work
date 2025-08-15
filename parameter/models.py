from django.db import models
from django.db.models import Sum, Case, When, F, FloatField, Q, Value, CharField
from django.db.models.functions import Concat
from django.utils import timezone
from core.models import Master1, ItemParamDet


class BCNStockSummary(models.Model):
    """Model to represent BCN-wise stock summary"""
    bcn = models.CharField(max_length=50, primary_key=True)
    item_code = models.CharField(max_length=20)
    item_name = models.CharField(max_length=100)
    parameters = models.CharField(max_length=255)
    opening_stock = models.FloatField(default=0)
    closing_stock = models.FloatField(default=0)
    movement = models.FloatField(default=0)
    
    class Meta:
        managed = False
        verbose_name = 'BCN-wise Stock Summary'
        verbose_name_plural = 'BCN-wise Stock Summary'
    
    @classmethod
    def get_queryset(cls, start_date=None, end_date=None):
        """Generate a queryset of BCN stock summaries"""
        # Get distinct BCNs from ItemParamDet
        bcn_query = ItemParamDet.objects.filter(BCN__isnull=False).exclude(BCN='').values_list('BCN', flat=True).distinct()
        
        # Create a list to hold our summary objects
        summaries = []
        
        for bcn in bcn_query:
            # Get a sample record to extract item and parameter info
            sample = ItemParamDet.objects.filter(BCN=bcn).first()
            if not sample:
                continue
                
            # Get item details
            item_code = sample.ItemCode
            item_name = 'Unknown Item'
            try:
                item = Master1.objects.filter(Code=item_code, MasterType=6).first()
                if item:
                    item_name = item.Name
            except Exception:
                pass
                
            # Get parameters
            params = []
            for i in range(1, 6):
                param_value = getattr(sample, f'C{i}', None)
                if param_value and param_value.strip():
                    params.append(param_value)
            parameters = ' | '.join(params) if params else 'No Parameters'
            
            # Calculate stock values
            opening_stock = ParameterStockView.get_opening_stock_by_bcn(bcn, start_date, end_date)
            closing_stock = ParameterStockView.get_closing_stock_by_bcn(bcn, start_date, end_date)
            movement = ParameterStockView.get_movement_by_bcn(bcn, start_date, end_date)
            
            # Create a summary object
            summary = cls(bcn=bcn, item_code=item_code, item_name=item_name, 
                          parameters=parameters, opening_stock=opening_stock,
                          closing_stock=closing_stock, movement=movement)
            summaries.append(summary)
            
        return summaries

# Proxy models to create separate admin interfaces
class StockReportView(Master1):
    """Proxy model for stock reporting"""
    class Meta:
        proxy = True
        verbose_name = "Stock Report"
        verbose_name_plural = "Stock Reports"
        app_label = 'parameter'

    def get_opening_stock(self, start_date=None, end_date=None):
        """Calculate opening stock for this item (VchType = 1)
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        try:
            query = ItemParamDet.objects.filter(ItemCode=self, VchType=1)
            
            # Apply date filters if provided
            if start_date:
                query = query.filter(Date__gte=start_date)
            if end_date:
                query = query.filter(Date__lte=end_date)
                
            opening_stock = query.aggregate(Sum('Value1'))['Value1__sum'] or 0
            return float(opening_stock)
        except (ValueError, TypeError):
            return 0.0

    def get_closing_stock(self, start_date=None, end_date=None):
        """Calculate closing stock for this item (all transactions)
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        try:
            query = ItemParamDet.objects.filter(ItemCode=self)
            
            # Apply date filters if provided
            if start_date:
                query = query.filter(Date__gte=start_date)
            if end_date:
                query = query.filter(Date__lte=end_date)
                
            closing_stock = query.aggregate(Sum('Value1'))['Value1__sum'] or 0
            return float(closing_stock)
        except (ValueError, TypeError):
            return 0.0

    def get_movement(self, start_date=None, end_date=None):
        """Calculate stock movement (excluding opening stock)
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        try:
            query = ItemParamDet.objects.filter(ItemCode=self).exclude(VchType=1)
            
            # Apply date filters if provided
            if start_date:
                query = query.filter(Date__gte=start_date)
            if end_date:
                query = query.filter(Date__lte=end_date)
                
            movement = query.aggregate(Sum('Value1'))['Value1__sum'] or 0
            return float(movement)
        except (ValueError, TypeError):
            return 0.0

    def get_stock_status(self, start_date=None, end_date=None):
        """Get stock status for display
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        closing = self.get_closing_stock(start_date, end_date)
        if closing > 0:
            return "✅ In Stock"
        elif closing == 0:
            return "⚠️ Zero Stock"
        else:
            return "❌ Negative Stock"

class ParameterStockView(ItemParamDet):
    """Proxy model for parameter-wise stock reporting"""
    class Meta:
        proxy = True
        verbose_name = "Parameter Stock Detail"
        verbose_name_plural = "Parameter Stock Details"
        app_label = 'parameter'

    def get_parameter_string(self):
        """Get formatted parameter string"""
        params = []
        for param in [self.C1, self.C2, self.C3, self.C4, self.C5]:
            if param and str(param).strip():
                params.append(str(param).strip())
        return ' | '.join(params) if params else "No Parameters"
    
    def get_item_code_display(self):
        """Get item code safely"""
        return self.ItemCode.Code if self.ItemCode else "N/A"
    
    def get_item_name_display(self):
        """Get item name safely"""
        return self.ItemCode.Name if self.ItemCode else "N/A"
        
    @classmethod
    def get_opening_stock_by_bcn(cls, bcn, start_date=None, end_date=None):
        """Get opening stock for a specific BCN"""
        query = cls.objects.filter(BCN=bcn)
        
        # Apply date filtering if provided
        if start_date:
            # For opening stock, we want all entries before start_date
            query = query.filter(Date__lt=start_date)
        
        # Sum the Value1 field (positive for receipts, negative for issues)
        result = query.aggregate(
            opening_stock=Sum(models.Case(
                models.When(VchType=1, then=models.F('Value1')),  # Opening Balance
                models.When(VchType=2, then=models.F('Value1')),  # Purchase/Receipt
                models.When(VchType=3, then=-models.F('Value1')),  # Sale/Issue
                models.When(VchType=4, then=models.F('Value1')),  # Transfer In
                models.When(VchType=5, then=-models.F('Value1')),  # Transfer Out
                models.When(VchType=9, then=-models.F('Value1')),  # Sale
                default=0,
                output_field=models.FloatField()
            ))
        )
        
        return result['opening_stock'] or 0
    
    @classmethod
    def get_closing_stock_by_bcn(cls, bcn, start_date=None, end_date=None):
        """Get closing stock for a specific BCN"""
        query = cls.objects.filter(BCN=bcn)
        
        # Apply date filtering if provided
        if end_date:
            query = query.filter(Date__lte=end_date)
        
        # Sum the Value1 field (positive for receipts, negative for issues)
        result = query.aggregate(
            closing_stock=Sum(models.Case(
                models.When(VchType=1, then=models.F('Value1')),  # Opening Balance
                models.When(VchType=2, then=models.F('Value1')),  # Purchase/Receipt
                models.When(VchType=3, then=-models.F('Value1')),  # Sale/Issue
                models.When(VchType=4, then=models.F('Value1')),  # Transfer In
                models.When(VchType=5, then=-models.F('Value1')),  # Transfer Out
                models.When(VchType=9, then=-models.F('Value1')),  # Sale
                default=0,
                output_field=models.FloatField()
            ))
        )
        
        return result['closing_stock'] or 0
        
    @classmethod
    def get_movement_by_bcn(cls, bcn, start_date=None, end_date=None):
        """Get stock movement for a specific BCN within date range"""
        query = cls.objects.filter(BCN=bcn)
        
        # Apply date filtering if provided
        if start_date and end_date:
            query = query.filter(Date__gte=start_date, Date__lte=end_date)
        elif start_date:
            query = query.filter(Date__gte=start_date)
        elif end_date:
            query = query.filter(Date__lte=end_date)
            
        # Exclude opening entries for movement calculation
        query = query.exclude(VchType=1)  # Exclude opening balance entries
        
        # Sum the Value1 field (positive for receipts, negative for issues)
        result = query.aggregate(
            movement=Sum(models.Case(
                models.When(VchType=2, then=models.F('Value1')),  # Purchase/Receipt
                models.When(VchType=3, then=-models.F('Value1')),  # Sale/Issue
                models.When(VchType=4, then=models.F('Value1')),  # Transfer In
                models.When(VchType=5, then=-models.F('Value1')),  # Transfer Out
                models.When(VchType=9, then=-models.F('Value1')),  # Sale
                default=0,
                output_field=models.FloatField()
            ))
        )
        
        return result['movement'] or 0