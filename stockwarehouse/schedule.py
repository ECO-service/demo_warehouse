from operation.processing import *
# from infotrading.models import get_all_info_stock_price
from stockwarehouse.backup import run_database_backup
from datetime import datetime



def schedule_morning():
    today = datetime.now().date()
    weekday = today.weekday() 
    check_in_dates =  DateNotTrading.objects.filter(date=today).exists()
    if not (check_in_dates or weekday == 5 or weekday == 6):
        try:
            check_dividend_recevie()
        except Exception as e_check_dividend:
            print(f"An error occurred while running check_dividend: {e_check_dividend}")
        
        try:
            pay_money_back()
        except Exception as e_auto_news:
            print(f"An error occurred while running auto_news_stock_worlds: {e_auto_news}")

    else:
        pass



def schedule_mid_trading_date():
    today = datetime.now().date()
    weekday = today.weekday() 
    check_in_dates =  DateNotTrading.objects.filter(date=today).exists()
    if not (check_in_dates or weekday == 5 or weekday == 6):
        
        try:
            atternoon_check()
            
        except Exception as e_afternoon_check:
            print(f"An error occurred while running atternoon_check: {e_afternoon_check}")
        
        try:
            check_dividend_recevie()
        except Exception as e_get_info_stock:
            print(f"An error occurred while running get_info_stock_price_filter: {e_get_info_stock}")

    else:
        pass

def run_get_list_and_save_stock_price():
    stock_list = Portfolio.objects.values_list('stock', flat=True).distinct()
    stock_list_python = list(stock_list)
    get_list_and_save_stock_price(stock_list_python)

def get_info_stock_price_filter():
    today = datetime.now().date()
    not_trading_dates = DateNotTrading.objects.filter(date=today)
    if not not_trading_dates:
        try:
            # Get distinct stocks where sum_stock > 0
            run_get_list_and_save_stock_price()
        except Exception as e_afternoon_check:
            print(f"An error occurred while running atternoon_check: {e_afternoon_check}")
    else:
        pass


