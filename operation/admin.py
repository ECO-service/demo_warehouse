from django.contrib import admin
from .models import *
from operation.processing import *
from django.contrib.humanize.templatetags.humanize import intcomma
from django.contrib import messages
from django.utils import timezone
from django import forms
from django.core.exceptions import ValidationError
from realstockaccount.models import *
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from import_export.admin import ImportExportModelAdmin
from import_export.resources import ModelResource
from import_export.formats.base_formats import XLSX
from import_export.widgets import ForeignKeyWidget
from import_export.fields import Field
from django.utils.timezone import now
from rangefilter.filters import DateRangeFilter
from django.contrib.admin import DateFieldListFilter


# Register your models here.


class PartnerInfoProxyAdmin(admin.ModelAdmin):
    models = PartnerInfo
    list_display = ['name', 'ratio_trading_fee','ratio_interest_fee','ratio_advance_fee','method_interest','total_date_interest']
   
admin.site.register(PartnerInfo,PartnerInfoProxyAdmin)


class AccountAdmin(admin.ModelAdmin):
    model= Account
    ordering = ['-nav']
    list_display = ['name','partner', 'id', 'formatted_cash_balance', 'formatted_interest_cash_balance', 'formatted_market_value', 'formatted_nav', 'formatted_margin_ratio','formatted_excess_equity','formatted_total_temporarily_pl', 'custom_status_display','interest_payments']
    fieldsets = [
        ('Thông tin cơ bản', {'fields': ['name','cpd','user_created','description']}),
        ('Biểu phí tài khoản', {'fields': ['interest_fee', 'transaction_fee', 'tax','credit_limit','maintenance_margin_ratio','force_sell_margin_ratio']}),
        ('Trạng thái tài khoản', {'fields': ['cash_balance', 'interest_cash_balance','advance_cash_balance','net_cash_flow','net_trading_value','market_value','nav','initial_margin_requirement','margin_ratio','excess_equity','custom_status_display','milestone_date_lated']}),
        ('Thông tin lãi và phí ứng', {'fields': ['total_loan_interest','total_interest_paid','total_temporarily_interest','total_advance_fee','total_advance_fee_paid','total_temporarily_advance_fee']}),
        ('Hiệu quả đầu tư', {'fields': ['total_pl','total_closed_pl','total_temporarily_pl',]}),
        ('Thành phần số dư tiền tính lãi', {'fields': ['cash_t0','cash_t1','cash_t2','total_buy_trading_value']}),
    ]
    readonly_fields = ['cash_balance', 'market_value', 'nav', 'margin_ratio', 'excess_equity', 'user_created', 'initial_margin_requirement', 'net_cash_flow', 'net_trading_value', 'custom_status_display','cash_t2','cash_t1',
                       'excess_equity', 'interest_cash_balance' , 'total_loan_interest','total_interest_paid','total_temporarily_interest','total_pl','total_closed_pl','total_temporarily_pl', 'user_modified',
                       'cash_t0','total_buy_trading_value','milestone_date_lated','advance_cash_balance','total_advance_fee','total_advance_fee_paid','total_temporarily_advance_fee'
                       ]
    search_fields = ['id','name']
    list_filter = ['name',]
    
    def save_model(self, request, obj, form, change):
        # Lưu người dùng đang đăng nhập vào trường user nếu đang tạo cart mới
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
        else:
            obj.user_modified = request.user.username
        super().save_model(request, obj, form, change)
    


    def formatted_number(self, value):
        # Format number with commas as thousand separators and no decimal places
        return '{:,.0f}'.format(value)

    def formatted_cash_balance(self, obj):
        return self.formatted_number(obj.cash_balance)
    def formatted_excess_equity(self, obj):
        return self.formatted_number(obj.excess_equity)

    def formatted_interest_cash_balance(self, obj):
        return self.formatted_number(obj.interest_cash_balance)

    def formatted_market_value(self, obj):
        return self.formatted_number(obj.market_value)

    def formatted_nav(self, obj):
        return self.formatted_number(obj.nav)

    def formatted_margin_ratio(self, obj):
        return f"{round(obj.margin_ratio * 100, 2)}%"


    def formatted_total_temporarily_pl(self, obj):
        return self.formatted_number(obj.total_temporarily_pl)
    # Add other formatted_* methods for other numeric fields

    actions = ['select_account_settlement']

    def interest_payments(self, obj):
        # Display a custom button in the admin list view with arrow formatting
        icon = 'fa-check' if obj.market_value == 0 and obj.total_temporarily_interest != 0 else 'fa-times'
        color = 'green' if obj.market_value == 0 and obj.total_temporarily_interest != 0 else 'gray'
        background_color = '#77cd8b' if color == 'green' else 'white'
        return format_html('<div style="text-align: center; width: 25px; margin: 0 auto; background-color: {0}; border: 1px solid {1}; padding: 5px; border-radius: 5px;"><i class="fas {2}" style="color: {3}; font-size: 12px;"></i></div>', background_color, color, icon, color)

    interest_payments.short_description = 'Tất toán'

    def select_account_settlement(self, request, queryset):
         # Check if the user is a superuser
        if request.user.is_superuser:
            # Custom action to reset selected accounts
            for account in queryset:
                status = setle_milestone_account(account)
                if status == True:
                    self.message_user(request, f'Đã tất toán {queryset.count()} tài khoản đã chọn.')
                else:
                    self.message_user(request, 'Tài khoản chưa đủ điều kiện để thanh toán lãi', level='ERROR')
        else:
            self.message_user(request, 'Bạn chưa có quyền thực hiện nghiệp vụ này.', level='ERROR')

    select_account_settlement.short_description = 'Tất toán tài khoản'

    
    formatted_cash_balance.short_description = 'Số dư tiền'
    formatted_interest_cash_balance.short_description = 'Số dư tính lãi'
    formatted_market_value.short_description = 'Giá trị thị trường'
    formatted_nav.short_description = 'Tài sản ròng'
    formatted_margin_ratio.short_description = 'Tỷ lệ kí quỹ'
    formatted_excess_equity.short_description = 'Dư kí quỹ'
    formatted_total_temporarily_pl.short_description = 'Tổng lãi lỗ'

    def custom_status_display(self, obj):
        if obj.status:
            # Thêm HTML cho màu sắc dựa trên điều kiện
            color = 'red' if 'giải chấp' in obj.status.lower() else 'green'
            # Thêm <br> để xuống dòng
            return format_html('<span style="color: {};">{}</span><br>', color, obj.status)
        return format_html('<span></span>')  # Trả về một span trống nếu status không tồn tại

    custom_status_display.short_description = 'Trạng thái'


admin.site.register(Account,AccountAdmin)


class AccountMilestoneAdmin(admin.ModelAdmin):
    model = AccountMilestone
    search_fields = ['account__name','account__id']
    list_display = ['account','created_at','milestone','formatted_net_cash_flow','formatted_net_trading_value','formatted_total_buy_trading_value','formatted_interest_paid','formatted_closed_pl']
    list_filter = ['account__name',]
    readonly_fields = ['account','created_at','milestone','formatted_net_cash_flow','formatted_net_trading_value','formatted_total_buy_trading_value','formatted_interest_paid','formatted_closed_pl']

    def has_add_permission(self, request):
        # Return False to disable the "Add" button
        return False
    
    def formatted_number(self, value):
        # Format number with commas as thousand separators and no decimal places
        return '{:,.0f}'.format(value)

    def formatted_net_cash_flow(self, obj):
        return self.formatted_number(obj.net_cash_flow)
    
    def formatted_net_trading_value(self, obj):
        return self.formatted_number(obj.net_trading_value)

    def formatted_total_buy_trading_value(self, obj):
        return self.formatted_number(obj.total_buy_trading_value)

    def formatted_interest_paid(self, obj):
        return self.formatted_number(obj.interest_paid)
    
    def formatted_closed_pl(self, obj):
        return self.formatted_number(obj.closed_pl)
    
    formatted_net_cash_flow.short_description = 'Nạp rút tiền ròng'
    formatted_net_trading_value.short_description = 'Giao dịch ròng'
    formatted_total_buy_trading_value.short_description = 'Tổng giá trị mua'
    formatted_interest_paid.short_description = 'Tổng lãi vay đã trả'
    formatted_closed_pl.short_description = 'Tổng lời lỗ đã chốt'
    
    
admin.site.register(AccountMilestone,AccountMilestoneAdmin)




class StockListMarginAdmin(admin.ModelAdmin):
    model= StockListMargin
    list_display = ['stock','initial_margin_requirement','formatted_max_loan_value','formatted_available_loan_value','ranking','exchanges','modified_at','user_created','custom_status_display']
    search_fields = ['stock',]
    readonly_fields = ['modified_at','user_created']
    def save_model(self, request, obj, form, change):
        # Lưu người dùng đang đăng nhập vào trường user nếu đang tạo cart mới
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
        else:
            obj.user_modified = request.user.username
        super().save_model(request, obj, form, change)
    
    def formatted_number(self, value):
        # Format number with commas as thousand separators and no decimal places
        return '{:,.0f}'.format(value)
    
    def formatted_max_loan_value(self, obj):
        return self.formatted_number(obj.max_loan_value)
    formatted_max_loan_value.short_description = 'Tổng giá trị cho vay'

    def formatted_available_loan_value(self, obj):
        if obj.available_loan_value is None:
            return None
        else:
            return self.formatted_number(obj.available_loan_value)
    formatted_available_loan_value.short_description = 'Giá trị cho vay khả dụng'
    
    def custom_status_display(self, obj):
        if obj.status:
            # Thêm HTML cho màu sắc dựa trên điều kiện
            color = 'red' if 'cảnh báo' in obj.status.lower() else 'green'
            # Thêm <br> để xuống dòng
            return format_html('<span style="color: {};">{}</span><br>', color, obj.status)
        return format_html('<span></span>')  # Trả về một span trống nếu status không tồn tại

    custom_status_display.short_description = 'Trạng thái'



admin.site.register(StockListMargin,StockListMarginAdmin)



class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        exclude = ['user_created', 'user_modified']
    


class CustomStockWidget(ForeignKeyWidget):
    """Dò tìm StockListMargin bằng tên hoặc mã cổ phiếu"""
    def clean(self, value, row=None, *args, **kwargs):
        return self.model.objects.filter(stock=value).first()

class TransactionResource(ModelResource):
    stock = Field(
        column_name='stock',
        attribute='stock',
        widget=CustomStockWidget(StockListMargin, field='stock')  # Tìm theo name hoặc symbol
    )

    class Meta:
        model = Transaction
        import_id_fields = []  
        skip_unchanged = True
        report_skipped = False
        use_bulk = False  # Tăng tốc độ import bằng bulk_create

    def before_import_row(self, row, **kwargs):
        
        """Kiểm tra dữ liệu trước khi import"""
        required_fields = ['date','account', 'stock', 'position', 'price', 'qty']
        
        # Kiểm tra trường bắt buộc không được để trống
        for field in required_fields:
            if not row.get(field):
                raise ValidationError(f"Lỗi: Trường '{field}' không được để trống.")
            
        """Chuyển đổi dữ liệu trước khi import"""
        position_map = {
            "mua": "buy",
            "bán": "sell",
            "buy": "buy",
            "sell": "sell"
        }
        
        # Chuẩn hóa vị trí giao dịch
        position = row.get("position", "").strip().lower()

        if position not in position_map:
            raise ValidationError(f"Lỗi: Giá trị position '{position}' không hợp lệ. Chỉ chấp nhận: {', '.join(position_map.keys())}")

        row["position"] = position_map[position]

        """Gán user đang đăng nhập vào user_created và user_modified"""
        request = kwargs.get('request')  # Lấy request để lấy user
        if request and request.user.is_authenticated:
            row["user_created"] = request.user.id
            row["user_modified"] = None
        # Tự động gán created_at theo thời gian hiện tại nếu chưa có
        if not row.get("created_at"):
            row["created_at"] = now()

        # Để trống modified_at
        row["modified_at"] = None  

        """Trả lỗi nếu không tìm được account"""
        account_id = row.get("account")
        account = Account.objects.filter(id=row.get("account")).first()
        if not account:
            raise ValidationError(f"Không tìm thấy tài khoản: {account_id}")
        row["account"] = account.id
        # Kiểm tra đối tác (partner) (nếu có cột partner)
        partner_id = row.get("partner")
        if partner_id:
            partner = PartnerInfo.objects.filter(id=partner_id).first()
            # kiểm tra nhập partner có đúng không
            if partner and account.partner != partner:
                raise ValidationError('Đối tác không khớp với tài khoản.')
            

        """Tính toán giá trị dựa theo logic save của model"""
        request = kwargs.get('request')
        if request and request.user.is_authenticated:
            row["user_created"] = request.user.id
            row["user_modified"] = request.user.username

        if not row.get("created_at"):
            row["created_at"] = now()
        row["modified_at"] = None  # Để trống modified_at

        # Lấy dữ liệu cần thiết
        price = float(row.get("price", 0))
        qty = int(row.get("qty", 0))
        # Kiểm tra điều kiện ràng buộc
        if price < 1000:
            raise ValidationError(f"Lỗi: Giá price = {price} quá thấp, phải >= 1000")
        if qty < 100:
            raise ValidationError(f"Lỗi: Số lượng qty = {qty} bị lẻ, phải >= 100")

        # # Tính toán giá trị giao dịch
        # row["total_value"] = price * qty
        # row["transaction_fee"] = row["total_value"] * (account.transaction_fee if account else 0)

        # if row.get("position") == "buy":
        #     row["tax"] = 0
        #     row["net_total_value"] = -row["total_value"] - row["transaction_fee"]
        # else:
        #     row["tax"] = row["total_value"] * (account.tax if account else 0)
        #     row["net_total_value"] = row["total_value"] - row["transaction_fee"] - row["tax"]

        # # Xử lý previous_date & previous_total_value
        # is_new = not row.get("id")  # Nếu không có ID => là bản ghi mới
        # if is_new and account and account.cpd:
        #     row["previous_date"] = row["date"]
        #     row["previous_total_value"] = row["total_value"]
        # else:
        #     row["previous_date"] = None
        #     row["previous_total_value"] = None
        
        # Kiểm tra số lượng có thể bán nếu là giao dịch bán
        if row["position"] == "sell":
            stock = StockListMargin.objects.filter(stock=row["stock"]).first()
            port = Portfolio.objects.filter(account=account, stock=stock).first()
            stock_hold = port.on_hold if port else 0
            sell_pending = Transaction.objects.filter(account=account, stock=stock, position="sell").aggregate(Sum('qty'))['qty__sum'] or 0
            max_sellable_qty = stock_hold - sell_pending

            if qty > max_sellable_qty:
                raise ValidationError({'qty': f'Không đủ cổ phiếu bán, tổng cổ phiếu khả dụng là {max_sellable_qty}'})
        return super().before_import_row(row, **kwargs)
    


class TransactionAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = TransactionResource
    formats = [XLSX]  # Chỉ cho phép import/export định dạng XLSX
    form = TransactionForm
    list_display_links = ['stock',]
    list_display = ['account','partner','date','stock','position','formatted_price','formatted_qty','formatted_net_total_value','created_at','user_created','formatted_transaction_fee','formatted_tax']
    readonly_fields = ['user_created','user_modified','transaction_fee','tax','total_value','net_total_value']
    fieldsets = (
        ('Thông tin giao dịch', {
            'fields': ('account','partner', 'date', 'stock', 'position', 'price', 'qty')
        }),
       
    )
    # search_fields = ['account__id','account__name','stock__stock']
    list_filter = [
        'account__name',
        'stock__stock',
        'partner__name',
        ('date', DateRangeFilter),  # Bộ lọc ngày từ ngày - đến ngày
    ]
    
    def get_readonly_fields(self, request, obj=None):
        # Nếu đang chỉnh sửa bản ghi đã tồn tại, trường account sẽ là chỉ đọc
        if obj:
            return ['account','partner', 'stock']
        return []
    
    def save_model(self, request, obj, form, change):
        # Lưu người dùng đang đăng nhập vào trường user nếu đang tạo cart mới
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
            super().save_model(request, obj, form, change)
        else:
            today = timezone.now().date()
            obj.user_modified = request.user.username
            milestone_account = AccountMilestone.objects.filter(account =obj.account).order_by('-created_at').first()
            if milestone_account and obj.created_at < milestone_account.created_at:
                raise PermissionDenied("Bạn không có quyền sửa đổi bản ghi trong giai đoạn đã được tất toán.")
            else:
                if obj.created_at.date() != today:
                    if not request.user.is_superuser:
                        raise PermissionDenied("Bạn không có quyền sửa đổi bản ghi lịch sử.")
                    else:
                        super().save_model(request, obj, form, change)
                        if obj.total_value != obj.previous_total_value or obj.previous_date != obj.date:
                            # Chạy lại phí tk tổng
                            delete_and_recreate_account_expense(obj.account)
                            # Chạy lại phí tk con
                            if obj.partner.method_interest =='total_buy_value':
                                account_partner = AccountPartner.objects.filter(account = obj.account, partner = obj.partner).first()
                                if account_partner:
                                    delete_and_recreate_account_partner_expense(obj.account, account_partner)
                            # Thêm dòng cảnh báo cho siêu người dùng
                            messages.warning(request, "Sao kê phí lãi vay đã được cập nhật.")
                else:
                    super().save_model(request, obj, form, change)
    
    

                
    



    def formatted_number(self, value):
        # Format number with commas as thousand separators and no decimal places
        return '{:,.0f}'.format(value)
    
    def formatted_price(self, obj):
        return self.formatted_number(obj.price)
    def formatted_tax(self, obj):
        return self.formatted_number(obj.tax)
    
    def formatted_transaction_fee(self, obj):
        return self.formatted_number(obj.transaction_fee)
    
    def formatted_qty(self, obj):
        return self.formatted_number(obj.qty)
    
    def formatted_net_total_value(self, obj):
        return self.formatted_number(obj.net_total_value)

    # Add other formatted_* methods for other numeric fields

    formatted_transaction_fee.short_description = 'Phí giao dịch'
    formatted_tax.short_description = 'Thuế'
    formatted_price.short_description = 'Giá'
    formatted_qty.short_description = 'Khối lượng'
    formatted_net_total_value.short_description = 'Giá trị giao dịch ròng'

admin.site.register(Transaction,TransactionAdmin)

class PortfolioAdmin(admin.ModelAdmin):
    model = Portfolio
    list_display = ['account', 'stock', 'formatted_market_price', 'formatted_avg_price', 'formatted_on_hold', 'formatted_receiving_t1', 'formatted_receiving_t2', 'formatted_profit', 'percent_profit', 'formatted_sum_stock']
    readonly_fields = ['account','stock','market_price','avg_price','on_hold','receiving_t1','receiving_t2','profit','percent_profit', 'sum_stock', 'market_value']
    search_fields = ['stock','account__id','account__name']
    list_filter = ['account__name',]
    def get_queryset(self, request):
        # Chỉ trả về các bản ghi có sum_stock > 0
        return super().get_queryset(request).filter(sum_stock__gt=0)

    def formatted_number(self, value):
        # Format number with commas as thousand separators and no decimal places
        return '{:,.0f}'.format(value)

    def formatted_market_price(self, obj):
        return self.formatted_number(obj.market_price)

    def formatted_avg_price(self, obj):
        return self.formatted_number(obj.avg_price)

    def formatted_on_hold(self, obj):
        return self.formatted_number(obj.on_hold)

    def formatted_receiving_t1(self, obj):
        return self.formatted_number(obj.receiving_t1)

    def formatted_receiving_t2(self, obj):
        return self.formatted_number(obj.receiving_t2)

    def formatted_profit(self, obj):
        return self.formatted_number(obj.profit)


    def formatted_sum_stock(self, obj):
        return self.formatted_number(obj.sum_stock)

    formatted_market_price.short_description = 'Giá thị trường'
    formatted_avg_price.short_description = 'Giá TB'
    formatted_on_hold.short_description = 'Khả dụng'
    formatted_receiving_t1.short_description = 'Chờ về T+1'
    formatted_receiving_t2.short_description = 'Chờ về T+2'
    formatted_profit.short_description = 'Lợi nhuận'
    formatted_sum_stock.short_description = 'Tổng cổ phiếu'

    def has_add_permission(self, request):
        # Return False to disable the "Add" button
        return False
    
admin.site.register(Portfolio,PortfolioAdmin)

class ExpenseStatementAdmin(admin.ModelAdmin):
    model = ExpenseStatement
    list_display = ['account', 'date', 'type', 'formatted_amount', 'description']
    search_fields = ['account__id','account__name']
    list_filter = ['account__name','type']


    def formatted_amount(self, obj):
        return '{:,.0f}'.format(obj.amount)
    

    formatted_amount.short_description = 'Số tiền'

    def has_add_permission(self, request):
        # Return False to disable the "Add" button
        return False

    def save_model(self, request, obj, form, change):
        # Lưu người dùng đang đăng nhập vào trường user nếu đang tạo cart mới
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
            super().save_model(request, obj, form, change)
        else:
            today = timezone.now().date()
            obj.user_modified = request.user.username
            milestone_account = AccountMilestone.objects.filter(account =obj.account).order_by('-created_at').first()
            if milestone_account and obj.created_at < milestone_account.created_at:
                raise PermissionDenied("Bạn không có quyền sửa đổi bản ghi trong giai đoạn đã được tất toán.")
            else:
                if obj.type !='interest':
                    messages.warning(request, "Phí và thuế sẽ tự động update khi chỉnh sổ lệnh")
                    raise PermissionDenied("Không cần chỉnh sửa")
                else:
                    if obj.created_at.date() != today:
                        if not request.user.is_superuser:
                            raise PermissionDenied("Bạn không có quyền sửa đổi bản ghi.")
                        else:
                            # Thêm dòng cảnh báo cho siêu người dùng
                            if obj.type =='interest':
                                messages.warning(request, "Lãi vay tạm tính đã được cập nhật")
                                super().save_model(request, obj, form, change)
                    else:       
                        super().save_model(request, obj, form, change)

admin.site.register(ExpenseStatement, ExpenseStatementAdmin)

class CashTransferForm(forms.ModelForm):
    class Meta:
        model = CashTransfer
        exclude = ['user_created', 'user_modified']

    # def clean(self):
    #     cleaned_data = super().clean()
    #     change = self.instance.pk is not None  # Kiểm tra xem có phải là sửa đổi không

    #     today = timezone.now().date()

    #     # Kiểm tra quyền
    #     if change and self.instance.created_at.date() != today:
    #         raise ValidationError("Bạn không có quyền sửa đổi các bản ghi được tạo ngày trước đó.")

    #     return cleaned_data

class CashTransferAdmin(admin.ModelAdmin):
    form  = CashTransferForm
    list_display = ['account','partner', 'date', 'formatted_amount', 'user_created', 'user_modified', 'created_at']
    readonly_fields = ['user_created', 'user_modified']
    search_fields = ['account__id','account__name']
    list_filter = [
        'account__name',
        'partner__name',
        ('date', DateRangeFilter),  # Bộ lọc ngày từ ngày - đến ngày
    ]
    

    def get_readonly_fields(self, request, obj=None):
        # Nếu đang chỉnh sửa bản ghi đã tồn tại, trường account sẽ là chỉ đọc
        if obj:
            return ['account']
        return []
    
    def formatted_amount(self, obj):
        return '{:,.0f}'.format(obj.amount)
    

    formatted_amount.short_description = 'Số tiền'
    

    
    def save_model(self, request, obj, form, change):
        # Lưu người dùng đang đăng nhập vào trường user nếu đang tạo cart mới
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
            super().save_model(request, obj, form, change)
        else:
            today = timezone.now().date()
            obj.user_modified = request.user.username
            milestone_account = AccountMilestone.objects.filter(account =obj.account).order_by('-created_at').first()
            if milestone_account and obj.created_at < milestone_account.created_at:
                raise PermissionDenied("Bạn không có quyền sửa đổi bản ghi trong giai đoạn đã được tất toán.")
            else:
                if obj.created_at.date() != today:
                    if not request.user.is_superuser:
                        raise PermissionDenied("Bạn không có quyền sửa đổi bản ghi.")
                    else:
                        # Thêm dòng cảnh báo cho siêu người dùng
                        messages.warning(request, "Số dư tiền và tài sản đã được cập nhật lại")
                        super().save_model(request, obj, form, change)
                        
                else:
                    super().save_model(request, obj, form, change)

        


admin.site.register(CashTransfer,CashTransferAdmin)