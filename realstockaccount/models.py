from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User, Group
from operation.models import Account, PartnerInfo
from realstockaccount import *
from django.db.models.signals import post_save, post_delete,pre_save, pre_delete
from django.dispatch import receiver
import logging

# Create your models here.
class RealStockAccountCashTransfer(models.Model):
    account = models.CharField(max_length=20,default = '011C263979',verbose_name = 'Tài khoản' )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date = models.DateField( default=timezone.now,verbose_name = 'Ngày nộp tiền' )
    amount = models.FloatField(verbose_name = 'Số tiền')
    description = models.TextField(max_length=255, blank=True,verbose_name = 'Mô tả')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    class Meta:
         verbose_name = 'Sao kê tiền TKCK'
         verbose_name_plural = 'Sao kê tiền TKCK'
    
    def __str__(self):
        return str(self.amount) 
    
class RealBankCashTransfer(models.Model):
    TYPE_CHOICES = [
        ('salary', 'Chi phí lương'),
        ('other_expense', 'Chi phí khác'),
        ('cp_commission','Hoa hồng CTV'),
        ('trade_transfer','Chuyển tiền giao dịch')
    ]
    account = models.CharField(max_length=20,default = 'TCB',verbose_name = 'Tài khoản' )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date = models.DateField( default=timezone.now,verbose_name = 'Ngày nộp tiền' )
    amount = models.FloatField(verbose_name = 'Số tiền')
    type = models.CharField(max_length=20,default  = 'trade_transfer' , choices=TYPE_CHOICES, null=False, blank=False,verbose_name = 'Mục')
    description = models.TextField(max_length=255, blank=True,verbose_name = 'Mô tả')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    class Meta:
         verbose_name = 'Sao kê tiền TKNH'
         verbose_name_plural =  'Sao kê tiền TKNH'
    
    def __str__(self):
        return str(self.amount) 
    
class BankCashTransfer(models.Model):
    TYPE_CHOICES = [
        ('salary', 'Chi phí lương'),
        ('other_expense', 'Chi phí khác'),
        ('cp_commission','Hoa hồng CTV'),
        ('trade_transfer','Chuyển tiền giao dịch')
    ]
    SOURCE_CHOICES= [
        ('TCB-Ha','TCB-Hà'),
        ('TCB-Vinh','TCB-Vĩnh')
    ]
    source = models.CharField(max_length=20,choices=SOURCE_CHOICES,default = 'TCB',verbose_name = 'Nguồn' )
    account = models.ForeignKey(Account,on_delete=models.CASCADE,null=True, blank= True,verbose_name="Khách hàng")
    partner = models.ForeignKey(PartnerInfo,on_delete=models.CASCADE,null=True, blank= True,verbose_name="Đối tác")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date = models.DateField( default=timezone.now,verbose_name = 'Ngày nộp tiền' )
    amount = models.FloatField(verbose_name = 'Số tiền')
    type = models.CharField(max_length=20,default  = 'trade_transfer' , choices=TYPE_CHOICES, null=False, blank=False,verbose_name = 'Mục')
    description = models.TextField(max_length=255, blank=True,verbose_name = 'Mô tả')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    customer_cash_id = models.FloatField(null =True, blank = True,verbose_name = 'Mã nạp tiền KH')
    class Meta:
         verbose_name = 'Sao kê TKNH-KH'
         verbose_name_plural = 'Sao kê TKNH-KH'
    
    def __str__(self):
        return f"{self.type}_{self.amount}" 
    
    def get_readonly_fields(self, request, obj=None):
        # Nếu đang chỉnh sửa bản ghi đã tồn tại, trường account sẽ là chỉ đọc
        if obj:
            return ['account','partner',]
        return []

class BankCashTransferManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(type ='trade_transfer')

class InternalBankCashTransfer(BankCashTransfer):
    objects = BankCashTransferManager()

    class Meta:
        proxy = True
        verbose_name = 'Sao kê TKNH - Nội bộ'
        verbose_name_plural = 'Sao kê TKNH - Nội bộ'
    

    def __str__(self):
        return f"{self.type}_{self.amount}" 

    
class RealTradingPower(models.Model):
    account = models.CharField(max_length=20,default = '011C263979',verbose_name = 'Tài khoản' )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date = models.DateField( default=timezone.now,verbose_name = 'Ngày' )
    max_amount = models.FloatField(verbose_name = 'Sức mua tối đa')
    min_amount = models.FloatField(verbose_name = 'Sức mua tối thiểu')
    description = models.TextField(max_length=255, blank=True,verbose_name = 'Mô tả')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    class Meta:
         verbose_name = 'Sức mua tài khoản'
         verbose_name_plural = 'Sức mua tài khoản'
    
    def __str__(self):
        return str(self.date) 
    
class RealStockAccount(models.Model):
    partner = models.ForeignKey(PartnerInfo,on_delete=models.CASCADE,verbose_name="Đối tác")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    description = models.TextField(max_length=255, blank=True,verbose_name = 'Mô tả')
    net_cash_flow_operation = models.FloatField(default=0,verbose_name= 'Nạp rút tiền ròng bổ sung vốn')
    cash_balance_open_account= models.FloatField(default=0,verbose_name= 'Số dư tiền TK đang mở')
    cash_balance  = models.FloatField(default=0,verbose_name= 'Số dư tiền')
    market_value = models.FloatField(default=0,verbose_name= 'Giá trị thị trường')
    nav = models.FloatField(default=0,verbose_name= 'Tài sản ròng')
    total_deposit_fee= models.FloatField(default=0,verbose_name= 'Tổng phí lưu kí')
    total_deposit_fee_paid= models.FloatField(default=0,verbose_name= 'Tổng phí lưu kí đã trả')
    total_temporarily_deposit_fee =models.FloatField(default=0,verbose_name= 'Tổng phí lưu kí tạm tính')
    total_loan_interest= models.FloatField(default=0,verbose_name= 'Tổng lãi vay')
    total_interest_paid= models.FloatField(default=0,verbose_name= 'Tổng lãi vay đã trả')
    total_temporarily_interest =models.FloatField(default=0,verbose_name= 'Tổng lãi vay tạm tính')
    total_deposit_interest_paid =models.FloatField(default=0,verbose_name= 'Tổng lãi tiền gửi đã trả')
    interest_cash_balance = models.FloatField(default=0,verbose_name= 'Số dư tính lãi')
    milestone_cash_t2 = models.FloatField(default=0,verbose_name= 'Tiền chờ về T2 TK đã tất toán')
    milestone_cash_t1 = models.FloatField(default=0,verbose_name= 'Tiền chờ về T1 TK đã tất toán')
    
    class Meta:
         verbose_name = 'Tài khoản chứng khoán'
         verbose_name_plural = 'Tài khoản chứng khoán'
    
    def __str__(self):
        return str(self.partner) 
    
    def save(self, *args, **kwargs):
        self.total_deposit_fee = self.total_deposit_fee_paid + self.total_temporarily_deposit_fee
        self.total_loan_interest = self.total_interest_paid + self.total_temporarily_interest
        self.cash_balance = self.net_cash_flow_operation + self.cash_balance_open_account+ self.total_deposit_fee +self.total_loan_interest + self.total_deposit_interest_paid
        self.nav = self.market_value + self.cash_balance
        super(RealStockAccount, self).save(*args, **kwargs)
        logging.info("save object {} ID {}.".format(self.__class__.__name__, self.id))

    def delete(self, *args, **kwargs):
        # Ghi log khi có hoạt động xóa
        logging.info("delete object {} ID {}.".format(self.__class__.__name__, self.id))
        super().delete(*args, **kwargs)

class ExpenseStatementRealStockAccount(models.Model):
    POSITION_CHOICES = [
        ('loan_interest', 'Lãi vay'),
        ('transaction_fee', 'Phí giao dịch'),
        ('tax', 'Thuế bán'),
        ('deposit_fee', 'Phí lưu kí'),
        ('deposit_interest', 'Lãi tiền gửi'),

    ]
    account = models.ForeignKey(RealStockAccount,on_delete=models.CASCADE,  verbose_name = 'Tài khoản CK' )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date =models.DateField( verbose_name = 'Ngày' )
    type =models.CharField(max_length=50, choices=POSITION_CHOICES, null=False, blank=False,verbose_name = 'Loại phí')
    amount = models.FloatField (verbose_name='Số tiền')
    description = models.CharField(max_length=100,null=True, blank=True, verbose_name='Diễn giải')
    interest_cash_balance = models.FloatField (null = True,blank =True ,verbose_name='Số dư tiền tính lãi')
    total_qty_stock= models.FloatField (null = True,blank =True ,verbose_name='Tổng số cổ phiếu lưu kí')

    class Meta:
         verbose_name = 'Bảng kê chi phí TKCK'
         verbose_name_plural = 'Bảng kê chi phí TKCK'
    