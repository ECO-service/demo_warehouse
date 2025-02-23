import re
from django.db import models
from django.db.models.signals import post_save, post_delete,pre_save, pre_delete
from django.contrib.auth.models import User, Group
from django.dispatch import receiver
from datetime import datetime, timedelta
from django.forms import ValidationError
import requests
from bs4 import BeautifulSoup
from infotrading.models import *
from django.db.models import Sum
from django.utils import timezone
from telegram import Bot
from django.db.models import Q
from cpd.models import *
from django.contrib.auth.hashers import make_password
from regulations.models import *
from accfifo import Entry, FIFO
from regulations.models import BotTelegram
import logging


def send_notification(message):
    bot= BotTelegram.objects.all().first()
    bot_token = bot.token
    chat_id =bot.bot_id
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    data = {'chat_id': chat_id, 'text': message}
    
    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        print("Message sent successfully.")
    else:
        print("Failed to send message.")


        

def cal_avg_price(account,stock, date_time): 
    item_transactions = Transaction.objects.filter(account=account, stock__stock = stock, created_at__gt =date_time).order_by('date','created_at')
    fifo = FIFO([])
    for item in item_transactions:
    # Kiểm tra xem giao dịch có phải là mua hay bán
        if item.position == 'buy':
            # Nếu là giao dịch mua, thêm một Entry mới với quantity dương vào FIFO
            entry = Entry(item.qty, item.price)
        else:
            # Nếu là giao dịch bán, thêm một Entry mới với quantity âm vào FIFO
            entry = Entry(-item.qty, item.price)
        # Thêm entry vào FIFO
        fifo._push(entry) if entry.buy else fifo._fill(entry)
        
        # fifo.trace in ra từng giao dịch bán
        # fifo.profit_and_loss tính lời lỗ
    return fifo.avgcost

def total_value_inventory_stock(account, stock, start_date, end_date,partner=None):
    filter_conditions = {'account': account, 'stock__stock': stock, 'created_at__gt': start_date, 'date__lte': end_date}
    if partner:
        filter_conditions['partner'] = partner
    item_transactions = Transaction.objects.filter(**filter_conditions).order_by('date', 'created_at')
    fifo = FIFO([])
    for item in item_transactions:
    # Kiểm tra xem giao dịch có phải là mua hay bán
        if item.position == 'buy':
            # Nếu là giao dịch mua, thêm một Entry mới với quantity dương vào FIFO
            entry = Entry(item.qty, item.price)
        else:
            # Nếu là giao dịch bán, thêm một Entry mới với quantity âm vào FIFO
            entry = Entry(-item.qty, item.price)
        # Thêm entry vào FIFO
        fifo._push(entry) if entry.buy else fifo._fill(entry)
    fifo_inventory =fifo.inventory
    total_value = 0
    for entry in fifo_inventory:
        quantity, price = entry.quantity, entry.price
        #Tìm tỷ lê cho vay để tính giá trị cho vay theo phần 5 của vlc
        margin_rate = StockListMargin.objects.filter(stock=stock).first().initial_margin_requirement
        ratio_margin_rate = max(1 - (margin_rate - 20) / 100, 0)
        #tính tổng số tiền tính lãi vay có bao gồm phí giao dịch => đã bỏ phí giao dịch
        total_value += quantity * price *ratio_margin_rate 
        
    return total_value


class PartnerInfo(models.Model):

    method_interest= [
        ('total_buy_value', 'Tính trên giá trị mua'),
        ('dept', 'Tính trên dư nợ'),
    ]
    name = models.CharField(max_length= 50, verbose_name='Tên đối tác')
    phone = models.IntegerField(null=False, verbose_name='Điện thoại', unique=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    address = models.CharField(max_length=100, null= True, blank = True, verbose_name='Địa chỉ')
    note =  models.CharField(max_length= 200,null=True, blank = True, verbose_name='Ghi chú')
    ratio_trading_fee = models.FloatField(default = 0.001, verbose_name='Phí giao dịch')
    ratio_interest_fee= models.FloatField(default = 0.15, verbose_name='Lãi vay')
    ratio_advance_fee= models.FloatField(default = 0.15, verbose_name='Phí ứng tiền')
    total_date_interest = models.IntegerField(default = 360,verbose_name = 'Số ngày tính lãi/năm')
    method_interest =models.CharField(max_length=100,default ='dept',null=True,blank=True, choices=method_interest,verbose_name = 'Phương thức tính lãi')
    maintenance_margin_ratio= models.FloatField(default = 17, verbose_name='Tỷ lệ duy trì')
    force_sell_margin_ratio= models.FloatField(default = 13, verbose_name='Tỷ lệ bán khống')
    
    class Meta:
        verbose_name = 'Đăng kí đối tác'
        verbose_name_plural = 'Đăng kí đối tác'

    def __str__(self):
        return str(self.name) + '_' + str(self.pk)
    

# nếu sau này 1 partner có nhiều đối tác, cần chuyển models realstockaccount qua đây, gán trasaction và banktransfer với realstockacount thay vì trực tiếp partner
# Create your models here.
class Account (models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name= 'Tên Khách hàng')
    partner = models.ForeignKey(PartnerInfo,on_delete=models.CASCADE,null=False, blank= False,verbose_name="Đối tác")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    description = models.TextField(max_length=255, blank=True, verbose_name= 'Mô tả')
    cpd = models.ForeignKey(ClientPartnerInfo,null=True, blank = True,on_delete=models.CASCADE, verbose_name= 'Người giới thiệu' )
    #biểu phí dịch vụ
    interest_fee = models.FloatField(default=0.00036, verbose_name='Lãi suất theo ngày')
    # interest_days_in_year = models.PositiveSmallIntegerField(default=365, verbose_name="Số ngày tính lãi trong năm")
    transaction_fee = models.FloatField(default=0.0015, verbose_name='Phí giao dịch')
    tax = models.FloatField(default=0.001, verbose_name='Thuế')
    maintenance_margin_ratio =models.FloatField(default=0.17, verbose_name='Tỷ lệ gọi kí quỹ')
    force_sell_margin_ratio =models.FloatField(default=0.13, verbose_name='Tỷ lệ giải chấp')
    # Phục vụ tính tổng cash_balace:
    net_cash_flow= models.FloatField(default=0,verbose_name= 'Nạp rút tiền ròng')
    net_trading_value= models.FloatField(default=0,verbose_name= 'Giao dịch ròng')
    cash_balance  = models.FloatField(default=0,verbose_name= 'Số dư tiền')
    market_value = models.FloatField(default=0,verbose_name= 'Giá trị thị trường')
    nav = models.FloatField(default=0,verbose_name= 'Tài sản ròng')
    initial_margin_requirement= models.FloatField(default=0,verbose_name= 'Kí quy ban đầu')
    margin_ratio = models.FloatField(default=0,verbose_name= 'Tỷ lệ margin')
    excess_equity= models.FloatField(default=0,verbose_name= 'Dư kí quỹ')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,related_name='user',null=True, blank= True,verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,verbose_name="Người chỉnh sửa")
    #Phục vụ tính số dư tiền tính lãi vay: interest_cash_balance = net_cash_flow + total_buy_trading_value  + casht0
    total_buy_trading_value= models.FloatField(default=0,verbose_name= 'Tổng giá trị mua')
    cash_t1 = models.FloatField(default=0,verbose_name= 'Số dư tiền T1')
    cash_t2= models.FloatField(default=0,verbose_name= 'Số dư tiền T2')
    cash_t0= models.FloatField(default=0,verbose_name= 'Số dư tiền bán đã về')
    interest_cash_balance= models.FloatField(default=0,verbose_name= 'Số dư tiền tính lãi')
    total_loan_interest= models.FloatField(default=0,verbose_name= 'Tổng lãi vay')
    total_interest_paid= models.FloatField(default=0,verbose_name= 'Tổng lãi vay đã trả')
    total_temporarily_interest =models.FloatField(default=0,verbose_name= 'Tổng lãi vay tạm tính')
    total_advance_fee= models.FloatField(default=0,verbose_name= 'Tổng phí ứng')
    total_advance_fee_paid= models.FloatField(default=0,verbose_name= 'Tổng phí ứng đã trả')
    total_temporarily_advance_fee =models.FloatField(default=0,verbose_name= 'Tổng phí ứng tạm tính')
    total_pl = models.FloatField(default=0,verbose_name= 'Tổng lời lỗ')
    total_closed_pl= models.FloatField(default=0,verbose_name= 'Tổng lời lỗ đã chốt')
    total_temporarily_pl= models.FloatField(default=0,verbose_name= 'Tổng lời lỗ tạm tính')
    # credit_limit = models.FloatField(default=get_credit_limit_default, verbose_name='Hạn mức mua')
    credit_limit = models.FloatField(default=1000000000, verbose_name='Hạn mức mua')
    milestone_date_lated = models.DateTimeField(null =True, blank =True, verbose_name = 'Ngày tất toán gần nhất')
    book_interest_date_lated = models.DateField(null =True, blank =True, verbose_name = 'Ngày hoạch toán lãi gần nhất')
    advance_cash_balance= models.FloatField(default=0,verbose_name= 'Số dư tiền tính phí ứng')
    class Meta:
         verbose_name = 'Tài khoản'
         verbose_name_plural = 'Tài khoản'

    def __str__(self):
        return self.name
    
    @property
    # giá áp dụng cho port chỉ có 1 mã
    def price_force_sell(self):
        port = Portfolio.objects.filter(account_id = self.pk, sum_stock__gt=0)
        if len(port)==1:
            item = port[0]
            price_force_sell = round(-self.cash_balance/( 0.87* item.sum_stock),0)
            return '{:,.0f}'.format(abs(price_force_sell))
        else:
            return None

    @property
    def status(self):
        check = self.margin_ratio
        value_force = round((self.maintenance_margin_ratio - self.margin_ratio)*self.market_value/100,0)
        value_force_str = '{:,.0f}'.format(value_force)
        status = ""
        port = Portfolio.objects.filter(account_id = self.pk, sum_stock__gt=0).first()
        if port:
            price_force_sell = round(-self.cash_balance/(( 1- self.force_sell_margin_ratio)* port.sum_stock),0)
            if abs(self.cash_balance) >1000 and value_force !=0:
                if check <= self.maintenance_margin_ratio and check >self.force_sell_margin_ratio:
                    status = f"CẢNH BÁO, số âm {value_force_str}, giá bán {port.stock}: {'{:,.0f}'.format(price_force_sell)}"
                elif check <= self.force_sell_margin_ratio:
                    status = f"GIẢI CHẤP {'{:,.0f}'.format(value_force*5)}, giá bán {port.stock}:\n{'{:,.0f}'.format(price_force_sell)}"

                return status
   
    

    def save(self, *args, **kwargs):
    # Your first save method code
        print('bắt đầu save')
        self.total_loan_interest = self.total_temporarily_interest + self.total_interest_paid
        self.total_advance_fee = self.total_temporarily_advance_fee + self.total_advance_fee_paid
        self.cash_balance = self.net_cash_flow + self.net_trading_value + self.total_temporarily_interest + self.total_temporarily_advance_fee
        stock_mapping = {obj.stock: obj.initial_margin_requirement for obj in StockListMargin.objects.all()}
        port = Portfolio.objects.filter(account=self.pk, sum_stock__gt=0)
        sum_initial_margin = 0
        market_value = 0
        total_value_buy=0
        if port:
            for item in port:
                value_buy = item.sum_stock * item.avg_price
                total_value_buy +=value_buy
                initial_margin = stock_mapping.get(item.stock, 0) * value_buy / 100
                sum_initial_margin += initial_margin
                market_value += item.market_value
        self.margin_ratio = 0
        self.market_value = market_value
        self.nav = self.market_value + self.cash_balance
        self.initial_margin_requirement = sum_initial_margin
        self.excess_equity = self.nav - self.initial_margin_requirement
        self.advance_cash_balance = (self.cash_t1 + self.cash_t2)*-1
        if self.market_value != 0:
            self.margin_ratio = self.nav / total_value_buy
        self.total_temporarily_pl= self.nav - self.net_cash_flow
        self.total_pl  = self.total_temporarily_pl + self.total_closed_pl
        
        
        # Your second save method code
        print('kết thúc save')
        super(Account, self).save(*args, **kwargs)

  

        # Tạo hoặc cập nhật User
        user, created = User.objects.get_or_create(username=str(self.pk))
        if created:
            user.set_password("20241q2w3e4r")
            user.save()

            # Thêm user vào nhóm "customer"
            group, created = Group.objects.get_or_create(name='customer')
            user.groups.add(group)
        logging.info("save object {} ID {}.".format(self.__class__.__name__, self.id))

    def delete(self, *args, **kwargs):
        # Ghi log khi có hoạt động xóa
        logging.info("delete object {}  ID {}.".format(self.__class__.__name__, self.id))
        super().delete(*args, **kwargs)

#Tạo model với các ngăn tất toán của tài khoản
class AccountMilestone(models.Model):
    account = models.ForeignKey(Account,on_delete=models.CASCADE,verbose_name="Tài khoản")
    partner = models.ForeignKey(PartnerInfo,on_delete=models.CASCADE,null=False, blank= False,verbose_name="Đối tác")
    milestone = models.IntegerField(verbose_name = 'Giai đoạn')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    description = models.TextField(max_length=255, blank=True, verbose_name= 'Mô tả')
    interest_fee = models.FloatField(default=0.00036, verbose_name='Lãi suất theo ngày')
    transaction_fee = models.FloatField(default=0.0015, verbose_name='Phí giao dịch')
    tax = models.FloatField(default=0.0001, verbose_name='Thuế')
    # Phục vụ tính tổng cash_balace:
    net_cash_flow= models.FloatField(default=0,verbose_name= 'Nạp rút tiền ròng')
    total_buy_trading_value= models.FloatField(default=0,verbose_name= 'Tổng giá trị mua')
    net_trading_value = models.FloatField(default=0,verbose_name= 'Giao dịch ròng')
    interest_paid= models.FloatField(default=0,verbose_name= 'Tổng lãi vay đã trả')
    closed_pl= models.FloatField(default=0,verbose_name= 'Tổng lời lỗ đã chốt')
    advance_fee_paid= models.FloatField(default=0,verbose_name= 'Tổng phí ứng đã trả')
    

    class Meta:
         verbose_name = 'Mốc Tài khoản'
         verbose_name_plural = 'Mốc Tài khoản'

    def __str__(self):
        return str(self.account) +str('_Lần_')+ str(self.milestone)

class MaxTradingPowerAccount(Account):
    class Meta:
        proxy = True
        verbose_name = 'Quản lí sức mua'
        verbose_name_plural = 'Quản lí sức mua'
        
    def get_queryset(self):
        return super().get_queryset().filter(nav__gt=0)
    def __str__(self):
        return str(self.name)

class StockListMargin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    stock = models.CharField(max_length=8,verbose_name = 'Cổ phiếu')
    initial_margin_requirement= models.FloatField(verbose_name= 'Kí quy ban đầu')
    ranking =models.IntegerField(verbose_name='Loại')
    exchanges = models.CharField(max_length=10, verbose_name= 'Sàn giao dịch')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    # Trường tổng room giá trị cho vay tối đa
    max_loan_value = models.FloatField(default=1000000000, verbose_name="Tổng room giá trị cho vay tối đa")

    class Meta:
         verbose_name = 'Danh mục cho vay'
         verbose_name_plural = 'Danh mục cho vay'

    def __str__(self):
        return str(self.stock)
    
    @property
    def available_loan_value(self):
        # Tính tổng giá trị cổ phiếu đã mua từ Portfolio
        portfolio = Portfolio.objects.filter(stock=self.stock)  # Lọc theo mã cổ phiếu
        now = difine_time_craw_stock_price(datetime.now())
        previous_market_stock_price = (
            StockPriceFilter.objects
            .filter(ticker=self.stock, date__lte=now)
            .filter(Q(close__isnull=False) & Q(close__gt=0))  # Loại bỏ close=None hoặc close=0
            .order_by('-date')
            .first()
            )
        if previous_market_stock_price:
            previous_market_stock_price = previous_market_stock_price.close
            total_stock_value = sum([p.sum_stock * previous_market_stock_price for p in portfolio])  # Tổng giá trị cổ phiếu đã mua
            # Tính giá trị cho vay khả dụng
            available_loan_value = self.max_loan_value - total_stock_value
            return available_loan_value
        else:
            return None
        
        
    
    @property
    def status(self):
        if self.max_loan_value == 0:
            return "KHÔNG CHO VAY"
        
        if self.available_loan_value:
            if self.available_loan_value > 0:
                if self.available_loan_value / self.max_loan_value  < 0.2:
                    status = "CẢNH BÁO đã mua hơn 80% giá trị hạn mức"
                else:
                    status = "BÌNH THƯỜNG"
            else:
                status = "CẢNH BÁO mua vượt hạn mức"
                
            
        else:
            status = "Không tính được số dư hiện tại"

        return status
        

class CashTransfer(models.Model):
    account = models.ForeignKey(Account,on_delete=models.CASCADE,verbose_name = 'Tài khoản' )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date = models.DateField( default=timezone.now,verbose_name = 'Ngày nộp tiền' )
    amount = models.FloatField(verbose_name = 'Số tiền')
    partner = models.ForeignKey(PartnerInfo,on_delete=models.CASCADE,null=True, blank= True,verbose_name="Đối tác")
    description = models.TextField(max_length=255, blank=True,verbose_name = 'Mô tả')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    class Meta:
         verbose_name = 'Giao dịch tiền'
         verbose_name_plural = 'Giao dịch tiền'
    
    def __str__(self):
        return str(self.amount) 
    

    def save(self, *args, **kwargs):
        if self.account.partner:
            self.partner = self.account.partner
    
        super().save(*args, **kwargs)
        # Ghi log khi có hoạt động lưu
        logging.info("save object {} ID {}.".format(self.__class__.__name__, self.id))

    def delete(self, *args, **kwargs):
        # Ghi log khi có hoạt động xóa
        logging.info("delete object {}  ID {}.".format(self.__class__.__name__, self.id))
        super().delete(*args, **kwargs)
    
    

class Transaction (models.Model):
    POSITION_CHOICES = [
        ('buy', 'Mua'),
        ('sell', 'Bán'),
    ]
    account = models.ForeignKey(Account,on_delete=models.CASCADE, null=False, blank=False, verbose_name = 'Tài khoản' )
    partner = models.ForeignKey(PartnerInfo,on_delete=models.CASCADE,null=True, blank= True,verbose_name="Đối tác")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    date = models.DateField( default=timezone.now,verbose_name = 'Ngày giao dịch' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    stock = models.ForeignKey(StockListMargin,on_delete=models.CASCADE, null=False, blank=False, verbose_name = 'Cổ phiếu')
    position = models.CharField(max_length=4, choices=POSITION_CHOICES, null=False, blank=False,verbose_name = 'Mua/Bán')
    price = models.FloatField(verbose_name = 'Giá')
    qty = models.IntegerField(verbose_name = 'Khối lượng')
    transaction_fee = models.FloatField( verbose_name= 'Phí giao dịch')
    tax = models.FloatField(default=0,verbose_name= 'Thuế')
    total_value= models.FloatField(default=0, verbose_name= 'Giá trị giao dịch')
    net_total_value = models.FloatField(default=0, verbose_name= 'Giá trị giao dịch ròng')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    previous_date= models.DateField(null= True, blank=True )
    previous_total_value = models.FloatField(null= True, blank=True)
    

    class Meta:
         verbose_name = 'Sổ lệnh '
         verbose_name_plural = 'Sổ lệnh '

    def __str__(self):
        return self.stock.stock
    
    def __init__(self, *args, **kwargs):
        super(Transaction, self).__init__(*args, **kwargs)
        self._original_date = self.date
        self._original_total_value =self.total_value
    
    def clean(self):
        if self.position == 'sell':
            port = Portfolio.objects.filter(account = self.account, stock =self.stock).first()
            stock_hold  = port.on_hold
            sell_pending = Transaction.objects.filter(pk=self.pk).aggregate(Sum('qty'))['qty__sum'] or 0
            max_sellable_qty =stock_hold  + sell_pending
            if self.qty > max_sellable_qty:
                    raise ValidationError({'qty': f'Không đủ cổ phiếu bán, tổng cổ phiếu khả dụng là {max_sellable_qty}'})        


    def save(self, *args, **kwargs):
        if self.account.partner:
            self.partner = self.account.partner
    
        self.total_value = self.price*self.qty
        self.transaction_fee = self.total_value*self.account.transaction_fee
        if self.position == 'buy':
            self.tax =0    
        else:
            self.tax = self.total_value*self.account.tax
        self.net_total_value = -self.total_value-self.transaction_fee-self.tax
        #lưu giá trị trước chỉnh sửa
        is_new = self._state.adding
        if is_new and self.account.cpd:
            # Nếu là bản ghi mới, gán các giá trị previous bằng các giá trị ban đầu
            self.previous_date = self.date
            self.previous_total_value = self.total_value
        else:
            # Nếu không phải là bản ghi mới, chỉ cập nhật previous khi có sự thay đổi
            self.previous_date = self._original_date
            self.previous_total_value = self._original_total_value
        
        #Kiểm tra trạng thái room cho vay của cổ phiếu
        if "CẢNH BÁO" in self.stock.status:
            message = f"Cổ phiếu {self.stock.stock}, có trạng thái {self.stock.status}"
            send_notification(message)

        super(Transaction, self).save(*args, **kwargs)
        logging.info("save object {} ID {}.".format(self.__class__.__name__, self.id))

    def delete(self, *args, **kwargs):
        # Ghi log khi có hoạt động xóa
        logging.info("delete object {}  ID {}.".format(self.__class__.__name__, self.id))
        super().delete(*args, **kwargs)


        
 
    
class ExpenseStatement(models.Model):
    POSITION_CHOICES = [
        ('interest', 'Lãi vay'),
        ('transaction_fee', 'Phí giao dịch'),
        ('tax', 'Thuế bán'),
        ('advance_fee', 'Phí ứng tiền bán'),
    ]
    account = models.ForeignKey(Account,on_delete=models.CASCADE, null=False, blank=False, verbose_name = 'Tài khoản' )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date =models.DateField( verbose_name = 'Ngày' )
    type =models.CharField(max_length=50, choices=POSITION_CHOICES, null=False, blank=False,verbose_name = 'Loại phí')
    amount = models.FloatField (verbose_name='Số tiền')
    description = models.CharField(max_length=100,null=True, blank=True, verbose_name='Diễn giải')
    interest_cash_balance = models.FloatField (null = True,blank =True ,verbose_name='Số dư tiền tính lãi')
    advance_cash_balance= models.FloatField (null = True,blank =True ,verbose_name='Số dư tiền tính phí ứng')
    transaction_id =models.CharField(max_length= 200,null = True,blank =True ,verbose_name= 'Mã lệnh')
    class Meta:
         verbose_name = 'Bảng kê chi phí '
         verbose_name_plural = 'Bảng kê chi phí '
    
    


    def __str__(self):
        return str(self.type) + str('_')+ str(self.date)
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Ghi log khi có hoạt động lưu
        logging.info("save object {} ID {}.".format(self.__class__.__name__, self.id))

    def delete(self, *args, **kwargs):
        # Ghi log khi có hoạt động xóa
        logging.info("delete object {}  ID {}.".format(self.__class__.__name__, self.id))
        super().delete(*args, **kwargs)

class Portfolio (models.Model):
    account = models.ForeignKey(Account,on_delete=models.CASCADE, null=False, blank=False, verbose_name = 'Tài khoản' )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    stock = models.CharField(max_length=10, verbose_name = 'Cổ phiếu')
    avg_price = models.FloatField(default=0,verbose_name = 'Giá')
    on_hold = models.IntegerField(default=0,null=True,blank=True,verbose_name = 'Khả dụng')
    receiving_t2 = models.IntegerField(default=0,null=True,blank=True,verbose_name = 'Chờ về T2')
    receiving_t1 = models.IntegerField(default=0,null=True,blank=True,verbose_name = 'Chờ về T1')
    cash_divident = models.FloatField(default=0,null=True,blank=True,verbose_name = 'Cổ tức bằng tiền')
    stock_divident =models.IntegerField(default=0,null=True,blank=True,verbose_name = 'Cổ tức cổ phiếu')
    market_price = models.FloatField(default=0,null=True,blank=True,verbose_name = 'Giá thị trường')
    profit = models.FloatField(default=0,null=True,blank=True,verbose_name = 'Lợi nhuận')
    percent_profit = models.FloatField(default=0,null=True,blank=True,verbose_name = '%Lợi nhuận')
    sum_stock =models.IntegerField(default=0,null=True,blank=True,verbose_name = 'Tổng cổ phiếu')
    market_value = models.FloatField(default=0,null=True,blank=True,verbose_name = 'Giá trị thị trường')
    partner = models.ForeignKey(PartnerInfo,on_delete=models.CASCADE,null=True, blank= True,verbose_name="Đối tác")
    
    class Meta:
         verbose_name = 'Danh mục '
         verbose_name_plural = 'Danh mục '

    def __str__(self):
        return self.stock
    
    
    def save(self, *args, update_avg_price=True, **kwargs):
        if self.account.partner:
            self.partner = self.account.partner
        self.sum_stock = self.receiving_t2+ self.receiving_t1+self.on_hold 
        self.profit =0
        self.percent_profit = 0
        if self.sum_stock >0:
            if update_avg_price and self.market_price==0:
                self.market_price = get_stock_market_price(str(self.stock))
            else:
                market_price = StockPriceFilter.objects.filter(ticker=self.stock).order_by('-date').first()
                self.market_price = market_price.close if market_price else 0
            if self.account.milestone_date_lated:
                date_cal = self.account.milestone_date_lated
            else:
                date_cal = self.account.created_at
            if update_avg_price:  # Chỉ tính avg_price khi được phép
                self.avg_price = round(cal_avg_price(self.account.pk, self.stock, date_cal), 0)
            self.profit = round((self.market_price - self.avg_price)*self.sum_stock,0)
            self.percent_profit = round((self.market_price/self.avg_price-1)*100,2)
            self.market_value = self.market_price*self.sum_stock
        super(Portfolio, self).save(*args, **kwargs)
        logging.info("save object {} ID {}.".format(self.__class__.__name__, self.id))

    def delete(self, *args, **kwargs):
        # Ghi log khi có hoạt động xóa
        logging.info("delete object {}  ID {}.".format(self.__class__.__name__, self.id))
        super().delete(*args, **kwargs)
