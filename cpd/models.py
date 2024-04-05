from django.db import models
from django.contrib.auth.models import User, Group
from datetime import datetime, timedelta
from django.db.models import F
# Create your models here.

class ClientPartnerInfo (models.Model):
    RANK_CHOICES = [
        ('1', '1'),
        ('2', '2'),
        ('3','3'),
    ]
    full_name = models.CharField(max_length= 50, verbose_name='Tên đầy đủ')
    phone = models.IntegerField(null=False, verbose_name='Điện thoại', unique=True)
    email = models.EmailField(max_length=100)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    address = models.CharField(max_length=100, null= True, blank = True, verbose_name='Địa chỉ')
    birthday = models.DateField(null=True, blank = True, verbose_name='Ngày sinh')
    note =  models.CharField(max_length= 200,null=True, blank = True, verbose_name='Ghi chú')
    company = models.CharField(max_length= 50,null=True, blank=True, verbose_name='Công ty')
    rank= models.CharField(max_length=4,choices=RANK_CHOICES, null=False, blank=False,verbose_name = 'Cấp')
    commission = models.FloatField(default = 0.3, verbose_name='Tỷ lệ chia hoa hồng')
    class Meta:
        verbose_name = 'Đăng kí CTV'
        verbose_name_plural = 'Đăng kí CTV'

    def __str__(self):
        return str(self.full_name) + '_' + str(self.pk)
    
    def save(self, *args, **kwargs):
        if self.rank =='1':
            self.commission = 0.2
        elif self.rank =='2':
            self.commission = 0.4
        else:
            self.commission =0
        super(ClientPartnerInfo, self).save(*args, **kwargs)


class ClientPartnerCommission (models.Model):
    cp = models.ForeignKey(ClientPartnerInfo,on_delete=models.CASCADE, verbose_name= 'Người giới thiệu' )
    month_year_str  = models.CharField(blank=True, null=True,verbose_name = 'Tháng/Năm' )
    month_year = models.DateField()
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,verbose_name="Người chỉnh sửa")
    total_value= models.FloatField(default=0, verbose_name= 'Tổng Giá trị GD')
    trading_fee_spreads = models.FloatField(default=0, verbose_name= 'DT chênh lệch PGD')
    commission_back = models.FloatField(default=0, verbose_name= 'HH HSC trả')
    total_revenue = models.FloatField(default=0, verbose_name= 'Tổng Doanh thu tính thu nhập')
    total_commission = models.FloatField(default=0, verbose_name= 'Thu nhập CTV')
    
    class Meta:
         verbose_name = 'Thu nhập CTV '
         verbose_name_plural = 'Thu nhập CTV '
    def __str__(self):
        return self.cp.full_name
    
    def save(self, *args, **kwargs):
        self.month_year_str = "{}/{}".format(str(self.month_year.month), str(self.month_year.year))
        self.trading_fee_spreads = self.total_value*0.0005
        self.commission_back = (self.total_value*0.001 -self.total_value*0.0003)*0.85*0.9
        self.total_revenue = self.trading_fee_spreads + self.commission_back
        self.total_commission = self.total_revenue * self.cp.commission
        super(ClientPartnerCommission , self).save(*args, **kwargs)

def transaction_cpd_filter(month_year,transaction_all,cp):
    end_period = month_year.replace(day=20)
    # Tính ngày đầu tiên của tháng trước đó
    start_period = month_year - timedelta(days=month_year.day)
    start_period = start_period.replace(day=20)
    total_value_items = transaction_all.filter(account__cp =cp,date__gt =start_period,date__lte = end_period )
    return total_value_items

def define_month_year_cp_commission(date):
    if date.day <=20:
        month_year =  datetime(date.year, date.month, 1)
    else:
        month_year = date + timedelta(days=31)
        month_year = month_year.replace(day=1)
    return month_year


def cp_create_transaction(instance):
    month_year=define_month_year_cp_commission(instance.date)
    try:
        # Kiểm tra xem bản ghi đã tồn tại chưa
        commission_record = ClientPartnerCommission.objects.get(cp=instance.account.cpd, month_year=month_year)
        # Nếu bản ghi tồn tại, cập nhật giá trị của trường total_value
        commission_record.total_value = F('total_value') + instance.total_value
        commission_record.save()
    except ClientPartnerCommission.DoesNotExist:
        # Nếu bản ghi không tồn tại, tạo mới bản ghi với giá trị mặc định
        commission_record = ClientPartnerCommission.objects.create(cp=instance.account.cpd, month_year=month_year, total_value=instance.total_value)


def cp_update_transaction( instance, account_all):
    cp = instance.account.cpd
    origin_total_value=instance.previous_total_value
    edit_total_value = instance.total_value
    original_date = instance.previous_date
    edit_month_year=define_month_year_cp_commission(instance.date)
    origin_month_year = define_month_year_cp_commission(original_date)
    if origin_month_year != edit_month_year:
        try:
            # Kiểm tra xem bản ghi đã tồn tại chưa
            edit_commission = ClientPartnerCommission.objects.get(cp=cp, month_year=edit_month_year)
            # Nếu bản ghi tồn tại, cập nhật giá trị của trường total_value
            edit_commission.total_value += edit_total_value
            edit_commission.save()
        except ClientPartnerCommission.DoesNotExist:
            # Nếu bản ghi không tồn tại, tạo mới bản ghi với giá trị mặc định
            ClientPartnerCommission.objects.create(cp=cp, month_year=edit_month_year, total_value=edit_total_value)
        edit_commission = ClientPartnerCommission.objects.get(cp=cp, month_year=edit_month_year)
        origin_commission = ClientPartnerCommission.objects.get(cp=cp, month_year=origin_month_year)  
        if edit_commission !=origin_commission:  
            origin_commission.total_value-=origin_total_value
            if origin_commission.total_value<0:
                origin_commission.total_value=0
            origin_commission.save()
    else:
        if origin_total_value != edit_total_value: 
            commission = ClientPartnerCommission.objects.get(cp=cp, month_year=edit_month_year)
            commission.total_value = commission.total_value + edit_total_value - origin_total_value
            commission.save()


# trường hợp có cho chỉnh account tại transaction
# def cp_update_transaction( instance, account_all):
#     origin_total_value=instance.previous_total_value
#     edit_total_value = instance.total_value
#     original_date = instance.previous_date
#     edit_account = instance.account
#     origin_account = instance.previous_account
#     edit_month_year=define_month_year_cp_commission(instance.date)
#     origin_month_year = define_month_year_cp_commission(original_date)
#     if origin_account != edit_account.pk or origin_month_year != edit_month_year:
#         edit_cpd = edit_account.cpd 
#         try:
#             # Kiểm tra xem bản ghi đã tồn tại chưa
#             edit_commission = ClientPartnerCommission.objects.get(cp=edit_cpd, month_year=edit_month_year)
#             # Nếu bản ghi tồn tại, cập nhật giá trị của trường total_value
#             edit_commission.total_value += edit_total_value
#             edit_commission.save()
#         except ClientPartnerCommission.DoesNotExist:
#             # Nếu bản ghi không tồn tại, tạo mới bản ghi với giá trị mặc định
#             ClientPartnerCommission.objects.create(cp=edit_cpd, month_year=edit_month_year, total_value=edit_total_value)
#         edit_commission = ClientPartnerCommission.objects.get(cp=edit_cpd, month_year=edit_month_year)
#         origin_cpd =  account_all.filter(id = origin_account).first().cpd
#         origin_commission = ClientPartnerCommission.objects.get(cp=origin_cpd, month_year=origin_month_year)  
#         if edit_commission !=origin_commission:  
#             origin_commission.total_value-=origin_total_value
#             if origin_commission.total_value<0:
#                 origin_commission.total_value=0
#             origin_commission.save()
#     else:
#         if origin_total_value != edit_total_value: 
#             commission = ClientPartnerCommission.objects.get(cp=instance.account.cpd, month_year=edit_month_year)
#             commission.total_value = commission.total_value + edit_total_value - origin_total_value
#             commission.save()


    
    





