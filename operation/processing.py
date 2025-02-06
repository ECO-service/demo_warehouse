from .models import *
from partner.models import *
from django.db.models import Sum, Case, When, F, Value, IntegerField



def real_stock_account_when_update_transaction(partner):
    # Tìm hoặc tạo một tài khoản RealStockAccount cho đối tác
    if partner.method_interest == 'dept':
        real_stock, created = RealStockAccount.objects.get_or_create(partner=partner)
        # Lấy tất cả các tài khoản của đối tác
        all_account = AccountPartner.objects.filter(partner=partner).exclude(nav=0)
        # Tính toán các giá trị tài khoản thực sự
        cash_balance_open_account = sum(item.cash_balance  for item in all_account)
        interest_cash_balance = sum(item.cash_t0 +item.total_buy_trading_value +item.net_cash_flow for item in all_account)
        market_value = sum(item.market_value for item in all_account)
        # Cập nhật các trường trong tài khoản RealStockAccount
        real_stock.cash_balance_open_account = cash_balance_open_account
        real_stock.market_value = market_value
        real_stock.interest_cash_balance = interest_cash_balance-real_stock.milestone_cash_t1 -real_stock.milestone_cash_t2 +real_stock.net_cash_flow_operation-570765#phí lãi tất toán của tháng 2
        real_stock.save()


        
def update_or_created_expense_partner(instance,account_partner, description_type):
    if description_type=='tax':
        amount = instance.tax*-1
        description = f"Thuế với lệnh bán {instance.stock} số lượng {"{:,.0f}".format(instance.qty)} và giá {"{:,.0f}".format(instance.price)} "
    elif description_type== 'transaction_fee':
        ratio_transaction_fee = instance.partner.ratio_trading_fee
        amount = -instance.total_value*ratio_transaction_fee
        description = f"PGD phát sinh với lệnh {instance.position} {instance.stock} số lượng {"{:,.0f}".format(instance.qty)} và giá {"{:,.0f}".format(instance.price) } "
    elif description_type== 'advance_fee':
        partner = instance.partner
        ratio_interest_fee = partner.ratio_interest_fee
        total_date_interest =partner.total_date_interest
        number_interest = define_date_receive_cash(instance.date,2)[1]
        amount = -ratio_interest_fee *instance.total_value*number_interest /total_date_interest  
        description = f"TK {account_partner} tính phí ứng tiền bán cho {number_interest} ngày, số dư tính phí là {"{:,.0f}".format(instance.total_value)}"
                
    ExpenseStatementPartner.objects.update_or_create(
        transaction_id=instance.pk,
        type=description_type,
        defaults={
            'account': account_partner,
            'date': instance.date,
            'amount': amount,
            'description': description,
    
        }
    )


def define_t_plus(initial_date, date_milestone):
    try:
        if date_milestone >= initial_date:
            t = 0
            check_date = initial_date 
            max_iterations = (date_milestone - check_date).days   # Số lần lặp tối đa để tránh vòng lặp vô tận
            for _ in range(max_iterations + 1):  
                check_date += timedelta(days=1)
                if check_date > date_milestone or t==2:
                    break  # Nếu đã vượt qua ngày mốc, thoát khỏi vòng lặp
                weekday = check_date.weekday() 
                check_in_dates =  DateNotTrading.objects.filter(date=check_date).exists()
                if not (check_in_dates or weekday == 5 or weekday == 6):
                    t += 1
            return t
        else:
            print(f'Lỗi: date_milestone không lớn hơn hoặc bằng initial_date')
    except Exception as e:
        print(f'Lỗi: {e}')

def created_transaction_partner(instance,account,date_mileston):
    partner = instance.partner
 
    account_partner , created= AccountPartner.objects.get_or_create(
        account=account,
        partner=partner,
        defaults={'description': ''}  # Trường 'description' không bị cập nhật
    )
    if account_partner.milestone_date_lated:
        date_mileston_apply = account_partner.milestone_date_lated
    else:
        date_mileston_apply = date_mileston
    # tạo phí giao dịch
    update_or_created_expense_partner(instance,account_partner, description_type='transaction_fee')
    if instance.position == 'buy':
        #điều chỉnh account partner
        account_partner.net_trading_value += instance.partner_net_total_value # Dẫn tới thay đổi cash_balace, nav, pl
        account_partner.total_buy_trading_value+= instance.partner_net_total_value #Dẫn tới thay đổi interest_cash_balance 
        if partner.method_interest == 'total_buy_value':    
            account_partner.interest_cash_balance += instance.partner_net_total_value
        try:
            portfolio_partner = PortfolioPartner.objects.get(stock=instance.stock, account=account_partner)
            # Nếu đối tượng tồn tại, điều chỉnh danh mục
            portfolio_partner.receiving_t2 += instance.qty
            portfolio_partner.save()
        except PortfolioPartner.DoesNotExist:
            # Nếu không tìm thấy, tạo danh mục mới
            PortfolioPartner.objects.create(
                stock=instance.stock,
                account=account_partner,
                receiving_t2=instance.qty,
            )
        
    elif instance.position == 'sell':
        # điều chỉnh danh mục
        portfolio_partner = PortfolioPartner.objects.get(stock=instance.stock, account=account_partner)
        portfolio_partner.on_hold = portfolio_partner.on_hold -instance.qty
        portfolio_partner.save()
        #điều chỉnh account_partner
        end_date = datetime.now().date()
        account_partner.net_trading_value += instance.partner_net_total_value # Dẫn tới thay đổi cash_balace, nav, pl
        if partner.method_interest == 'total_buy_value':
            account_partner.cash_t2 += instance.total_value #Dẫn tới thay đổi cash_t0 trong tương lai và thay đổi interest_cash_balance 
            account_partner.interest_cash_balance =define_interest_cash_balace(account_partner.account, date_mileston_apply, end_date,account_partner)
        else:
            account_partner.cash_t2 += instance.partner_net_total_value
        update_or_created_expense_partner(instance,account_partner, description_type='tax')
        # tạo phí ứng
        if partner.method_interest == 'total_buy_value':
            update_or_created_expense_partner(instance,account_partner, description_type='advance_fee')
    
    account_partner.save()

def partner_update_transaction(instance,date_mileston):
    account_partner = AccountPartner.objects.get(account=instance.account, partner=instance.partner)
    if account_partner.milestone_date_lated:
        date_mileston_apply = account_partner.milestone_date_lated
    else:
        date_mileston_apply = date_mileston
    transaction = Transaction.objects.filter(account = instance.account,partner =instance.partner,created_at__gt = date_mileston_apply)
    # sửa chi phí
    update_or_created_expense_partner(instance,account_partner, description_type='transaction_fee')
    if instance.position == 'sell':
        update_or_created_expense_partner(instance,account_partner, description_type='tax')
        # bổ sung phí ứng
        if instance.partner.method_interest == 'total_buy_value':
            update_or_created_expense_partner(instance,account_partner, description_type='advance_fee')
    # sửa danh mục
    portfolio_partner = PortfolioPartner.objects.filter(stock =instance.stock, account= account_partner).first()
    stock_transaction = transaction.filter(stock = instance.stock)
    sum_sell = sum(item.qty for item in stock_transaction if item.position =='sell')
    item_buy = stock_transaction.filter( position = 'buy')
    
    if portfolio_partner:
        receiving_t2,receiving_t1,on_hold =0,0,0
        today  = datetime.now().date()      
        for item in item_buy:
            if define_t_plus(item.date, today) == 0:
                receiving_t2 += item.qty                           
            elif define_t_plus(item.date, today) == 1:
                receiving_t1 += item.qty                             
            else:
                on_hold += item.qty

        on_hold = on_hold - sum_sell
                                           
        portfolio_partner.receiving_t2 = receiving_t2
        portfolio_partner.receiving_t1 = receiving_t1
        portfolio_partner.on_hold = on_hold
        portfolio_partner.save()
    # sửa tài khoản    
    item_all_sell = transaction.filter(position = 'sell')
    cash_t0, cash_t1, cash_t2 =0,0,0
    total_value_buy= sum(i.net_total_value for i in transaction if i.position =='buy')
    today  = datetime.now().date()  
    if item_all_sell:
        for item in item_all_sell:
            if define_t_plus(item.date,today) == 0:
                if account_partner.partner.method_interest == 'total_buy_value':
                    account_partner.interest_cash_balance =define_interest_cash_balace(account_partner.account, date_mileston_apply,today,account_partner)
                    cash_t2 += item.total_value 
                else:
                    cash_t2+= item.partner_net_total_value
            elif define_t_plus(item.date, today) == 1:
                if account_partner.partner.method_interest == 'total_buy_value':
                    cash_t1 += item.total_value 
                else:
                    cash_t1+= item.partner_net_total_value
            else:
                if account_partner.partner.method_interest == 'total_buy_value':
                    cash_t0 += item.total_value 
                else:
                    cash_t0+= item.partner_net_total_value
        account_partner.cash_t2 = cash_t2
        account_partner.cash_t1 = cash_t1
        account_partner.cash_t0 = cash_t0
    account_partner.total_buy_trading_value = total_value_buy
    account_partner.net_trading_value = sum(item.partner_net_total_value for item in transaction)
    end_date = datetime.now().date()
    
    account_partner.save()

def define_t_plus(initial_date, date_milestone):
    try:
        if date_milestone >= initial_date:
            t = 0
            check_date = initial_date 
            max_iterations = (date_milestone - check_date).days   # Số lần lặp tối đa để tránh vòng lặp vô tận
            for _ in range(max_iterations + 1):  
                check_date += timedelta(days=1)
                if check_date > date_milestone or t==2:
                    break  # Nếu đã vượt qua ngày mốc, thoát khỏi vòng lặp
                weekday = check_date.weekday() 
                check_in_dates =  DateNotTrading.objects.filter(date=check_date).exists()
                if not (check_in_dates or weekday == 5 or weekday == 6):
                    t += 1
            return t
        else:
            print(f'Lỗi: date_milestone không lớn hơn hoặc bằng initial_date')
    except Exception as e:
        print(f'Lỗi: {e}')



    



def define_date_receive_cash(initial_date, t_plus):
    t = 0
    check_date = initial_date 
    while t < t_plus:
        check_date += timedelta(days=1)
        weekday = check_date.weekday()
        check_in_dates = DateNotTrading.objects.filter(date=check_date).exists()
        if not (check_in_dates or weekday == 5 or weekday == 6):
            t += 1
        if t == t_plus:
            nunber_days = (check_date-initial_date).days
            return check_date, nunber_days






    
        





   

# cập nhật giá danh mục => cập nhật giá trị tk chứng khoán
@receiver (post_save, sender=StockPriceFilter)
def update_market_price_port(sender, instance, created, **kwargs):
    port = Portfolio.objects.filter(sum_stock__gt=0, stock =instance.ticker)
    port_partner = PortfolioPartner.objects.filter(sum_stock__gt=0, stock =instance.ticker)
    if port:
        for item in port:
            new_price = instance.close*1000
            item.market_price = new_price*item.sum_stock
            item.save()
            account = item.account
            account.save()
    if port_partner:
        for item in port_partner:
            new_price = instance.close*1000
            item.market_price = new_price*item.sum_stock
            item.save()
            account_partner = item.account
            account_partner.save()


            
# Các hàm cập nhập cho account và port
def define_interest_cash_balace(account,start_date, end_date=None,account_partner=None):
    interest_cash_balance =0
    if end_date is None:
        end_date = datetime.now().date()
    if account_partner:
        partner = account_partner.partner
        all_port = PortfolioPartner.objects.filter(account=account_partner,sum_stock__gt=0)
        ratio_trading_fee =account_partner.partner.ratio_trading_fee
        for item in all_port:
            interest_cash_balance += (total_value_inventory_stock (account,ratio_trading_fee,item.stock,start_date,end_date,partner=partner))*-1
        if partner.method_interest =='dept':
            
            interest_cash_balance = interest_cash_balance + account_partner.net_cash_flow
            if interest_cash_balance >0:
                interest_cash_balance=0
    else:
        all_port = Portfolio.objects.filter(account=account, sum_stock__gt=0)
        ratio_trading_fee = account.transaction_fee
        for item in all_port:
            interest_cash_balance += (total_value_inventory_stock (account,ratio_trading_fee,item.stock,start_date,end_date))*-1
    return interest_cash_balance


def created_transaction(instance, portfolio, account,date_mileston):
    if instance.position == 'buy':
            #điều chỉnh account
            account.net_trading_value += instance.net_total_value # Dẫn tới thay đổi cash_balace, nav, pl
            account.total_buy_trading_value+= instance.net_total_value #Dẫn tới thay đổi interest_cash_balance 
            account.interest_cash_balance += instance.net_total_value
            if portfolio:
                # điều chỉnh danh mục
                    portfolio.receiving_t2 = portfolio.receiving_t2 + instance.qty 
            else: 
                #tạo danh mục mới
                    Portfolio.objects.create(
                    stock=instance.stock,
                    account= instance.account,
                    receiving_t2 = instance.qty ,)
    elif instance.position == 'sell':
        # điều chỉnh danh mục
        portfolio.on_hold = portfolio.on_hold -instance.qty
        #điều chỉnh account
        account.net_trading_value += instance.net_total_value # Dẫn tới thay đổi cash_balace, nav, pl
        account.cash_t2 += instance.total_value #Dẫn tới thay đổi cash_t0 trong tương lai và thay đổi interest_cash_balance 
        account.interest_cash_balance = define_interest_cash_balace(account,date_mileston)
        
        # tạo sao kê thuế
        ExpenseStatement.objects.create(
                transaction_id = instance.pk,
                account=instance.account,
                date=instance.date,
                type = 'tax',
                amount = instance.tax*-1,
                description = f"Thuế phát sinh bán với lệnh bán {instance.stock} số lượng {instance.qty} và giá {instance.price } "
                )
    
    
    
    
                

            
def update_portfolio_transaction(instance,transaction_items, portfolio):
    #sửa danh mục
    stock_transaction = transaction_items.filter(stock = instance.stock)
    sum_sell = sum(item.qty for item in stock_transaction if item.position =='sell')
    item_buy = stock_transaction.filter( position = 'buy')
    
    if portfolio:
        receiving_t2 =0
        receiving_t1=0
        on_hold =0 
        today  = datetime.now().date()      
        for item in item_buy:
            if define_t_plus(item.date, today) == 0:
                        receiving_t2 += item.qty                           
            elif define_t_plus(item.date, today) == 1:
                        receiving_t1 += item.qty                             
            else:
                        on_hold += item.qty

        on_hold = on_hold - sum_sell
                                           
        portfolio.receiving_t2 = receiving_t2
        portfolio.receiving_t1 = receiving_t1
        portfolio.on_hold = on_hold
        
        
# thay đổi sổ lệnh sẽ thay đổi trực tiếp cash_t0 và total_buy_trading_value, net_trading_value
def update_account_transaction(account, transaction_items,date_mileston):
    item_all_sell = transaction_items.filter( position = 'sell')
    cash_t2 = 0
    cash_t1 = 0
    cash_t0 =0
    total_value_buy= sum(i.net_total_value for i in transaction_items if i.position =='buy')
    today  = datetime.now().date()     
    for item in item_all_sell:
        if define_t_plus(item.date,today) == 0:
            cash_t2 += item.total_value 
        elif define_t_plus(item.date, today) == 1:
            cash_t1+= item.total_value 
        else:
            cash_t0 += item.total_value 
    account.cash_t2 = cash_t2
    account.cash_t1 = cash_t1
    account.cash_t0 = cash_t0
    account.total_buy_trading_value = total_value_buy
    account.net_trading_value = sum(item.net_total_value for item in transaction_items)
    account.interest_cash_balance = define_interest_cash_balace(account,date_mileston)




def update_or_created_expense_transaction(instance, description_type):
    if description_type=='tax':
        amount = instance.tax*-1
        description = f"Thuế với lệnh bán {instance.stock} số lượng {"{:,.0f}".format(instance.qty)} và giá {"{:,.0f}".format(instance.price) } "
    elif description_type== 'transaction_fee':
        amount = instance.transaction_fee*-1
        description = f"PGD phát sinh với lệnh {instance.position} {instance.stock} số lượng {"{:,.0f}".format(instance.qty)} và giá {"{:,.0f}".format(instance.price) } "
    elif description_type== 'advance_fee':
        number_interest = define_date_receive_cash(instance.date,2)[1]
        amount = -instance.account.interest_fee *instance.total_value*number_interest
        description = f"TK {instance.account} tính phí ứng tiền bán cho {number_interest} ngày, số dư tính phí ứng là {"{:,.0f}".format(instance.total_value)}"
    
    ExpenseStatement.objects.update_or_create(
        transaction_id=instance.pk,
        type=description_type,
        defaults={
            'account': instance.account,
            'date': instance.date,
            'amount': amount,
            'description': description,
    
        }
    )


def process_cash_flow(cash_t0, cash_t1, cash_t2):
    cash_t0 += cash_t1
    cash_t1 = 0
    cash_t1 += cash_t2
    cash_t2 = 0
    return cash_t0, cash_t1, cash_t2

def add_list_when_not_trading(account, list_data, cash_t1,cash_t2,interest_cash_balance, end_date,interest_fee):
    # Kiểm tra xem end_date đã tồn tại trong list_data hay chưa
    advance_cash_balance = -(cash_t1 + cash_t2)
    interest = round(interest_cash_balance *interest_fee, 0)
    advance_fee = round(advance_cash_balance * interest_fee, 0)
    dict_data = {
        'date': end_date,
        'interest_cash_balance': interest_cash_balance,
        'interest': interest,
        'advance_cash_balance':advance_cash_balance,
        'advance_fee':advance_fee
    }
    list_data.append(dict_data)
    return list_data, advance_cash_balance

def add_list_when_sell(account, list_data, cash_t1,cash_t2,start_date, end_date,interest_fee,account_partner=None):
    # Kiểm tra xem end_date đã tồn tại trong list_data hay chưa
    existing_data = next((item for item in list_data if item['date'] == end_date), None)
    interest_cash_balance = define_interest_cash_balace(account, start_date, end_date, account_partner)
    interest_cash_balance = interest_cash_balance if interest_cash_balance <= 0 else 0
    advance_cash_balance = -(cash_t1 + cash_t2)
    interest = round(interest_cash_balance * interest_fee, 0)
    advance_fee = round(advance_cash_balance * interest_fee, 0)
    # Nếu end_date đã tồn tại
    if existing_data:
        existing_data['interest_cash_balance'] = interest_cash_balance
        existing_data['interest'] = interest
        existing_data['advance_cash_balance'] = advance_cash_balance
        existing_data['advance_fee'] = advance_fee
    else:
        dict_data = {
            'date': end_date,
            'interest_cash_balance': interest_cash_balance,
            'interest': interest,
            'advance_cash_balance':advance_cash_balance,
            'advance_fee':advance_fee
        }
        list_data.append(dict_data)
    return list_data, interest_cash_balance, advance_cash_balance

def add_list_when_buy(list_data,value_buy, date_interest,interest_cash_balance,advance_cash_balance,interest_fee):
    # Kiểm tra xem date_interest đã tồn tại trong list_data hay chưa
    existing_data = next((item for item in list_data if item['date'] == date_interest), None)
    interest_cash_balance += value_buy
    interest = round(interest_cash_balance * interest_fee, 0)
    advance_fee = round(advance_cash_balance * interest_fee, 0) if advance_cash_balance !=0 else 0
    # Nếu date_interest đã tồn tại
    if existing_data:
        existing_data['interest_cash_balance'] = interest_cash_balance
        existing_data['interest'] = interest
        existing_data['advance_cash_balance'] = advance_cash_balance
        existing_data['advance_fee'] = advance_fee
    else:
        dict_data = {
            'date': date_interest,
            'interest_cash_balance': interest_cash_balance,
            'interest': interest,
            'advance_cash_balance':advance_cash_balance,
            'advance_fee':advance_fee
        }
        list_data.append(dict_data)
    return list_data, interest_cash_balance



def create_expense_list_when_edit_transaction(account,account_partner=None):
    end_date = datetime.now().date() - timedelta(days=1)
    interest_fee =account.interest_fee
    trading_fee =account.transaction_fee
    milestone_account = AccountMilestone.objects.filter(account=account).order_by('-created_at').first()
    if milestone_account:
        date_previous = milestone_account.created_at
    else:
        date_previous = account.created_at
    filter_params = {'account': account}
    if account_partner is not None:
        filter_params['partner'] = account_partner.partner
        interest_fee = account_partner.partner.ratio_interest_fee
        trading_fee= account_partner.partner.ratio_trading_fee
    transaction_items_merge_date = (
        Transaction.objects
        .filter(**filter_params, created_at__gt=date_previous)
        .values('position', 'date')
        .annotate(
            total_value=Sum(
                Case(
                    When(position='buy', then=F('total_value') * -(trading_fee+1)),
                    default=F('total_value'),
                    output_field=IntegerField(),
                )
            )
        )
        .order_by('date','created_at')
    )
    list_data = []
    interest_cash_balance, advance_cash_balance  = 0, 0
    cash_t2, cash_t1, cash_t0 = 0, 0, 0
    if transaction_items_merge_date and transaction_items_merge_date[0]['date']<=end_date:
        for index, item in enumerate(transaction_items_merge_date):
            # Kiểm tra xem có ngày tiếp theo hay không
            if index < len(transaction_items_merge_date) - 1:
                next_item_date = transaction_items_merge_date[index + 1]['date']
            else:
                # Nếu đến cuối list, thì thay thế ngày tiếp theo bằng ngày hôm nay
                next_item_date = end_date
            next_day = define_date_receive_cash(item['date'], 1)[0]
            if item['position']== 'buy':
                when_buy = add_list_when_buy(list_data,item['total_value'], item['date'],interest_cash_balance,advance_cash_balance,interest_fee)
                interest_cash_balance = when_buy[1]
            else:
                cash_t2 += item['total_value']
                when_sell =add_list_when_sell(account, list_data, cash_t1,cash_t2,date_previous, item['date'],interest_fee,account_partner)
                interest_cash_balance = when_sell[1]
                advance_cash_balance = when_sell[2]
            while next_day <= next_item_date:
                date_while_loop = next_day
                cash_t0, cash_t1, cash_t2 = process_cash_flow(cash_t0, cash_t1, cash_t2)
                when_not_traing = add_list_when_not_trading(account, list_data, cash_t1,cash_t2,interest_cash_balance,date_while_loop,interest_fee)
                advance_cash_balance = when_not_traing[1]
                next_day = define_date_receive_cash(next_day, 1)[0]
                if next_day > next_item_date:
                    break
        # Tạo một danh sách chứa tất cả các ngày từ ngày đầu tiên đến ngày cuối
        all_dates = [list_data[0]['date'] + timedelta(days=i) for i in range((end_date - list_data[0]['date']).days + 1)]
        # Tạo một danh sách mới chứa các phần tử đã có và điền giá trị bằng giá trị trước đó nếu thiếu
        new_data = []
        for d in all_dates:
            existing_entry = next((item for item in list_data if item['date'] == d), None)
            if existing_entry:
                new_data.append(existing_entry)
            else:
                previous_entry = new_data[-1]
                new_entry = {
                    'date': d,
                    'interest_cash_balance': previous_entry['interest_cash_balance'],
                    'interest': previous_entry['interest'],
                    'advance_cash_balance': previous_entry['advance_cash_balance'],
                    'advance_fee':previous_entry['advance_fee']}
                new_data.append(new_entry)
    new_data.sort(key=lambda x: x['date'])
    return new_data

def delete_and_recreate_account_expense(account):
    expense_list= create_expense_list_when_edit_transaction(account)
    expense_interest = ExpenseStatement.objects.filter(account = account, type ='interest')
    expense_advance_fee = ExpenseStatement.objects.filter(account = account, type ='advance_fee')
    expense_interest.delete()
    expense_advance_fee.delete()
    for item in expense_list:
        if item['interest'] != 0:
            formatted_interest_cash_balance = "{:,.0f}".format(item['interest_cash_balance'])
            ExpenseStatement.objects.create(
                description=f"Số dư tính lãi {formatted_interest_cash_balance}",
                type='interest',
                account=account,
                date=item['date'],
                amount=item['interest'],
                interest_cash_balance=item['interest_cash_balance']
        )
        if item['advance_fee'] != 0:
            formatted_advance_cash_balance = "{:,.0f}".format(item['advance_cash_balance'])
            ExpenseStatement.objects.create(
                description=f"Số dư tính lãi {formatted_advance_cash_balance}",
                type='advance_fee',
                account=account,
                date=item['date'],
                amount=item['advance_fee'],
                advance_cash_balance=item['advance_cash_balance']
        )
    return 


def delete_and_recreate_account_partner_expense(account, account_partner):
    if account_partner.partner.method_interest == 'total_buy_value':
        expense_list= create_expense_list_when_edit_transaction(account,account_partner)
        expense_interest = ExpenseStatementPartner.objects.filter(account = account_partner, type ='interest')
        expense_advance_fee = ExpenseStatementPartner.objects.filter(account = account_partner, type ='advance_fee')
        expense_interest.delete()
        expense_advance_fee.delete()
        for item in expense_list:
            if item['interest'] != 0:
                formatted_interest_cash_balance = "{:,.0f}".format(item['interest_cash_balance'])
                ExpenseStatementPartner.objects.create(
                    description=f"Số dư tính lãi {formatted_interest_cash_balance}",
                    type='interest',
                    account=account_partner,
                    date=item['date'],
                    amount=item['interest'],
                    interest_cash_balance=item['interest_cash_balance']
            )
            if item['advance_fee'] != 0:
                formatted_advance_cash_balance = "{:,.0f}".format(item['advance_cash_balance'])
                ExpenseStatementPartner.objects.create(
                    description=f"Số dư tính lãi {formatted_advance_cash_balance}",
                    type='advance_fee',
                    account=account_partner,
                    date=item['date'],
                    amount=item['advance_fee'],
                    advance_cash_balance=item['advance_cash_balance']
            )
    return 


def calculate_original_date_transaction_edit(transaction):
    # Tính toán ngày giao dịch gốc dựa trên dữ liệu trong cơ sở dữ liệu, lấy record được chỉnh sửa gần nhất
    original_date = Transaction.objects.filter(id=transaction.id, date__lt=transaction.date).order_by('-date').first().date
    return original_date

@receiver([post_save, post_delete], sender=Transaction)
@receiver([post_save, post_delete], sender=CashTransfer)
def save_field_account_1(sender, instance, **kwargs):
    created = kwargs.get('created', False)
    account = instance.account
    milestone_account = AccountMilestone.objects.filter(account =account).order_by('-created_at').first()
    if milestone_account:
        date_mileston = milestone_account.created_at
    else:
        date_mileston = account.created_at
    
    if sender == CashTransfer:
        if not created:
            cash_items = CashTransfer.objects.filter(account=account,created_at__gt = date_mileston)
            account.net_cash_flow = sum(item.amount for item in cash_items)
            # update lệnh tiền tk bank tư động
            bank_cash_transfer = BankCashTransfer.objects.get(customer_cash_id = instance.pk)
            bank_cash_transfer.amount = instance.amount
            bank_cash_transfer.date=instance.date
            bank_cash_transfer.save()

        else:
            account.net_cash_flow +=  instance.amount
            #tạo lệnh lệnh tiền tk bank tư động
            if instance.amount >0:
                description=f"Lệnh nạp tiền tự động từ KH {instance.account}"
            else:
                description=f"Lệnh rút tiền tự động từ KH {instance.account}"
            bank_cash_transfer = BankCashTransfer.objects.create(
                source='TCB-Ha',
                account=instance.account,
                amount=instance.amount,
                type='trade_transfer',
                date=instance.date,
                description=description,
                customer_cash_id = instance.pk
            )
        
    elif sender == Transaction:
        portfolio = Portfolio.objects.filter(stock =instance.stock, account= instance.account).first()
        transaction_items = Transaction.objects.filter(account=account,created_at__gt = date_mileston)
        
        if not created:
            # sửa sao kê phí và thuế
            update_or_created_expense_transaction(instance,'transaction_fee' )
            if instance.position =='sell':
                update_or_created_expense_transaction(instance,'tax' )
                update_or_created_expense_transaction(instance, 'advance_fee')
            # sửa sao kê lãi
            # sửa danh mục
            update_portfolio_transaction(instance,transaction_items, portfolio)
            
            # sửa account
            update_account_transaction( account, transaction_items,date_mileston)
            # sửa accout_partner
            if instance.partner and instance.total_value != instance.previous_total_value:
                partner_update_transaction(instance,date_mileston)         
            # sửa hoa hồng cp
            if account.cpd:
                account_all = Account.objects.all()
                try:
                    # Kiểm tra xem bản ghi đã bị xóa chưa
                    edit_commission = Transaction.objects.get(pk =instance.pk)
                    # Nếu bản ghi tồn tại, cập nhật giá trị của trường total_value
                    cp_update_transaction( instance, account_all)
                except Transaction.DoesNotExist:
                    pass
                    
           
        else:
            created_transaction(instance, portfolio, account,date_mileston)
            update_or_created_expense_transaction(instance,'transaction_fee' )
            if instance.position =='sell':
                update_or_created_expense_transaction(instance, 'advance_fee')
            if account.cpd:
                cp_create_transaction(instance)
            #xủ lí account partner
            if instance.partner:
                created_transaction_partner(instance,account,date_mileston)
        if portfolio:
            portfolio.save()   
    
    account.save()

        
            
@receiver(post_delete, sender=Transaction)
def delete_expense_statement(sender, instance, **kwargs):
    expense = ExpenseStatement.objects.filter(transaction_id=instance.pk)
    if expense:
        expense.delete()  
    # điều chỉnh chi phí partner 
    expense_partner = ExpenseStatementPartner.objects.filter(transaction_id=instance.pk)
    if expense_partner:
        expense_partner.delete()  
    # điều chỉnh hoa hồng
    if instance.account.cpd:
        month_year=define_month_year_cp_commission(instance.date)   
        commission = ClientPartnerCommission.objects.get(cp=instance.account.cpd, month_year=month_year)      
        commission.total_value=commission.total_value -instance.total_value
        if commission.total_value<0:
                commission.total_value=0
        commission.save()


@receiver(post_delete, sender=CashTransfer)
def delete_bankcash(sender, instance, **kwargs):
    bank_cash_transfer = BankCashTransfer.objects.get(customer_cash_id = instance.pk)
    if bank_cash_transfer:
        bank_cash_transfer.delete()  
    

def sum_temporarily_account_when_edit_expense(instance,account,account_expense_period):
    # tìm mileston gần nhất
    if account_expense_period:
        #tinh tong lãi TK tổng tam tinh
        account.total_temporarily_interest = sum(item.amount for item in account_expense_period if item.type =='interest' )
        # tinh tong phi ung TK tổng tam tinh
        account.total_temporarily_advance_fee = sum(item.amount for item in account_expense_period if item.type =='advance_fee')
    account.save()

@receiver([post_save, post_delete], sender=ExpenseStatement)
def save_field_account_2_1(sender, instance, **kwargs):
    account = instance.account
    milestone_account = AccountMilestone.objects.filter(account = account).order_by('-created_at').first()
    if milestone_account:
        date_mileston = milestone_account.created_at
    else:
        date_mileston = account.created_at
    account =instance.account
    account_expense_period = ExpenseStatement.objects.filter(account= account , created_at__gt = date_mileston)
    sum_temporarily_account_when_edit_expense(instance,account,account_expense_period)

@receiver([post_save, post_delete], sender=ExpenseStatementPartner)
def save_field_account_2_2(sender, instance, **kwargs):
    account_partner = instance.account
    if account_partner.partner.method_interest == 'total_buy_value':
        account = account_partner.account
        lated_mileston = account_partner.milestone_date_lated
        if lated_mileston:
            date_mileston = lated_mileston
        else:
            date_mileston = account.created_at
        account_expense_period = ExpenseStatementPartner.objects.filter(account= account_partner , created_at__gt = date_mileston)
        sum_temporarily_account_when_edit_expense(instance, account_partner ,account_expense_period)

@receiver([post_save, post_delete], sender=ExpenseStatementRealStockAccount)
def save_field_account_2_3(sender, instance, **kwargs):
    account_real_stock = instance.account
    current_date = datetime.now()
    year = current_date.year
    month = current_date.month
    if current_date.day == 1:  # Nếu là ngày đầu tháng
        if month == 1:  # Nếu là tháng 1
            start_date = datetime(year - 1, 12, 1)
        else:
            start_date = datetime(year, month - 1, 1)
        end_date = datetime(year, month, 1) - timedelta(days=1)
    else:
        start_date = datetime(year, month, 1)
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    # Tính tổng amount của các record trong khoảng thời gian có type là 'loan_interest' hoặc 'deposit_interest'
    total_loan_interest_amount = ExpenseStatementRealStockAccount.objects.filter(
        account=account_real_stock,
        date__range=(start_date, end_date),
        type__in=['loan_interest']
    ).aggregate(Sum('amount'))['amount__sum'] or 0.0

     
    account_real_stock.total_temporarily_interest = total_loan_interest_amount

    if current_date.day == 1: 
        total_deposit_interest_amount = ExpenseStatementRealStockAccount.objects.filter(
        account=account_real_stock,
        date__range=(start_date, end_date),
        type__in=['deposit_interest']
            ).aggregate(Sum('amount'))['amount__sum'] or 0.0
        
        account_real_stock.total_deposit_interest_paid =total_deposit_interest_amount
        account_real_stock.total_interest_paid += account_real_stock.total_temporarily_interest 
        account_real_stock.total_temporarily_interest = 0
    
    account_real_stock.save()
        
        
                                               

    
        
@receiver([post_save, post_delete], sender=AccountMilestone)
def save_field_account_4(sender, instance, **kwargs):
    created = kwargs.get('created', False)
    if not created:
        account = instance.account
        item_milestone = AccountMilestone.objects.filter(account=account)
        account.total_interest_paid = sum(item.interest_paid for item in item_milestone)
        account.total_closed_pl =  sum(item.closed_pl for item in item_milestone)
        account.total_advance_fee_paid = sum(item.advance_fee_paid for item in item_milestone)
        account.save()

@receiver([post_save, post_delete], sender=AccountPartner)
def save_field_account_5(sender, instance, **kwargs):
    real_stock_account_when_update_transaction(instance.partner)

#chạy 1 phút 1 lần
def update_market_price_for_port():
    port = Portfolio.objects.filter(sum_stock__gt=0)
    for item in port:
        item.market_price = get_stock_market_price(item.stock)
        # item.profit = (item.market_price - item.avg_price)*item.sum_stock
        # item.percent_profit = round((item.market_price/item.avg_price-1)*100,2)
        item.save()

def calculate_interest():
    #kiểm tra TK tổng  tính lãi suất
    account_interest = Account.objects.filter(interest_cash_balance__lt=0)
    if account_interest:
        for instance in account_interest:
            formatted_interest_cash_balance = "{:,.0f}".format(instance.interest_cash_balance)
            interest_amount = instance.interest_fee * instance.interest_cash_balance
            if abs(interest_amount)>10:
                ExpenseStatement.objects.create(
                    account=instance,
                    date=datetime.now().date()-timedelta(days=1),
                    type = 'interest',
                    amount = interest_amount,
                    description=f"Số dư tính lãi {formatted_interest_cash_balance}",
                    interest_cash_balance = instance.interest_cash_balance
                    )
    # # KT tài khoảng tổng chạy tính lãi phí ứng
    # account_advance_fee = Account.objects.filter(advance_cash_balance__lt=0)
    # if account_advance_fee:
    #     for instance in account_advance_fee:
    #         formatted_advance_cash_balance= "{:,.0f}".format(instance.advance_cash_balance)
    #         advance_amount =instance.interest_fee * instance.advance_cash_balance/360
    #         if abs(advance_amount)>10:
    #             ExpenseStatement.objects.create(
    #                 account=instance,
    #                 date=datetime.now().date()-timedelta(days=1),
    #                 type = 'advance_fee',
    #                 amount = advance_amount,
    #                 description=f"Số dư tính phí ứng {formatted_advance_cash_balance}",
    #                 advance_cash_balance = instance.advance_cash_balance
    #                 )
    # kt tài khoản con, tính lãi
    account_partner_interest = AccountPartner.objects.filter(interest_cash_balance__lt=0,partner__method_interest = 'total_buy_value')
    if account_partner_interest:
        for instance in account_partner_interest:
            formatted_interest_cash_balance = "{:,.0f}".format(instance.interest_cash_balance)
            interest_amount = instance.partner.ratio_interest_fee * instance.interest_cash_balance/instance.partner.total_date_interest
            if abs(interest_amount)>10:
                ExpenseStatementPartner.objects.create(
                    account=instance,
                    date=datetime.now().date()-timedelta(days=1),
                    type = 'interest',
                    amount = interest_amount,
                    description=f"Số dư tính lãi {formatted_interest_cash_balance}",
                    interest_cash_balance = instance.interest_cash_balance
                    )
    # # KT tài khoảng con chạy tính lãi phí ứng
    # account_partner_advance = AccountPartner.objects.filter(advance_cash_balance__lt=0,partner__method_interest = 'total_buy_value')
    # if account_partner_advance:
    #     for instance in account_partner_advance:
    #         formatted_advance_cash_balance= "{:,.0f}".format(instance.advance_cash_balance)
    #         advance_amount =instance.partner.ratio_advance_fee * instance.advance_cash_balance/instance.partner.total_date_interest
    #         if abs(advance_amount)>10:
    #             ExpenseStatementPartner.objects.create(
    #                 account=instance,
    #                 date=datetime.now().date()-timedelta(days=1),
    #                 type = 'advance_fee',
    #                 amount = advance_amount,
    #                 description=f"Số dư tính phí ứng {formatted_advance_cash_balance}",
    #                 interest_cash_balance = instance.interest_cash_balance
    #                 )
    #kt tài khoản ck thực chạy tính lãi
    real_stock_account_interest = RealStockAccount.objects.filter(partner__method_interest = 'dept')
    for instance in real_stock_account_interest:
            formatted_interest_cash_balance= "{:,.0f}".format(instance.interest_cash_balance)
            if instance.interest_cash_balance >0:
                amount = 0.0001  * instance.interest_cash_balance/instance.partner.total_date_interest
                type = 'deposit_interest'
                description = f"Số dư tính lãi tiền gửi không kì hạn {formatted_interest_cash_balance}"
                
            else:
                type = 'loan_interest'
                amount =instance.partner.ratio_interest_fee  * instance.interest_cash_balance/instance.partner.total_date_interest
                description = f"Số dư tính lãi vay {formatted_interest_cash_balance}"
            ExpenseStatementRealStockAccount.objects.create(
                    account=instance,
                    date=datetime.now().date()-timedelta(days=1),
                    type = type,
                    amount = amount,
                    description=description,
                    interest_cash_balance = instance.interest_cash_balance
                    )

def pay_money_back():
    # chạy tk tổng
    account = Account.objects.all()
    if account:
        for instance in account:
        # chuyển tiền dời lên 1 ngày
            instance.cash_t0 += instance.cash_t1
            instance.cash_t1= instance.cash_t2
            instance.cash_t2 =0
            instance.save()
    # chạy tk con
    account_partner = AccountPartner.objects.all()
    if account:
        for instance in account_partner:
        # chuyển tiền dời lên 1 ngày
            instance.cash_t0 += instance.cash_t1
            instance.cash_t1= instance.cash_t2
            instance.cash_t2 =0
            instance.save()
    real_stock = RealStockAccount.objects.filter(Q(milestone_cash_t2__gt=0) | Q(milestone_cash_t1__gt=0))
    for item in real_stock:
        item.milestone_cash_t1 = 0
        item.milestone_cash_t1+= item.milestone_cash_t2
        item.save()


def atternoon_check():
    #chạy tk tổng
    port = Portfolio.objects.filter(sum_stock__gt=0)
    if port:
        for item in port:
            buy_today = Transaction.objects.filter(account = item.account,position ='buy',date = datetime.now().date(),stock__stock = item.stock)
            qty_buy_today = sum(item.qty for item in buy_today )
            item.on_hold += item.receiving_t1
            item.receiving_t1 = item.receiving_t2  - qty_buy_today
            item.receiving_t2 = qty_buy_today
            item.save()
    # chạy tk con
    port_partner = PortfolioPartner.objects.filter(sum_stock__gt=0)
    if port_partner:
        for item in port_partner:
            partner = item.account.partner
            buy_today = Transaction.objects.filter(account = item.account.account,partner =partner,position ='buy',date = datetime.now().date(),stock__stock = item.stock)
            qty_buy_today = sum(item.qty for item in buy_today )
            item.on_hold += item.receiving_t1
            item.receiving_t1 = item.receiving_t2  - qty_buy_today
            item.receiving_t2 = qty_buy_today
            item.save()
            

def check_dividend_recevie():
    #check cổ tức
    port = Portfolio.objects.filter(Q(cash_divident__gt=0) | Q(stock_divident__gt=0))
    if port:
        for item in port:
            item.on_hold += item.stock_divident
            account = item.account
            account.cash_balance += item.cash_divident
            account.interest_cash_balance += item.cash_divident
            item.save()
            account.save()


# stockbiz đổi web, tạm thời hàm lỗi
def save_event_stock(stock):
    list_event =[]
    linkbase= 'https://www.stockbiz.vn/MarketCalendar.aspx?Symbol='+ stock
    r = requests.get(linkbase)
    soup = BeautifulSoup(r.text,'html.parser')
    table = soup.find('table', class_='dataTable')  # Tìm bảng chứa thông tin
    if table:
        rows = table.find_all('tr')  # Lấy tất cả các dòng trong bảng (loại bỏ dòng tiêu đề)
        cash_value= 0
        stock_value=0
        stock_option_value=0
        price_option_value=0
        dividend_type = 'order'
        for row in rows[1:]:  # Bắt đầu từ vị trí thứ hai (loại bỏ dòng tiêu đề)
            dividend  = {}
            columns = row.find_all('td')  # Lấy tất cả các cột trong dòng
            if len(columns) >= 3:  # Kiểm tra số lượng cột
                dividend['ex_rights_date'] = columns[0].get_text(strip=True)
                dividend['event'] = columns[4].get_text(strip=True)
                list_event.append(dividend)
                event = dividend['event'].lower()
                ex_rights_date = datetime.strptime(dividend['ex_rights_date'], '%d/%m/%Y').date()
                if ex_rights_date == datetime.now().date():
                    if 'tiền' in event:
                        dividend_type = 'cash'
                        cash = re.findall(r'\d+', event)  # Tìm tất cả các giá trị số trong chuỗi
                        if cash:
                            value1 = int(cash[-1])/1000  # Lấy giá trị số đầu tiên
                            cash_value += value1
                    elif 'cổ phiếu' in event and 'phát hành' not in event:
                        dividend_type = 'stock'
                        stock_values = re.findall(r'\d+', event)
                        if stock_values:
                            value2 = int(stock_values[-1])/int(stock_values[-2])
                            stock_value += value2
                    elif 'cổ phiếu' in event and 'giá' in event and 'tỷ lệ' in event:
                        dividend_type = 'option'
                        option = re.findall(r'\d+', event)
                        if option:
                                stock_option_value = int(option[-2])/int(option[-3])
                                price_option_value = int(option[-1])
        if dividend_type == 'order':
            pass
        else:
            DividendManage.objects.update_or_create(
                        ticker= stock,  # Thay thế 'Your_Ticker_Value' bằng giá trị ticker thực tế
                        date_apply=ex_rights_date,
                        defaults={
                            'type': dividend_type,
                            'cash': cash_value,
                            'stock': stock_value,
                            'price_option': price_option_value,
                            'stock_option':stock_option_value
                        }
                    )
    return list_event

def check_dividend():
    signal = Portfolio.objects.filter(sum_stock__gt=0).distinct('stock') 
    for stock in signal:
        dividend = save_event_stock(stock.stock)
    dividend_today = DividendManage.objects.filter(date_apply =datetime.now().date() )
    for i in dividend_today:
        i.save()

def setle_milestone_account_partner(account_partner):
    status = False
    if account_partner.market_value == 0 and account_partner.nav >0:
        status = True
        date=datetime.now().date()
        partner =account_partner.partner
        # ratio_interest_fee = partner.ratio_interest_fee
        # total_date_interest =partner.total_date_interest
        # if account_partner.cash_t1 !=0 and account_partner.cash_t2 !=0:
        #     number_interest_t1 = define_date_receive_cash(date,1)[1]
        #     number_interest_t2 = define_date_receive_cash(date,2)[1]
        #     amount1 = ratio_interest_fee *(account_partner.advance_cash_balance)*number_interest_t1 /total_date_interest
        #     amount2 = ratio_interest_fee *(account_partner.advance_cash_balance + account_partner.cash_t1)*(number_interest_t2-number_interest_t1) /total_date_interest
        #     amount =amount1+amount2
    
        # elif account_partner.cash_t1 !=0 and account_partner.cash_t2 ==0:
        #     number_interest = define_date_receive_cash(date,1)[1]
        #     amount =ratio_interest_fee *(account_partner.advance_cash_balance)*number_interest /total_date_interest
        # if account_partner.cash_t1 ==0 and account_partner.cash_t2 !=0:
        #     number_interest = define_date_receive_cash(date,2)[1]
        #     amount = ratio_interest_fee *(account_partner.advance_cash_balance)*number_interest /total_date_interest  
        # else:
        #     print('Vẫn còn âm tiền, cần giải pháp đòi nọ')
        #     amount = 0
            
        # if  amount <0 :
        #     description = f"TK {account_partner} tính phí ứng tiền bán tất toán cho {number_interest} ngày"
        #     ExpenseStatementPartner.objects.create(
        #             account=account_partner,
        #             date=date,
        #             type = 'advance_fee',
        #             amount = amount,
        #             description = description,
        #             advance_cash_balance = account_partner.advance_cash_balance
        #             )
        withdraw_cash = BankCashTransfer.objects.create(
                source='TCB-Ha',
                partner = account_partner.partner,
                account=account_partner.account,
                amount= account_partner.nav,
                type='trade_transfer',
                date=date,
                description=f"Lệnh chuyển tiền tự động từ tiểu khoản {account_partner} đến TKNH khi tất toán ",
            )
        if partner.name == 'MCF':
            cash_in = BankCashTransfer.objects.create(
                    source='TCB-Ha',
                    partner = account_partner.partner,
                    amount= -account_partner.nav,
                    type='trade_transfer',
                    date=date,
                    description=f"Lệnh chuyển tiền từ TKNH đến TKCK của MCF khi tất toán" ,
                )
        # reset thong so account_partner
        real_stock= RealStockAccount.objects.get(partner=partner)
        real_stock.milestone_cash_t2 += account_partner.cash_t2
        real_stock.milestone_cash_t1 += account_partner.cash_t1
        real_stock.save()
        account_partner.cash_t0 = 0
        account_partner.cash_t1 = 0
        account_partner.cash_t2 = 0
        account_partner.total_interest_paid = account_partner.total_temporarily_interest
        account_partner.total_advance_fee_paid +=account_partner.total_temporarily_advance_fee
        account_partner.total_closed_pl += account_partner.total_temporarily_pl
        account_partner.net_cash_flow = 0
        account_partner.net_trading_value = 0
        account_partner.total_buy_trading_value = 0
        account_partner.total_temporarily_interest = 0
        account_partner.total_temporarily_advance_fee =0
        account_partner.total_temporarily_pl = 0
        account_partner.milestone_date_lated = datetime.now()
        account_partner.save()
        
        

    return  status

def setle_milestone_account(account):
    status = False
    if account.market_value == 0  and account.total_temporarily_interest !=0:  
        date=datetime.now().date()

        withdraw_cash = CashTransfer.objects.create(
            account = account,
            date = date,
            amount = -account.nav,
            description = "Tất toán tài khoản, lệnh rút tiền tự động",      
        )
        number = len(AccountMilestone.objects.filter(account=account)) +1
        a = AccountMilestone.objects.create(
            account=account,
            milestone = number,
            interest_fee = account.interest_fee,
            transaction_fee = account.transaction_fee,
            tax = account.tax,
            net_cash_flow = account.net_cash_flow,
            total_buy_trading_value = account.total_buy_trading_value,
            net_trading_value = account.net_trading_value,
            interest_paid  = account.total_temporarily_interest,
            advance_fee_paid = account.total_temporarily_advance_fee,
            closed_pl    = account.total_temporarily_pl   )
        
        # reset thong so account
        account.cash_t0 = 0
        account.cash_t1 = 0
        account.cash_t2 = 0
        account.total_interest_paid = a.interest_paid
        account.total_advance_fee_paid += a.advance_fee_paid
        account.total_closed_pl += a.closed_pl
        account.milestone_date_lated = a.created_at
        account.net_cash_flow = 0
        account.net_trading_value = 0
        account.total_buy_trading_value = 0
        account.total_temporarily_interest = 0
        account.total_temporarily_advance_fee =0
        account.total_temporarily_pl = 0
        account.save()
        status = True
        account_partner = AccountPartner.objects.filter(account=account)
        for item in account_partner:
            setle_milestone_account_partner(item)
    return  status

