from django import forms
from django.contrib import admin
from realstockaccount.models import *
from django.contrib.admin.views.main import ChangeList
from django.db.models import Count, Sum
# Register your models here.


class RealCashTransferForm(forms.ModelForm):
    class Meta:
        model = RealStockAccountCashTransfer
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        change = self.instance.pk is not None  # Kiểm tra xem có phải là sửa đổi không

        today = timezone.now().date()

        # Kiểm tra quyền
        if change and self.instance.created_at.date() != today:
            raise forms.ValidationError("Bạn không có quyền sửa đổi các bản ghi được tạo ngày trước đó.")

        return cleaned_data


class BankCashTransferForm(forms.ModelForm):
    partner = forms.ModelChoiceField(queryset=PartnerInfo.objects.all())

    class Meta:
        model = BankCashTransfer
        fields = '__all__'
        widgets = {
            'partner': forms.Select(attrs={'placeholder': 'Luôn luôn nhập tên đối tác nếu là chuyển tiền giao dịch', 'required': True})
        }

    def clean(self):
        cleaned_data = super().clean()
        change = self.instance.pk is not None  # Kiểm tra xem có phải là sửa đổi không

        today = timezone.now().date()

        # Kiểm tra quyền
        if change and self.instance.created_at.date() != today:
            raise forms.ValidationError("Bạn không có quyền sửa đổi các bản ghi được tạo ngày trước đó.")

        return cleaned_data
    

class InternalBankCashTransferForm(forms.ModelForm):
    TYPE_CHOICES = [
        ('salary', 'Chi phí lương'),
        ('other_expense', 'Chi phí khác'),
        ('cp_commission','Hoa hồng CTV')
    ]
    type = forms.ChoiceField(choices=TYPE_CHOICES, required=True, initial='salary')
    class Meta:
        model = InternalBankCashTransfer
        exclude = ['partner', 'account']

    def clean(self):
        cleaned_data = super().clean()
        change = self.instance.pk is not None  # Kiểm tra xem có phải là sửa đổi không
        today = timezone.now().date()
        # Kiểm tra quyền
        if change and self.instance.created_at.date() != today:
            raise forms.ValidationError("Bạn không có quyền sửa đổi các bản ghi được tạo ngày trước đó.")
        return cleaned_data



class MyChangeList1(ChangeList):
    def get_total_amount(self, queryset):
        total_amount = queryset.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
        return "{:,.0f}".format(total_amount,0)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).filter(type='trade_transfer')
        self.total_amount = self.get_total_amount(queryset)
        return queryset
    
class MyChangeList2(ChangeList):
    def get_total_amount(self, queryset):
        total_amount = queryset.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
        return "{:,.0f}".format(total_amount,0)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).all()
        self.total_amount = self.get_total_amount(queryset)
        return queryset

class BankCashTransferAdmin(admin.ModelAdmin):
    form  = BankCashTransferForm
    list_display = ['source','type','date','account','partner', 'formatted_amount','description', 'user_created', 'created_at']
    readonly_fields = ['user_created', 'user_modified','customer_cash_id','type']
    search_fields = ['account__id','account__name']
    list_filter = ['account__name', 'partner__name']
    
    def get_changelist(self, request):
        return MyChangeList1
        
    def formatted_amount(self, obj):
        return '{:,.0f}'.format(obj.amount)

    formatted_amount.short_description = 'Số tiền'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
         # Check if the record is being edited
        else:
            obj.user_modified = request.user.username
                
        super().save_model(request, obj, form, change)

admin.site.register(BankCashTransfer,BankCashTransferAdmin)

class InternalBankCashTransferAdmin(admin.ModelAdmin):
    form  = InternalBankCashTransferForm
    list_display = ['source','type','date', 'formatted_amount','description', 'user_created', 'created_at']
    readonly_fields = ['user_created', 'user_modified','customer_cash_id']
    search_fields = ['description',]
    list_filter = ['type',]
    
    def get_changelist(self, request):
        return MyChangeList2
    
    def formatted_amount(self, obj):
        return '{:,.0f}'.format(obj.amount)

    formatted_amount.short_description = 'Số tiền'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
         # Check if the record is being edited
        else:
            obj.user_modified = request.user.username
                
        super().save_model(request, obj, form, change)

admin.site.register(InternalBankCashTransfer,InternalBankCashTransferAdmin)


class RealTradingPowerForm(forms.ModelForm):
    class Meta:
        model = RealTradingPower
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        change = self.instance.pk is not None  # Kiểm tra xem có phải là sửa đổi không

        today = timezone.now().date()

        # Kiểm tra quyền
        if change and self.instance.created_at.date() != today:
            raise forms.ValidationError("Bạn không có quyền sửa đổi các bản ghi được tạo ngày trước đó.")

        return cleaned_data

class RealTradingPowerAdmin(admin.ModelAdmin):
    form  = RealTradingPowerForm
    list_display = ['date', 'formatted_min_amount','formatted_max_amount','description', 'user_created', 'user_modified', 'created_at']
    readonly_fields = ['user_created', 'user_modified']
    search_fields = ['account__id','account__name']

    def formatted_min_amount(self, obj):
        return '{:,.0f}'.format(obj.min_amount)

    formatted_min_amount.short_description = 'Sức mua tối thiểu'

    def formatted_max_amount(self, obj):
        return '{:,.0f}'.format(obj.max_amount)

    formatted_max_amount.short_description = 'sức mua tối đa'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
         # Check if the record is being edited
        else:
            obj.user_modified = request.user.username
                
        super().save_model(request, obj, form, change)

        


admin.site.register(RealTradingPower,RealTradingPowerAdmin)



class RealStockAccountForm(forms.ModelForm):
    class Meta:
        model = RealStockAccount
        fields = '__all__'


class RealStockAccountAdmin(admin.ModelAdmin):
    list_display = ['partner','description', 'formatted_cash_balance_open_account', 'formatted_net_cash_flow_operation','formatted_interest_cash_balance', 'formatted_cash_balance', 'formatted_market_value', 'formatted_nav']

    def formatted_amount(self, obj):
        return '{:,.0f}'.format(obj.amount)
    def formatted_interest_cash_balance(self, obj):
        return '{:,.0f}'.format(obj.interest_cash_balance)
    
    formatted_interest_cash_balance.short_description = 'Số dư tính lãi'
    
    
    def formatted_cash_balance_open_account(self, obj):
        return '{:,.0f}'.format(obj.cash_balance_open_account)
    
    formatted_cash_balance_open_account.short_description = 'Tổng dư tiền TK đang GD'


    def formatted_net_cash_flow_operation(self, obj):
        return '{:,.0f}'.format(obj.net_cash_flow_operation)
    formatted_net_cash_flow_operation.short_description = 'Nạp rút tiền ròng bổ sung vốn'

   
    def formatted_cash_balance(self, obj):
        return '{:,.0f}'.format(obj.cash_balance)
    formatted_cash_balance.short_description = 'Số dư tiền'

    def formatted_market_value(self, obj):
        return '{:,.0f}'.format(obj.market_value)
    formatted_market_value.short_description = 'Giá trị thị trường'

    def formatted_nav(self, obj):
        return '{:,.0f}'.format(obj.nav)
    formatted_nav.short_description = 'Tài sản ròng'

admin.site.register(RealStockAccount, RealStockAccountAdmin)

class ExpenseStatementRealStockAccountAdmin(admin.ModelAdmin):
    model = ExpenseStatementRealStockAccount
    list_display = ['account','get_partner', 'date', 'type', 'formatted_amount', 'description']
    # list_filter = ['account__account__name','account__partner__name','type']

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

admin.site.register(ExpenseStatementRealStockAccount,ExpenseStatementRealStockAccountAdmin)