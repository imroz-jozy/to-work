from django.db import models

class UserProfile(models.Model):
    # SQL Server Info
    sql_host = models.URLField(max_length=100)
    server = models.CharField(max_length=100)
    sql_port = models.CharField(max_length=10, blank=True)
    sql_username = models.CharField(max_length=100)
    sql_password = models.CharField(max_length=100)
    sql_database = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)

    # Company Info
    company_name = models.CharField(max_length=255)
    company_address = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.is_active:
            UserProfile.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active_config(cls):
        """Return the active profile, or None if not set."""
        return cls.objects.filter(is_active=True).first()

    def __str__(self):
        return f"{self.company_name}"





class Master1(models.Model):
     Code = models.CharField(max_length=20, unique=True)
     MasterType = models.CharField(max_length=10) 
     Name = models.CharField(max_length=100)
     
     def __str__(self): 
         return f"{self.Code} - {self.Name}"
     




class ItemParamDet(models.Model):
     VOUCHER_TYPES = [
        ('1', 'Opening Balance'),
        ('2', 'Purchase'),
        ('9', 'Sale'),
    ]
     Date = models.DateField(help_text="Format: YYYY-MM-DD")  
     VchNo = models.CharField(max_length=10)
     ItemCode = models.ForeignKey(Master1, on_delete=models.CASCADE)
     C1 = models.CharField(max_length=50, blank=True)
     C2 = models.CharField(max_length=50, blank=True)
     C3 = models.CharField(max_length=50, blank=True)
     C4 = models.CharField(max_length=50, blank=True)
     C5 = models.CharField(max_length=50, blank=True)
     D3 = models.CharField(max_length=50, blank=True,verbose_name='mrp') 
     D4 = models.CharField(max_length=50, blank=True,verbose_name='sale price') 
     BCN = models.CharField(max_length=50, blank=True) 
     Value1 = models.FloatField(default=0)
     
     def __str__(self):
         return f"{self.ItemCode.Code if self.ItemCode else 'N/A'} - {self.Date} - {self.VchNo}"