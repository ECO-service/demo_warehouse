from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(SaleReportParam)
class SaleReportAdmin(admin.ModelAdmin):

    def formatted_amount(self, amount):
        if amount is not None:
            return '{:,.0f}'.format(amount)
        return None

    list_display = ['month_year_str','formatted_total_revenue','formatted_total_cost','formatted_total_expense','formatted_net_profit',]
    readonly_fields = ['formatted_transaction_fee_revenue','formatted_interest_revenue','formatted_advance_fee_revenue','formatted_brokerage_commission','formatted_total_revenue','formatted_transaction_costs_paid_securities', 'formatted_interest_costs_paid_securities', 'formatted_depository_fees','formatted_interest_paid_partners','formatted_advance_paid_partners','formatted_total_cost','formatted_cp_commission', 'formatted_salary','formatted_other_expense','formatted_total_expense','formatted_net_profit','formatted_total_deposit_interest_revenue']
    fieldsets = [
        ('Doanh thu', {'fields': ['formatted_transaction_fee_revenue','formatted_interest_revenue','formatted_advance_fee_revenue','formatted_brokerage_commission','formatted_total_deposit_interest_revenue','formatted_total_revenue']}),
        ('Giá vốn', {'fields': ['formatted_transaction_costs_paid_securities', 'formatted_interest_costs_paid_securities', 'formatted_depository_fees','formatted_interest_paid_partners','formatted_advance_paid_partners','formatted_total_cost']}),
        ('Chi phí vận hành', {'fields': ['formatted_cp_commission', 'formatted_salary','formatted_other_expense','formatted_total_expense',]}),
        ('Lợi nhuận ròng', {'fields': ['formatted_net_profit']}),
    ]    


    def formatted_transaction_fee_revenue(self, obj):
        return self.formatted_amount(obj.transaction_fee_revenue)
    
    formatted_transaction_fee_revenue.short_description = SaleReport._meta.get_field('transaction_fee_revenue').verbose_name
    
    def formatted_interest_revenue(self, obj):
        return self.formatted_amount(obj.interest_revenue)
    
    formatted_interest_revenue.short_description = SaleReport._meta.get_field('interest_revenue').verbose_name

    def formatted_advance_fee_revenue(self, obj):
        return self.formatted_amount(obj.advance_fee_revenue)
    
    formatted_advance_fee_revenue.short_description = SaleReport._meta.get_field('advance_fee_revenue').verbose_name

    def formatted_brokerage_commission(self, obj):
        return self.formatted_amount(obj.brokerage_commission)
    
    formatted_brokerage_commission.short_description = SaleReport._meta.get_field('brokerage_commission').verbose_name

    def formatted_total_revenue(self, obj):
        return self.formatted_amount(obj.total_revenue)
    
    formatted_total_revenue.short_description = SaleReport._meta.get_field('total_revenue').verbose_name

    def formatted_transaction_costs_paid_securities(self, obj):
        return self.formatted_amount(obj.transaction_costs_paid_securities)
    
    formatted_transaction_costs_paid_securities.short_description = SaleReport._meta.get_field('transaction_costs_paid_securities').verbose_name

    def formatted_interest_costs_paid_securities(self, obj):
        return self.formatted_amount(obj.interest_costs_paid_securities)
    
    formatted_interest_costs_paid_securities.short_description = SaleReport._meta.get_field('interest_costs_paid_securities').verbose_name

    def formatted_depository_fees(self, obj):
        return self.formatted_amount(obj.depository_fees)
    
    formatted_depository_fees.short_description = SaleReport._meta.get_field('depository_fees').verbose_name

    def formatted_interest_paid_partners(self, obj):
        return self.formatted_amount(obj.interest_paid_partners)
    
    formatted_interest_paid_partners.short_description = SaleReport._meta.get_field('interest_paid_partners').verbose_name

    def formatted_advance_paid_partners(self, obj):
        return self.formatted_amount(obj.advance_paid_partners)
    
    formatted_advance_paid_partners.short_description = SaleReport._meta.get_field('advance_paid_partners').verbose_name

    def formatted_total_cost(self, obj):
        return self.formatted_amount(obj.total_cost)
    
    formatted_total_cost.short_description = SaleReport._meta.get_field('total_cost').verbose_name

    def formatted_cp_commission(self, obj):
        return self.formatted_amount(obj.cp_commission)
    
    formatted_cp_commission.short_description = SaleReport._meta.get_field('cp_commission').verbose_name

    def formatted_salary(self, obj):
        return self.formatted_amount(obj.salary)
    
    formatted_salary.short_description = SaleReport._meta.get_field('salary').verbose_name

    def formatted_other_expense(self, obj):
        return self.formatted_amount(obj.other_expense)
    
    formatted_other_expense.short_description = SaleReport._meta.get_field('other_expense').verbose_name

    def formatted_total_expense(self, obj):
        return self.formatted_amount(obj.total_expense)
    
    formatted_total_expense.short_description = SaleReport._meta.get_field('total_expense').verbose_name

    def formatted_net_profit(self, obj):
        return self.formatted_amount(obj.net_profit)
    
    formatted_net_profit.short_description = SaleReport._meta.get_field('net_profit').verbose_name

    
    def formatted_total_deposit_interest_revenue(self, obj):
        return self.formatted_amount(obj.total_deposit_interest_revenue)
    
    formatted_total_deposit_interest_revenue.short_description = SaleReport._meta.get_field('total_deposit_interest_revenue').verbose_name
# Đăng ký admin cho model SaleReport
admin.site.register(SaleReport, SaleReportAdmin)