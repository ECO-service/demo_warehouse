import json
from bs4 import BeautifulSoup
from django.db import models
from datetime import datetime, timedelta, time
import yfinance as yf
import requests
import concurrent.futures
import random

# Create your models here.


class StockPriceFilter(models.Model):
    ticker = models.CharField(max_length=10)
    date = models.DateField()#auto_now_add=True)
    close = models.FloatField()
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
    # date_item = DateNotTrading.objects.filter(date__gte=date_time)
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



def cophieu68_get_market_price(stock):
    linkbase = 'https://www.cophieu68.vn/quote/summary.php?id=' + stock
    r = requests.get(linkbase)
    r.raise_for_status()  # Check for HTTP errors
    soup = BeautifulSoup(r.text, 'html.parser')
    div_tag = soup.find('div', id='stockname_close')
    return float(div_tag.text) * 1000

def yahoo_get_market_price(stock: str):
    """Lấy giá gần nhất của cổ phiếu trên sàn HOSE từ Yahoo Finance."""
    full_symbol = f"{stock}.VN"  # Tự động thêm .VN
    try:
        stock = yf.Ticker(full_symbol)
        return stock.fast_info["last_price"]
    except Exception as e:
        print(f"Lỗi khi lấy giá {full_symbol}: {e}")
        return None

def pinetree_get_stock_prices():
    base_url = "https://trade.pinetree.vn/getliststockById/{:02d}?board=G1"
    all_data = []
    seen_stocks = set()  # Dùng set để theo dõi các stock đã gặp
    
    # Sử dụng Session để tối ưu hóa kết nối
    with requests.Session() as session:
        for i in [1, 2, 10]:  # Lặp qua các số 1, 2, 10 thay vì 1, 2, 3
            url = base_url.format(i)
            try:
                response = session.get(url)
                response.raise_for_status()  # Kiểm tra lỗi HTTP
                data = response.json()
                
                # Duyệt qua các cổ phiếu trong data và chỉ thêm những cổ phiếu chưa gặp
                for stock in data:
                    stock_data = {"stock": stock["sym"], "price": stock["lastPrice"] * 1000}
                    
                    # Kiểm tra nếu stock đã tồn tại trong seen_stocks
                    if stock_data["stock"] not in seen_stocks:
                        all_data.append(stock_data)
                        seen_stocks.add(stock_data["stock"])  # Thêm stock vào set đã gặp
                
            except requests.exceptions.RequestException as e:
                print(f"Lỗi request {url}: {e}")
            except ValueError as e:
                print(f"Lỗi JSON từ {url}: {e}")
    
    return all_data





def bvsc_get_stock_prices():
    # Danh sách các URL cần lấy dữ liệu
    urls = [
        "https://online.bvsc.com.vn/datafeed/instruments?exchange=HOSE",
        "https://online.bvsc.com.vn/datafeed/instruments?exchange=HNX",
        "https://online.bvsc.com.vn/datafeed/instruments?exchange=UPCOM"
    ]
    
    all_data = []
    seen_stocks = set()  # Dùng set để theo dõi các stock đã gặp
    
    # Sử dụng Session để tối ưu hóa kết nối
    with requests.Session() as session:
        for url in urls:
            try:
                response = session.get(url)
                response.raise_for_status()  # Kiểm tra lỗi HTTP
                data = response.json()
                
                for stock in data.get("d", []):  # Lấy từ key "d"
                    stock_data = {"stock": stock["symbol"], "price": stock["closePrice"]}
                    
                    # Kiểm tra nếu stock đã tồn tại trong seen_stocks
                    if stock_data["stock"] not in seen_stocks:
                        all_data.append(stock_data)
                        seen_stocks.add(stock_data["stock"])  # Thêm stock vào set đã gặp
                
            except requests.exceptions.RequestException as e:
                print(f"Lỗi request {url}: {e}")
            except ValueError as e:
                print(f"Lỗi JSON từ {url}: {e}")
    
    return all_data

def vps_get_stock_price(stock):
    url = f"https://bgapidatafeed.vps.com.vn/getliststockdata/{stock}"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        try:
            data = response.json()  # Parse JSON response
            if data:
                stock_info = data[0]  # Assuming the response is a list with one dictionary
                # sym = stock_info.get("sym")
                last_price = stock_info.get("lastPrice")*1000
                return last_price
            else:
                return {"error": "No data found"}
        except ValueError:
            return {"error": "Error parsing JSON"}
    else:
        return {"error": f"Request failed with status code {response.status_code}"}


def return_json_data(data):
    data_dict = json.loads(data)
    data_list = data_dict['data']
    return data_list


def get_dividend_data():
    # Tính toán ngày hôm nay và ngày kế tiếp +7 ngày
    today = datetime.today()
    end_date = today + timedelta(days=7)
    
    # Chuyển đổi ngày sang định dạng YYYY-MM-DD
    start_date = today.strftime('%Y-%m-%d')
    end_date = end_date.strftime('%Y-%m-%d')
    
    url = f"https://api-finfo.vndirect.com.vn/v4/events?q=effectiveDate:gte:{start_date}~effectiveDate:lte:{end_date}~locale:VN&size=10000"

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Origin': 'https://banggia.vndirect.com.vn',
        'Pragma': 'no-cache',
        'Referer': 'https://banggia.vndirect.com.vn/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0',
        'sec-ch-ua': '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

    # Tạo session để duy trì kết nối
    with requests.Session() as session:
        session.headers.update(headers)  # Cập nhật header vào session
        
        # Gửi yêu cầu GET
        response = session.get(url)
        
        if response.status_code == 200:
            try:
                data = response.json()  # Phân tích JSON trả về
                dividend_data = []
                
                # Lọc các sự kiện có type là "DIVIDEND" và lấy code và effectiveDate
                for item in data.get("data", []):
                    if item.get("type") == "DIVIDEND":
                        dividend_data.append({
                            "code": item.get("code"),
                            "effectiveDate": item.get("effectiveDate")
                        })
                
                return dividend_data  # Trả về dữ liệu lọc theo yêu cầu
                
            except ValueError:
                return {"error": "Lỗi khi phân tích dữ liệu JSON"}
        else:
            return {"error": f"Yêu cầu thất bại với mã lỗi {response.status_code}"}
        

def get_stock_market_price(stock):
    """Lấy giá cổ phiếu từ các API với thứ tự ngẫu nhiên và timeout 5s mỗi API."""

    def fetch_with_timeout(func, stock, timeout=5):
        """Gọi API với timeout, trả về None nếu hết thời gian."""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(func, stock)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                return None

    # Danh sách API lấy giá cổ phiếu, xáo trộn thứ tự mỗi lần chạy
    sources = [
        ("Cophieu68", cophieu68_get_market_price),
        ("Yahoo Finance", yahoo_get_market_price),
        ("VPS", vps_get_stock_price)
    ]
    random.shuffle(sources)  # Xáo trộn thứ tự mỗi lần chạy

    # Thử từng API với timeout 5s
    for source_name, func in sources:
        print(f"🟡 Đang lấy giá từ: {source_name}...")
        price = fetch_with_timeout(func, stock, timeout=5)
        if price is not None:
            print(f"✅ Giá lấy từ {source_name}: {price}")
            return price  # Trả về ngay khi có giá hợp lệ
        else:
            print(f"❌ {source_name} không trả về giá hoặc bị timeout.")

    print("⚠️ Không thể lấy giá từ bất kỳ nguồn nào.")
    return None  # Trả về None nếu tất cả API đều thất bại 


def get_list_and_save_stock_price(list_stock):
    
    """Lấy danh sách giá cổ phiếu và lưu vào cơ sở dữ liệu."""
    date_time = difine_time_craw_stock_price(datetime.now())  # Xác định thời gian crawl

    def fetch_with_timeout(func, *args, timeout=5):
        """Chạy hàm với timeout, trả về None nếu quá thời gian."""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(func, *args)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                return None

    # 1️⃣ Thử lấy dữ liệu từ danh sách nguồn trước (pinetree, bvsc)
    stock_price_sources = [
        ("Pinetree", pinetree_get_stock_prices),
        ("BVSC", bvsc_get_stock_prices)
    ]
    random.shuffle(stock_price_sources)  # Ngẫu nhiên hóa thứ tự gọi API

    filtered_stocks = []
    for source_name, func in stock_price_sources:
        print(f"🟡 Đang lấy danh sách giá cổ phiếu từ: {source_name}...")
        data = fetch_with_timeout(func, timeout=5)
        if data:
            filtered_stocks = [
                {'stock': item['stock'], 'price': item['price']}
                for item in data if item['stock'] in list_stock
            ]
            if filtered_stocks:
                print(f"✅ Lấy thành công từ {source_name}.")
                break  # Nếu có dữ liệu, dừng thử nguồn tiếp theo
        print(f"❌ Không thể lấy dữ liệu từ {source_name}.")

    # 2️⃣ Nếu chưa có dữ liệu, thử lấy từng cổ phiếu từ các API riêng lẻ
    if not filtered_stocks:
        stock_price_sources = [
            ("Cophieu68", cophieu68_get_market_price),
            ("Yahoo Finance", yahoo_get_market_price),
            ("VPS", vps_get_stock_price)
        ]
        random.shuffle(stock_price_sources)  # Ngẫu nhiên hóa thứ tự ưu tiên

        for stock in list_stock:
            for source_name, func in stock_price_sources:
                print(f"🟡 Đang lấy giá {stock} từ: {source_name}...")
                price = fetch_with_timeout(func, stock, timeout=5)
                if price:
                    filtered_stocks.append({'stock': stock, 'price': price})
                    print(f"✅ Giá {stock} từ {source_name}: {price}")
                    break  # Nếu lấy được giá, dừng thử tiếp
                print(f"❌ {source_name} không có giá cho {stock} hoặc bị timeout.")

    # 3️⃣ Cập nhật hoặc tạo mới bản ghi trong cơ sở dữ liệu
    if filtered_stocks:
        for stock in filtered_stocks:
            ticker = stock.get('stock')
            date = date_time.date()
            price = stock.get('price')

            StockPriceFilter.objects.update_or_create(
                ticker=ticker,
                date=date,
                defaults={'close': price, 'date_time': date_time},
            )

    return filtered_stocks