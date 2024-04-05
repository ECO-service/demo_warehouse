import math
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from operation.models import *
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader
from django.urls import reverse
from django.contrib.auth.forms import PasswordChangeForm
from .forms import *
from datetime import timedelta,datetime as dt


def LoginUser(request):
    pk = request.user.username
    if pk == "":
        return render(request, "stockwarehouse/login.html")
    else:
        if pk.isnumeric():
            return redirect('customer_detail', pk=pk)
        else:
            return HttpResponse("<h1> Bạn đang truy cập trang admin, hãy thoát ra trước khi truy cập giao diện cho KH<h1>")


@login_required(login_url="/loginuser/")
def customer_view(request, pk):
    account = get_object_or_404(Account, pk=pk)
    port = Portfolio.objects.filter(account=account, sum_stock__gt=0)
    transaction = Transaction.objects.filter(account=account).order_by('-date')
    cash = CashTransfer.objects.filter(account=account).order_by('-date')
    expense = ExpenseStatement.objects.filter(
        account=account).order_by('-date')
    list_margin = StockListMargin.objects.all()

    context = {
        'account': account,
        'port': port,
        'transaction': transaction,
        'cash': cash,
        'expense': expense,
        'list_margin': list_margin,

    }

    if request.user.username == str(pk):
        template = loader.get_template('stockwarehouse/customer_home.html')
        return HttpResponse(template.render(context, request))
    else:
        return HttpResponse("<h1>Permission denied<h1>")


# def clicklogin(request):
#     if request.method!="POST":
#         return HttpResponse("<h1> Methoid not allowed<h1>")
#     else:
#         username = request.POST.get('username','')
#         password = request.POST.get('password','')

#         user=authenticate(username=username,password=password)
#         try:
#             if user!=None:
#                 login(request,user)
#                 pk=user.pk
#                 return redirect('customer_detail', pk=pk)
#                 # return HttpResponseRedirect('homepage')
#             else:
#                 messages.warning(request, 'Mật khẩu không đúng.')
#                 return HttpResponseRedirect('loginuser')

#         except user.DoesNotExist:
#             # Xử lý khi tài khoản không tồn tại
#             messages.warning(request, 'Tài khoản không tồn tại.')

def clicklogin(request):
    if request.method != "POST":
        # return HttpResponse("<h1> Method not allowed<h1>")
        return HttpResponseRedirect(reverse('loginuser'))
    else:
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_authenticated:
                # Nếu người dùng đã đăng nhập và không đăng nhập vào trang admin, sử dụng user.pk
                if username.isnumeric():
                    return redirect('customer_detail', pk=username)
                else:
                    return HttpResponseRedirect('admin')
                    # return HttpResponse("<h1> Bạn đang truy cập trang admin, hãy thoát ra trước khi truy cập giao diện cho KH<h1>")

            else:
                # Xử lý nếu người dùng chưa đăng nhập
                # Ví dụ: return redirect('home')
                return HttpResponseRedirect(reverse('loginuser'))
        else:
            messages.warning(
                request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
            return HttpResponseRedirect(reverse('loginuser'))


def LogoutUser(request):
    logout(request)
    request.user = None
    # return HttpResponseRedirect("loginuser")
    return redirect('loginuser')


@login_required(login_url="/loginuser/")
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Đảm bảo người dùng vẫn đăng nhập
            update_session_auth_hash(request, user)
            messages.success(request, 'Mật khẩu đã được thay đổi thành công.')
            return redirect('change_password')
        else:
            messages.error(request, 'Vui lòng kiểm tra lại thông tin đầu vào.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'stockwarehouse/change_password.html', {'form': form})


def cal_trading_power_customer(request):
    if request.method == 'POST':
        try:
            # Lấy thông tin từ yêu cầu
            pk = int(request.user.username)
            ticker = request.POST.get('ticker', '').upper()
            price = float(request.POST.get('price', ''))
        except (ValueError, KeyError) as e:
            return JsonResponse({'error': 'Tham số không hợp lệ'}, status=400)

        # Lấy thông tin tài khoản và biên độ cổ phiếu
        account = get_object_or_404(Account, pk=pk)
        margin = StockListMargin.objects.filter(stock=ticker).first()

        if not margin:
            return JsonResponse({'error': 'Cổ phiếu không hợp lệ'}, status=400)

        # Thực hiện tính toán
        if account.excess_equity > 0:
            initial_margin_requirement = margin.initial_margin_requirement
            max_value = abs(account.excess_equity /
                            (initial_margin_requirement / 100))
            qty = math.floor(max_value / price)
            string_qty = '{:,.0f}'.format(qty)

            # Trả về kết quả tính toán
            return JsonResponse({'qty': string_qty})
        else:
            return JsonResponse({'error': 'Không đủ vốn để mua cổ phiếu'}, status=400)

    # Trường hợp không phải POST
    return JsonResponse({'error': 'Yêu cầu không hợp lệ'}, status=400)


def assumption_sell_stock(request, pk, port_pk):
    pk = int(request.user.username)
    account = get_object_or_404(Account, pk=pk)
    portfolio = get_object_or_404(
        Portfolio, pk=port_pk, account=pk, sum_stock__gt=0)

    if portfolio.sum_stock > 0:
        if request.method == 'POST':
            form = SellingForm(request.POST)
            if form.is_valid():
                # Perform calculations or update the portfolio with selling details

                selling_price = form.cleaned_data['selling_price']
                selling_date = form.cleaned_data['selling_date']
                # do T2 nền phải 2 ngày sao mới về
                next_hold_number_days = (
                    selling_date - dt.now().date()).days + 2
                transaction_fee = -(selling_price + portfolio.avg_price) *  portfolio.sum_stock*account.transaction_fee
                tax_fee = selling_price * portfolio.sum_stock*account.tax*-1
                locked_interest_fee = account.total_temporarily_interest
                # tính phí ứng dựa trên giá trị bán không có phí va thuế
                advance_fee = selling_price *portfolio.sum_stock *account.interest_fee*next_hold_number_days/360
                total_expense = locked_interest_fee + advance_fee+transaction_fee+tax_fee
                profit = round((selling_price - portfolio.avg_price) * portfolio.sum_stock +total_expense, 0)

                return JsonResponse({
                    'Lợi nhuận ròng': '{:,.0f}'.format(profit),
                    'Thuế': '{:,.0f}'.format(tax_fee),
                    'Phí giao dịch': '{:,.0f}'.format(transaction_fee),
                    'Lãi vay': '{:,.0f}'.format(locked_interest_fee),
                    'Phí ứng tiền bán': '{:,.0f}'.format(advance_fee),
                })
        else:
            form = SellingForm()

        return render(request, 'stockwarehouse/sell_stock.html', {'form': form, 'portfolio': portfolio, 'account': account})
    else:
        return render(request, 'stockwarehouse/no_sell_stock.html', {'portfolio': portfolio})