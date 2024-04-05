from django.contrib import admin
from .models import *
from django import forms
from django.utils.html import format_html
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from operation.processing import setle_milestone_account_partner
# Register your models here.

class PartnerInfoProxyAdmin(admin.ModelAdmin):
    models = PartnerInfoProxy
    list_display = ['name', 'ratio_trading_fee','ratio_interest_fee','ratio_advance_fee','method_interest','total_date_interest']
   
admin.site.register(PartnerInfoProxy,PartnerInfoProxyAdmin)

class AccountPartnerAdmin(admin.ModelAdmin):
    model= AccountPartner
    ordering = ['-nav']
    list_display = ['account','partner', 'id', 'formatted_cash_balance', 'formatted_interest_cash_balance', 'formatted_market_value', 'formatted_nav', 'margin_ratio','formatted_excess_equity','formatted_total_temporarily_pl', 'custom_status_display']
    fieldsets = [
        ('Thông tin cơ bản', {'fields': ['account','partner','description']}),
        ('Trạng thái tài khoản', {'fields': ['cash_balance', 'interest_cash_balance','advance_cash_balance','net_cash_flow','net_trading_value','market_value','nav','initial_margin_requirement','margin_ratio','excess_equity','custom_status_display','milestone_date_lated']}),
        ('Thông tin lãi và phí ứng', {'fields': ['total_loan_interest','total_interest_paid','total_temporarily_interest','total_advance_fee','total_advance_fee_paid','total_temporarily_advance_fee']}),
        ('Hiệu quả đầu tư', {'fields': ['total_pl','total_closed_pl','total_temporarily_pl',]}),
        ('Thành phần số dư tiền tính lãi', {'fields': ['cash_t0','cash_t1','cash_t2','total_buy_trading_value']}),
    ]
    readonly_fields = ['cash_balance', 'market_value', 'nav', 'margin_ratio', 'excess_equity','initial_margin_requirement', 'net_cash_flow', 'net_trading_value', 'custom_status_display','cash_t2','cash_t1',
                       'excess_equity', 'interest_cash_balance' , 'total_loan_interest','total_interest_paid','total_temporarily_interest','total_pl','total_closed_pl','total_temporarily_pl', 
                       'cash_t0','total_buy_trading_value','milestone_date_lated','advance_cash_balance','total_advance_fee','total_advance_fee_paid','total_temporarily_advance_fee',
                       'account','partner'
                       ]
    search_fields = ['id','account__name']
    list_filter = ['partner__name','account__name',]

    actions = ['select_account_partner_settlement']

    def select_account_partner_settlement(self, request, queryset):
         # Check if the user is a superuser
        if request.user.is_superuser:
            # Custom action to reset selected accounts
            for account_partner in queryset:
                status = setle_milestone_account_partner(account_partner)
                if status == True:
                    self.message_user(request, f'Đã tất toán {queryset.count()} tài khoản đã chọn.')
                else:
                    self.message_user(request, 'Tài khoản chưa đủ điều kiện để thanh toán lãi', level='ERROR')
        else:
            self.message_user(request, 'Bạn chưa có quyền thực hiện nghiệp vụ này.', level='ERROR')

    select_account_partner_settlement.short_description = 'Tất toán tài khoản đối tác'
    
    def get_queryset(self, request):
    # Chỉ trả về các bản ghi có nav khác 0
        return super().get_queryset(request).exclude(nav=0)

    
    def has_add_permission(self, request):
        # Return False to disable the "Add" button
        return False
    

    # def has_change_permission(self, request, obj=None):
    #     return False
    
    def has_delete_permission(self, request, obj=None):
        return False

    
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
        return self.formatted_number(obj.margin_ratio)


    def formatted_total_temporarily_pl(self, obj):
        return self.formatted_number(obj.total_temporarily_pl)
    # Add other formatted_* methods for other numeric fields


    def interest_payments(self, obj):
        # Display a custom button in the admin list view with arrow formatting
        icon = 'fa-check' if obj.market_value == 0 and obj.total_temporarily_interest != 0 else 'fa-times'
        color = 'green' if obj.market_value == 0 and obj.total_temporarily_interest != 0 else 'gray'
        background_color = '#77cd8b' if color == 'green' else 'white'
        return format_html('<div style="text-align: center; width: 25px; margin: 0 auto; background-color: {0}; border: 1px solid {1}; padding: 5px; border-radius: 5px;"><i class="fas {2}" style="color: {3}; font-size: 12px;"></i></div>', background_color, color, icon, color)

    
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


admin.site.register(AccountPartner,AccountPartnerAdmin)

class TransactionPartnerForm(forms.ModelForm):
    class Meta:
        model = TransactionPartner
        exclude = ['user_created', 'user_modified']

class TransationPartnerAdmin(admin.ModelAdmin):
    form = TransactionPartnerForm
    list_display_links = ['stock',]
    list_display = ['account','partner','date','stock','position','formatted_price','formatted_qty','formatted_partner_net_total_value','created_at','user_created',]
    readonly_fields = ['account','partner', 'date', 'stock', 'position', 'price', 'qty','user_created','user_modified','transaction_fee','tax','total_value',]
    fieldsets = (
        ('Thông tin giao dịch', {
            'fields': ('account','partner', 'date', 'stock', 'position', 'price', 'qty')
        }),
       
    )
    def has_add_permission(self, request):
        # Return False to disable the "Add" button
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    
    search_fields = ['account__id','account__name','stock__stock']
    list_filter = ['account__name',]

    def formatted_number(self, value):
        # Format number with commas as thousand separators and no decimal places
        return '{:,.0f}'.format(value)
    
    def formatted_price(self, obj):
        return self.formatted_number(obj.price)
    
    def formatted_qty(self, obj):
        return self.formatted_number(obj.qty)
    
    def formatted_net_total_value(self, obj):
        return self.formatted_number(obj.net_total_value)
    
    def formatted_partner_net_total_value(self, obj):
        return self.formatted_number(obj.partner_net_total_value)
    # Add other formatted_* methods for other numeric fields
    formatted_partner_net_total_value.short_description = 'Giá trị giao dịch ròng'
    formatted_price.short_description = 'Giá'
    formatted_qty.short_description = 'Khối lượng'
    formatted_net_total_value.short_description = 'Giá trị giao dịch ròng'

admin.site.register(TransactionPartner,TransationPartnerAdmin)

class PortfolioPartnerAdmin(admin.ModelAdmin):
    model = PortfolioPartner
    list_display = ['account', 'stock','get_partner', 'formatted_market_price', 'formatted_avg_price', 'formatted_on_hold', 'formatted_receiving_t1', 'formatted_receiving_t2', 'formatted_profit', 'percent_profit', 'formatted_sum_stock']
    readonly_fields = ['account','stock','market_price','avg_price','on_hold','receiving_t1','receiving_t2','profit','percent_profit', 'sum_stock', 'market_value']
    search_fields = ['stock','account__id','account__name']
    list_filter = ['account__partner__name','account__account',]
    
    def get_partner(self,obj):
        return obj.account.partner
    get_partner.short_description = 'Đối tác'
    
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
    
admin.site.register(PortfolioPartner,PortfolioPartnerAdmin)


class CashTransferPartnerForm(forms.ModelForm):
    class Meta:
        model = CashTransferPartner
        exclude = ['user_created', 'user_modified']

class CashTransferPartnerAdmin(admin.ModelAdmin):
    form  = CashTransferPartnerForm
    list_display = ['source','partner','account', 'date', 'formatted_amount', 'user_created', 'user_modified', 'created_at']
    readonly_fields = ['user_created', 'user_modified']
    search_fields = ['account__id','account__name']
    list_filter = ['partner__name',]

    def has_add_permission(self, request):
        # Return False to disable the "Add" button
        return False
    

    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def formatted_amount(self, obj):
        return '{:,.0f}'.format(obj.amount)
    
    formatted_amount.short_description = 'Số tiền'
    
admin.site.register(CashTransferPartner,CashTransferPartnerAdmin)

class ExpenseStatementPartnerAdmin(admin.ModelAdmin):
    model = ExpenseStatementPartner
    list_display = ['account','get_partner', 'date', 'type', 'formatted_amount', 'description']
    search_fields = ['account__account__name']
    list_filter = ['account__account__name','account__partner__name','type']

    def get_partner(self,obj):
        return obj.account.partner
    get_partner.short_description = 'Đối tác'
    
    def has_add_permission(self, request):
        # Return False to disable the "Add" button
        return False
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

admin.site.register(ExpenseStatementPartner, ExpenseStatementPartnerAdmin)







