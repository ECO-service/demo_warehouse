from .models import *
from partner.models import *
from django.db.models import Sum, Case, When, F, Value, IntegerField, Max




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
    # port_partner = PortfolioPartner.objects.filter(sum_stock__gt=0, stock =instance.ticker)
    if port:
        saved_accounts = set()  # Lưu các account đã save
        for item in port:
            new_price = instance.close
            item.market_price = new_price * item.sum_stock
            item.save(update_avg_price=False)  # Không cập nhật avg_price
            
            account = item.account
            if account not in saved_accounts:  # Kiểm tra nếu chưa lưu
                account.save()
                saved_accounts.add(account)  # Thêm vào set để tránh lưu lại
            
            if account.status:
                message = f"Tài khoản {account.pk}, tên {account.name} bị {account.status}"
                send_notification(message)

   



            
# Các hàm cập nhập cho account và port
def define_interest_cash_balace(account,start_date, end_date=None):
    interest_cash_balance =0
    if end_date is None:
        end_date = datetime.now().date()
    all_port = Portfolio.objects.filter(account=account, sum_stock__gt=0)
    for item in all_port:
        interest_cash_balance += (total_value_inventory_stock (account,item.stock,start_date,end_date))*-1
    return interest_cash_balance


def created_transaction(instance, portfolio, account,date_mileston):
    if instance.position == 'buy':
            #điều chỉnh account
            account.net_trading_value += instance.net_total_value # Dẫn tới thay đổi cash_balace, nav, pl
            account.total_buy_trading_value+= instance.net_total_value #Dẫn tới thay đổi interest_cash_balance 
            #Tìm tỷ lê cho vay để tính giá trị cho vay theo phần 5 của vlc
            margin_rate = StockListMargin.objects.filter(stock=instance.stock).first().initial_margin_requirement
            ratio_margin_rate = max(1 - (margin_rate - 20) / 100, 0)
            account.interest_cash_balance += instance.total_value*ratio_margin_rate
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
    cash_t2, cash_t1,cash_t0 = 0,0,0
    total_value_buy= sum(i.total_value for i in transaction_items if i.position =='buy')
    today  = datetime.now().date()  
    if item_all_sell:
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




def update_expense_transaction(instance, description_type):
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

def created_expense_transaction(instance,account, description_type):
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
    
        ExpenseStatement.objects.create(
                transaction_id=instance.pk,
                type=description_type,
                account=instance.account,
                date=instance.date,
                amount=amount,
                description=description
            )
        account.total_temporarily_advance_fee += amount
    

    

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

def add_list_when_sell(account, list_data, cash_t1,cash_t2,start_date, end_date,interest_fee):
    # Kiểm tra xem end_date đã tồn tại trong list_data hay chưa
    existing_data = next((item for item in list_data if item['date'] == end_date), None)
    interest_cash_balance = define_interest_cash_balace(account, start_date, end_date)
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



def create_expense_list_when_edit_transaction(account):
    end_date = datetime.now().date() - timedelta(days=1)
    interest_fee =account.interest_fee
    trading_fee =account.transaction_fee
    milestone_account = AccountMilestone.objects.filter(account=account).order_by('-created_at').first()
    if milestone_account:
        date_previous = milestone_account.created_at
    else:
        date_previous = account.created_at
    filter_params = {'account': account}
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
                when_sell =add_list_when_sell(account, list_data, cash_t1,cash_t2,date_previous, item['date'],interest_fee)
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

        else:
            account.net_cash_flow +=  instance.amount
           
            #tạo lệnh lệnh tiền tk bank tư động
            if instance.amount >0:
                description=f"Lệnh nạp tiền từ KH {instance.account}"
            else:
                if account.excess_equity > 0 and account.margin_ratio > 0.15 and account.nav > 0:
                    description = "Lệnh rút tiền hợp lệ\n"
                else:
                    description = "Lệnh rút tiền KHÔNG hợp lệ\n"

                # Thông báo lệnh rút tiền cho superadmin
                message = (
                    f"Tài khoản {instance.account.name}, rút số tiền {'{:,.0f}'.format(abs(instance.amount))} từ đối tác {instance.partner}. Trạng thái tài khoản:\n"
                    f"- Tài sản ròng: {'{:,.0f}'.format(instance.account.nav)}\n"
                    f"- Tỷ lệ margin: {round(instance.account.margin_ratio * 100, 2)}%"
                )
                send_notification(description + message)

                
    elif sender == Transaction:
        portfolio = Portfolio.objects.filter(stock =instance.stock, account= instance.account).first()
        transaction_items = Transaction.objects.filter(account=account,created_at__gt = date_mileston)
        
        if not created:
            # sửa sao kê phí và thuế
            update_expense_transaction(instance,'transaction_fee' )
            if instance.position =='sell':
                update_expense_transaction(instance,'tax' )
                update_expense_transaction(instance, 'advance_fee')
            # sửa sao kê lãi
            if (instance.total_value != instance.previous_total_value or instance.previous_date != instance.date) and instance.date != timezone.now().date():
                delete_and_recreate_account_expense(account)    
                date_edit = instance.date +timedelta(days=1)
                update_interest_expense(account,date_edit)
                
            # sửa danh mục
            update_portfolio_transaction(instance,transaction_items, portfolio)
            
            # sửa account
            update_account_transaction( account, transaction_items,date_mileston)
   
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
            created_expense_transaction(instance,account,'transaction_fee' )
            if instance.position =='sell':
                created_expense_transaction(instance,account,'tax' )
                created_expense_transaction(instance,account, 'advance_fee')
            if account.cpd:
                cp_create_transaction(instance)
        if portfolio:
            portfolio.save()   
    
    account.save()
  

        
            
@receiver(post_delete, sender=Transaction)
def delete_expense_statement(sender, instance, **kwargs):
    expense = ExpenseStatement.objects.filter(transaction_id=instance.pk)
    if expense:
        expense.delete()   
    # điều chỉnh hoa hồng
    if instance.account.cpd:
        month_year=define_month_year_cp_commission(instance.date)   
        commission = ClientPartnerCommission.objects.get(cp=instance.account.cpd, month_year=month_year)      
        commission.total_value=commission.total_value -instance.total_value
        if commission.total_value<0:
                commission.total_value=0
        commission.save()
    

def update_interest_expense(account,date_edit):
    start_date = account.book_interest_date_lated or account.created_at.date()

    if date_edit <= start_date:
        previous_book_interest = BankCashTransfer.objects.filter(
            account=account, 
            description__icontains='Hoạch toán'
        ).order_by('-date')
        
        if previous_book_interest.exists():
            previous_book_interest.filter(date__gte=date_edit).delete()

            send_notification(f"Tài khoản {account.pk}, tên {account.name} có chỉnh sửa lệnh trước ngày đã hoạch toán lãi")
            previous_book_interest = BankCashTransfer.objects.filter(account=account, date__lt=date_edit).order_by('-date').first()
            start_date = previous_book_interest.date if previous_book_interest else None

    totals = ExpenseStatement.objects.filter(
            account=account,
            date__gte=start_date,
            type__in=['interest', 'advance_fee']
        ).values('type').annotate(total=Sum('amount'))

    total_interest = sum(item['total'] for item in totals if item['type'] == 'interest')
    total_advance_fee = sum(item['total'] for item in totals if item['type'] == 'advance_fee')

    booked_interest = BankCashTransfer.objects.filter(
        account=account, description__icontains='Hoạch toán'
    ).aggregate(
        total_interest_paid=models.Sum('amount'),
        total_advance_fee_paid=models.Sum('amount')
    )

    account.total_temporarily_interest = total_interest
    account.total_temporarily_advance_fee = total_advance_fee 
    account.book_interest_date_lated = start_date
    account.total_interest_paid = booked_interest['total_interest_paid'] or 0
    account.total_advance_fee_paid = booked_interest['total_advance_fee_paid'] or 0


# # chạy trong trường hợp chỉnh sửa trực tiếp trên model ExpenseStatement
# @receiver([post_save, post_delete], sender=ExpenseStatement)
# def save_field_account_2_1(sender, instance, **kwargs):
#     created = kwargs.get('created', False)
#     if not created:
#         account = instance.account
#         date_edit = instance.date
#         update_interest_expense(account,date_edit)


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
                instance.total_temporarily_interest += interest_amount
                instance.save()
    
   
   

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



def check_dividend_and_notify():
    list_event = get_dividend_data()
    signal = Portfolio.objects.filter(sum_stock__gt=0).distinct('stock') 
    for item in signal:
        for event in list_event:
            if item.stock == event['code']:
                message = f"Tài khoản {item.account}, có {item.stock} sẽ nhận cổ tức ngày {event['effectiveDate']}"
                send_notification(message)
                



def setle_milestone_account(account):
    status = False
    if account.market_value == 0:  
        date=datetime.now().date()
        partner = CashTransfer.objects.filter(account = account, amount__gt=0).order_by('-date')[0].partner
        withdraw_cash = CashTransfer.objects.create(
            account = account,
            partner = partner,
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
        account.total_closed_pl += a.closed_pl
        account.milestone_date_lated = a.created_at
        account.net_cash_flow = 0
        account.net_trading_value = 0
        account.total_buy_trading_value = 0
        account.total_temporarily_pl = 0
        account.save()
        status = True
        
    return  status


def booking_fee_interest(item):
    if item.total_temporarily_advance_fee !=0 and item.total_temporarily_interest !=0 :
        today = timezone.now().date()
        item.total_interest_paid += item.total_temporarily_interest
        item.total_advance_fee_paid += item.total_temporarily_advance_fee
        BankCashTransfer.objects.create(
                partner=item.partner,
                date= today,
                amount = -item.total_temporarily_interest ,
                type = 'cash_in',
                account = item,
                description = f'Hoạch toán lãi vay của tài khoản {item.name}'
                )
        BankCashTransfer.objects.create(
                partner=item.partner,
                date= today,
                amount = -item.total_temporarily_advance_fee ,
                account = item,
                type = 'cash_in',
                description = f'Hoạch toán phí ứng của tài khoản {item.name}'
                )
        item.total_temporarily_advance_fee=0
        item.total_temporarily_interest = 0
        item.book_interest_date_lated = today
        item.save()
        status = True
        
        return  status
            

def run_booked_fee_interest():
    today = timezone.now().date()
    # Lấy ngày cuối cùng của tháng hiện tại
    last_day_of_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    account = Account.objects.all()
    if today == last_day_of_month:
        for item in account:
            booking_fee_interest(item)
    else:
        for item in account:
            if item.interest_cash_balance==0:
                booking_fee_interest(item)