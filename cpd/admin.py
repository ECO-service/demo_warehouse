from django.contrib import admin
from .models import *

# Register your models here.
class ClientPartnerInfoAdmin(admin.ModelAdmin):
    model= ClientPartnerInfo
    list_display = ['full_name', 'id', 'rank', 'phone','commission']
    search_fields = ['id','full_name']
    readonly_fields = ['commission']

admin.site.register(ClientPartnerInfo,ClientPartnerInfoAdmin)

class ClientPartnerCommissionAdmin(admin.ModelAdmin):
    model= ClientPartnerCommission
    list_display = ('cp', 'month_year_str', 'formatted_total_value', 'formatted_trading_fee_spreads', 'formatted_commission_back', 'formatted_total_revenue', 'formatted_total_commission')
    search_fields = ['cp__full_name','month_year_str']
    list_filter = ['cp__full_name','month_year_str']
    readonly_fields = ['user_created', 'user_modified','total_value','trading_fee_spreads','commission_back','total_revenue','total_commission']
    ordering = ['-total_commission']

    def has_add_permission(self, request):
        # Return False to disable the "Add" button
        return False
    def get_queryset(self, request):
        # Chỉ trả về các bản ghi có sum_stock > 0
        return super().get_queryset(request).filter(total_value__gt=0)
    
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
    
    def formatted_trading_fee_spreads(self, obj):
        return self.formatted_number(obj.trading_fee_spreads)
    
    def formatted_total_value(self, obj):
        return self.formatted_number(obj.total_value)
    
    def formatted_commission_back(self, obj):
        return self.formatted_number(obj.commission_back)
    
    def formatted_total_revenue(self, obj):
        return self.formatted_number(obj.total_revenue)
    
    def formatted_total_commission(self, obj):
        return self.formatted_number(obj.total_commission)

    # Add other formatted_* methods for other numeric fields

    
    formatted_total_value.short_description = 'Tổng GTGD'
    formatted_trading_fee_spreads.short_description = 'DT chênh lệch PGD'
    formatted_total_revenue.short_description = 'Tổng Doanh thu tính thu nhập'
    formatted_total_commission.short_description = 'Thu nhập CTV'
    formatted_commission_back.short_description = 'HH HSC trả'

admin.site.register(ClientPartnerCommission, ClientPartnerCommissionAdmin)