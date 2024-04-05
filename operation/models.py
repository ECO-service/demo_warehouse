import re
from django.db import models
from django.db.models.signals import post_save, post_delete,pre_save, pre_delete
from django.contrib.auth.models import User, Group
from django.dispatch import receiver
from datetime import datetime, timedelta
from django.forms import ValidationError
import requests
from bs4 import BeautifulSoup
from infotrading.models import DateNotTrading, StockPriceFilter, DividendManage, get_stock_price_tpbs
from django.db.models import Sum
from django.utils import timezone
from telegram import Bot
from django.db.models import Q
from cpd.models import *
from django.contrib.auth.hashers import make_password
from regulations.models import *
from accfifo import Entry, FIFO
import asyncio



maintenance_margin_ratio = OperationRegulations.objects.get(pk=4).parameters
force_sell_margin_ratio = OperationRegulations.objects.get(pk=5).parameters
# maintenance_margin_ratio =17
# force_sell_margin_ratio =13

def get_default_parameters(pk):
    try:
        return OperationRegulations.objects.get(pk=pk).parameters
    except OperationRegulations.DoesNotExist:
        # Trả về giá trị mặc định nếu không tìm thấy đối tượng
        return 0.0  # hoặc giá trị mặc định của bạn

def get_interest_fee_default():
    return get_default_parameters(pk=3)

def get_transaction_fee_default():
    return get_default_parameters(pk=1)

def get_tax_fee_default():
    return get_default_parameters(pk=2)

def get_credit_limit_default():
    return get_default_parameters(pk=6)

async def send_notification(bot,chat_id,noti):
    # Mã khởi tạo bot và các mã khác ở đây
    chat_id =chat_id 
    text = noti
    # Sử dụng await để thực hiện coroutine
    await bot.send_message(chat_id=chat_id, text=text)

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

def total_value_inventory_stock(account,ratio_trading_fee, stock, start_date, end_date,partner=None):
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
        total_value += quantity * price *(1+ratio_trading_fee)
    return total_value


def get_stock_market_price(stock):
    linkbase = 'https://www.cophieu68.vn/quote/summary.php?id=' + stock
    try:
        # Attempt to get stock price from the primary source
        r = requests.get(linkbase)
        r.raise_for_status()  # Check for HTTP errors
        soup = BeautifulSoup(r.text, 'html.parser')
        div_tag = soup.find('div', id='stockname_close')
        if div_tag is not None:
            return float(div_tag.text) * 1000
        else:
            print(f"Cổ phiếu 68 không có cổ phiếu")
            list_stock = []
            list_stock.append(stock)
            price = get_stock_price_tpbs(list_stock)[1]
            return price   
    except requests.exceptions.RequestException as primary_exception:
        try:
            print(f"lỗi truy cập cổ phiếu 68")
            list_stock = []
            list_stock.append(stock)
            price = get_stock_price_tpbs(list_stock)[1]
            return price
        except Exception as alternative_exception:
            print(f"Lỗi truy cập TPBS: {alternative_exception}")
            return 0
    
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
    method_interest =models.CharField(max_length=100,null=True,blank=True, choices=method_interest,verbose_name = 'Phương thức tính lãi')
    class Meta:
        verbose_name = 'Đăng kí đối tác'
        verbose_name_plural = 'Đăng kí đối tác'

    def __str__(self):
        return str(self.name) + '_' + str(self.pk)
    

# nếu sau này 1 partner có nhiều đối tác, cần chuyển models realstockaccount qua đây, gán trasaction và banktransfer với realstockacount thay vì trực tiếp partner
# Create your models here.
class Account (models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name= 'Tên Khách hàng')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    description = models.TextField(max_length=255, blank=True, verbose_name= 'Mô tả')
    cpd = models.ForeignKey(ClientPartnerInfo,null=True, blank = True,on_delete=models.CASCADE, verbose_name= 'Người giới thiệu' )
    #biểu phí dịch vụ
    interest_fee = models.FloatField(default=get_interest_fee_default, verbose_name='Lãi suất')
    transaction_fee = models.FloatField(default=get_transaction_fee_default, verbose_name='Phí giao dịch')
    tax = models.FloatField(default=get_tax_fee_default, verbose_name='Thuế')
    # interest_fee = models.FloatField(default=0, verbose_name='Lãi suất')
    # transaction_fee = models.FloatField(default=0, verbose_name='Phí giao dịch')
    # tax = models.FloatField(default=0, verbose_name='Thuế')
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
    credit_limit = models.FloatField(default=get_credit_limit_default, verbose_name='Hạn mức mua')
    # credit_limit = models.FloatField(default=1000000000, verbose_name='Hạn mức mua')
    milestone_date_lated = models.DateTimeField(null =True, blank =True, verbose_name = 'Ngày tất toán gần nhất')
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
        value_force = round((maintenance_margin_ratio - self.margin_ratio)*self.market_value/100,0)
        value_force_str = '{:,.0f}'.format(value_force)
        status = ""
        port = Portfolio.objects.filter(account_id = self.pk, sum_stock__gt=0).first()
        if port:
            price_force_sell = round(-self.cash_balance/( 0.87* port.sum_stock),0)
            if abs(self.cash_balance) >1000 and value_force !=0:
                if check <= maintenance_margin_ratio and check >force_sell_margin_ratio:
                    status = f"CẢNH BÁO, số âm {value_force_str}, giá bán {port.stock}: {'{:,.0f}'.format(price_force_sell)}"
                elif check <= force_sell_margin_ratio:
                    status = f"GIẢI CHẤP {'{:,.0f}'.format(value_force*5)}, giá bán {port.stock}:\n{'{:,.0f}'.format(price_force_sell)}"

                return status
   
    
    def save(self, *args, **kwargs):
    # Your first save method code
        self.total_loan_interest = self.total_temporarily_interest + self.total_interest_paid
        self.total_advance_fee = self.total_temporarily_advance_fee + self.total_advance_fee_paid
        self.cash_balance = self.net_cash_flow + self.net_trading_value + self.total_temporarily_interest + self.total_temporarily_advance_fee
        stock_mapping = {obj.stock: obj.initial_margin_requirement for obj in StockListMargin.objects.all()}
        port = Portfolio.objects.filter(account=self.pk, sum_stock__gt=0)
        sum_initial_margin = 0
        market_value = 0
        if port:
            for item in port:
                initial_margin = stock_mapping.get(item.stock, 0) * item.sum_stock * item.avg_price / 100
                sum_initial_margin += initial_margin
                market_value += item.market_value
        self.margin_ratio = 0
        self.market_value = market_value
        self.nav = self.market_value + self.cash_balance
        self.initial_margin_requirement = sum_initial_margin
        self.excess_equity = self.nav - self.initial_margin_requirement
        self.advance_cash_balance = (self.cash_t1 + self.cash_t2)*-1
        if self.market_value != 0:
            self.margin_ratio = abs(round((self.nav / self.market_value) * 100, 2))
        self.total_temporarily_pl= self.nav - self.net_cash_flow
        self.total_pl  = self.total_temporarily_pl + self.total_closed_pl
        bot = Bot(token='5806464470:AAH9bLZxhx6xXDJ9rlPKkhaJ6lKpKRrZEfA')
        chat_id ='-4055438156'
        # if self.status:
        #     noti = f"Tài khoản {self.pk}, tên {self.name} bị {self.status} "
        #     asyncio.run(send_notification(bot,chat_id,noti))

        # Your second save method code
        super(Account, self).save(*args, **kwargs)

        # Additional code from the second save method
        # ...

        # Tạo hoặc cập nhật User
        user, created = User.objects.get_or_create(username=str(self.pk))
        if created:
            user.set_password("20241q2w3e4r")
            user.save()

            # Thêm user vào nhóm "customer"
            group, created = Group.objects.get_or_create(name='customer')
            user.groups.add(group)

#Tạo model với các ngăn tất toán của tài khoản
class AccountMilestone(models.Model):
    account = models.ForeignKey(Account,on_delete=models.CASCADE,verbose_name="Tài khoản")
    milestone = models.IntegerField(verbose_name = 'Giai đoạn')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    description = models.TextField(max_length=255, blank=True, verbose_name= 'Mô tả')
    interest_fee = models.FloatField(default=0.16, verbose_name='Lãi suất')
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
    class Meta:
         verbose_name = 'Danh mục cho vay'
         verbose_name_plural = 'Danh mục cho vay'

    def __str__(self):
        return str(self.stock)

class CashTransfer(models.Model):
    account = models.ForeignKey(Account,on_delete=models.CASCADE,verbose_name = 'Tài khoản' )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    date = models.DateField( default=timezone.now,verbose_name = 'Ngày nộp tiền' )
    amount = models.FloatField(verbose_name = 'Số tiền')
    description = models.TextField(max_length=255, blank=True,verbose_name = 'Mô tả')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,null=True, blank= True,                   verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,
                             verbose_name="Người chỉnh sửa")
    class Meta:
         verbose_name = 'Giao dịch tiền'
         verbose_name_plural = 'Giao dịch tiền'
    
    def __str__(self):
        return str(self.amount) 
    
    

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
        if self.price < 0: 
            raise ValidationError('Lỗi giá phải lớn hơn 0')
          
        if self.position == 'sell':
            port = Portfolio.objects.filter(account = self.account, stock =self.stock).first()
            stock_hold  = port.on_hold
            sell_pending = Transaction.objects.filter(pk=self.pk).aggregate(Sum('qty'))['qty__sum'] or 0
            max_sellable_qty =stock_hold  + sell_pending
            if self.qty > max_sellable_qty:
                    raise ValidationError({'qty': f'Không đủ cổ phiếu bán, tổng cổ phiếu khả dụng là {max_sellable_qty}'})        

    @property
    def partner_net_total_value(self):
        ratio_transaction_fee = self.partner.ratio_trading_fee
        partner_transaction_fee = self.total_value * ratio_transaction_fee
        if self.position == 'buy':
            partner_net_total_value = -self.total_value - partner_transaction_fee - self.tax
        else:
            partner_net_total_value = self.total_value - self.tax - partner_transaction_fee
        return partner_net_total_value           

    def save(self, *args, **kwargs):
        self.total_value = self.price*self.qty
        self.transaction_fee = self.total_value*self.account.transaction_fee
        if self.position == 'buy':
            self.tax =0
            self.net_total_value = -self.total_value-self.transaction_fee-self.tax
        else:
            self.tax = self.total_value*self.account.tax
            self.net_total_value = self.total_value-self.transaction_fee-self.tax
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

        super(Transaction, self).save(*args, **kwargs)


        
 
    
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
    class Meta:
         verbose_name = 'Danh mục '
         verbose_name_plural = 'Danh mục '

    def __str__(self):
        return self.stock
    
    def save(self, *args, **kwargs):
        self.sum_stock = self.receiving_t2+ self.receiving_t1+self.on_hold 
        self.profit =0
        self.percent_profit = 0
        if self.sum_stock >0:
            self.market_price = round(get_stock_market_price(str(self.stock)),0)
            if self.account.milestone_date_lated:
                date_cal = self.account.milestone_date_lated
            else:
                date_cal = self.account.created_at
            self.avg_price = round(cal_avg_price(self.account.pk,self.stock,date_cal ),0)
            self.profit = round((self.market_price - self.avg_price)*self.sum_stock,0)
            self.percent_profit = round((self.market_price/self.avg_price-1)*100,2)
            self.market_value = self.market_price*self.sum_stock
        super(Portfolio, self).save(*args, **kwargs)



   