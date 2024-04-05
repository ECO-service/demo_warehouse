import json
from django.db import models
from datetime import datetime, timedelta, time

import requests

# Create your models here.

    
class StockPriceFilter(models.Model):
    ticker = models.CharField(max_length=10)
    date = models.DateField()#auto_now_add=True)
    open = models.FloatField()
    high =models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    volume =models.FloatField()
    date_time = models.DateTimeField(null=True, blank=True)
    class Meta:
         verbose_name = 'Giá thị trường'
         verbose_name_plural = 'Giá thị trường'
    def __str__(self):
        return str(self.ticker) + str(self.date)
    
class DateNotTrading(models.Model):
    date = models.DateField(unique=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    description = models.TextField(max_length=255, blank=True)
    def __str__(self):
        return str(self.date) 
    class Meta:
         verbose_name = 'Ngày lễ không giao dịch'
         verbose_name_plural = 'Ngày lễ không giao dịch'
    
class DividendManage(models.Model):
    DIVIDEND_CHOICES = [
        ('cash', 'cash'),
        ('stock', 'stock'),
        ('option','option'),
        ('order','order'),

    ]
    stock =  models.CharField(max_length=20,verbose_name = 'Cổ phiếu')
    type = models.CharField(max_length=20, choices=DIVIDEND_CHOICES, null=False, blank=False)
    date_apply = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now=True, verbose_name = 'Ngày chỉnh sửa' )
    cash = models.FloatField( default=0)
    stock = models.FloatField( default=0)
    price_option = models.FloatField(default=0)
    stock_option = models.FloatField(default=0)
    
    class Meta:
         verbose_name = 'Quản lí cổ tức'
         verbose_name_plural = 'Quản lí cổ tức'
    def __str__(self):
        return str(self.ticker) +str("_")+ str(self.date_apply)

def difine_time_craw_stock_price(date_time):
    date_item = DateNotTrading.objects.filter(date__gte=date_time)
    weekday = date_time.weekday()
    old_time = date_time.time()
    date_time=date_time.date()
    if weekday == 6:  # Nếu là Chủ nhật
        date_time = date_time - timedelta(days=2)  # Giảm 2 ngày
    elif weekday == 5:  # Nếu là thứ 7
        date_time = date_time - timedelta(days=1)  # Giảm 1 ngày
    weekday = date_time.weekday()
    while True:
        if DateNotTrading.objects.filter(date=date_time).exists() or weekday == 6 or weekday == 5 :  # Nếu là một ngày trong danh sách không giao dịch
            date_time = date_time - timedelta(days=1)  # Giảm về ngày liền trước đó
        else:
            break
        weekday = date_time.weekday()  # Cập nhật lại ngày trong tuần sau khi thay đổi time
    if old_time < time(14, 45, 0) and old_time > time(9, 00, 0):
        new_time = old_time
    else:
        new_time = time(14, 45, 0)
    return datetime.combine(date_time, new_time)


def get_list_stock_price(list_stock):
    # list_stock = list(Transaction.objects.values_list('stock', flat=True).distinct())
    number =len(list_stock)
    linkstockquote ='https://price.tpbs.com.vn/api/SymbolApi/getStockQuote'
    r = requests.post(linkstockquote,json = {"stocklist" : list_stock })
    b= json.loads(r.text)
    a = json.loads(b['content'])
    date_time = datetime.now()
    date_time = difine_time_craw_stock_price(date_time)
    for i in range (0,len(a)):
        ticker=a[i]['sym']
        open=float(a[i]['ope'].replace(',', ''))
        low_price=float(a[i]['low'].replace(',', ''))
        high_price = float(a[i]['hig'].replace(',', ''))
        close=float(a[i]['mat'].replace(',', ''))
        volume=float(a[i]['tmv'].replace(',', '') )*10
        StockPriceFilter.objects.update_or_create(
                ticker=ticker,
                date= date_time.date(),
            defaults={
           'low': low_price,
            'high': high_price,
            'open':open,
            'close': close,
            'volume': volume,
            'date_time':date_time
                        } )
    return StockPriceFilter.objects.all().order_by('-date')[:number]


def get_stock_price_tpbs(list_stock):
    # list_stock = list(Transaction.objects.values_list('stock', flat=True).distinct())
    number =len(list_stock)
    linkstockquote ='https://price.tpbs.com.vn/api/SymbolApi/getStockQuote'
    r = requests.post(linkstockquote,json = {"stocklist" : list_stock })
    b= json.loads(r.text)
    a = json.loads(b['content'])
    for i in range (0,len(a)):
        ticker=a[i]['sym']
        close=float(a[i]['mat'].replace(',', ''))
    return ticker,close*1000
