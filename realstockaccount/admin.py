from django import forms
from django.contrib import admin
from realstockaccount.models import *
from django.contrib.admin.views.main import ChangeList
from django.db.models import Count, Sum
# Register your models here.




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
    




class MyChangeList1(ChangeList):
    def get_total_amount(self, queryset):
        total_amount = queryset.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
        return "{:,.0f}".format(total_amount,0)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).filter(type__in=['cash_in','cash_out'])
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
    list_display = ['type','date','partner', 'formatted_amount','description', 'user_created', 'created_at']
    readonly_fields = ['user_created', 'user_modified',]
    search_fields = ['account__id','partner__name']
    list_filter = ['partner__name']
    
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
