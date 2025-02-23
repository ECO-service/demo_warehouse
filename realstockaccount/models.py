from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User, Group
from operation.models import Account, PartnerInfo
from realstockaccount import *
from django.db.models.signals import post_save, post_delete,pre_save, pre_delete
from django.dispatch import receiver
import logging

# Create your models here.
  
class BankCashTransfer(models.Model):
    TYPE_CHOICES = [
        ('cash_in', 'Ghi có'),
        ('cash_out', 'Ghi nợ')
        
    ]
    partner = models.ForeignKey(PartnerInfo,on_delete=models.CASCADE,verbose_name="Đối tác")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date = models.DateField( default=timezone.now,verbose_name = 'Ngày giao dịch' )
    amount = models.FloatField(verbose_name = 'Số tiền')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, null=False, blank=False,verbose_name = 'Loại giao dịch')
    account = models.ForeignKey(Account,on_delete=models.CASCADE,null=True, blank= True,verbose_name="Tài khoản")
    description = models.TextField(max_length=255, blank=True,verbose_name = 'Mô tả')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True, verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    
    class Meta:
         verbose_name = 'Sao kê TKNH'
         verbose_name_plural = 'Sao kê TKNH'
    
    def __str__(self):
        return f"{self.type}_{self.amount}" 
    
    


    
