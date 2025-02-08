import math
from django.http import HttpResponse
from .models import *
from django.template import loader
from statistics import mean
from django.http import JsonResponse
from infotrading.models import get_list_and_save_stock_price
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.contrib.auth import authenticate, login





def warehouse(request):
    # Xử lý logic cho trang warehouse ở đây
    if request.method == 'POST':
        action = request.POST.get('action', None)

        # Xử lý cập nhật giá thị trường cho các cổ phiếu trong danh sách
        if action == 'update_market_price':
            try:
                stock_list = Portfolio.objects.values_list('stock', flat=True).distinct()
                stock_list_python = list(stock_list)
                get_list_and_save_stock_price(stock_list_python)
                return JsonResponse({'message': 'Cập nhật giá thành công!'})
            except Exception as e:
                return JsonResponse({'error': f'Đã có lỗi xảy ra khi cập nhật giá: {str(e)}'}, status=500)

        # Xử lý tính toán số lượng tối đa có thể mua
        elif action == 'calculate_max_qty_buy':
            # Kiểm tra và lấy các dữ liệu từ request.POST
            account_id = request.POST.get('account', None)
            ticker = request.POST.get('ticker', '').upper()
            price = request.POST.get('price', None)

            # Kiểm tra xem có đủ thông tin chưa
            if not account_id or not ticker or not price:
                return JsonResponse({'error': 'Vui lòng nhập đầy đủ thông tin: tài khoản, mã cổ phiếu và giá'}, status=400)

            try:
                account = Account.objects.get(pk=account_id)
            except Account.DoesNotExist:
                return JsonResponse({'error': 'Không tìm thấy tài khoản'}, status=400)

            try:
                price = float(price)
            except ValueError:
                return JsonResponse({'error': 'Giá cổ phiếu không hợp lệ'}, status=400)

            margin = StockListMargin.objects.filter(stock=ticker).first()
            if not margin:
                return JsonResponse({'error': f'Cổ phiếu {ticker} không có trong danh sách cho vay'}, status=400)

            if account.excess_equity <= 0:
                return JsonResponse({'error': 'Tài khoản không có tiền thừa'}, status=400)

            # Tính toán số lượng tối đa có thể mua
            max_value = 0
            if margin.available_loan_value and margin.available_loan_value > 0:  # Kiểm tra xem có hạn mức vay không
                pre_max_value = account.excess_equity / (margin.initial_margin_requirement / 100)
                max_value = min(pre_max_value, account.credit_limit, margin.available_loan_value)
                qty = math.floor(max_value / price)
                return JsonResponse({'qty': '{:,.0f}'.format(qty)})
            else:
                return JsonResponse({'error': f'Hết sức mua cho cổ phiếu {ticker}'}, status=400)

    # Trả về template chung cho cả hai trường hợp
    return render(request, 'stockwarehouse/warehouse.html')


