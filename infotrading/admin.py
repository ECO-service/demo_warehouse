from django.contrib import admin
from .models import *

# Register your models here.



admin.site.register(DateNotTrading)

class StockPriceFilterAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'date', 'close', 'date_time')  # Các trường hiển thị trong danh sách
    search_fields = ('ticker',)  # Cho phép tìm kiếm theo ticker
    list_filter = ('date',)  # Thêm bộ lọc theo ngày
    ordering = ('-date',)  # Sắp xếp theo ngày giảm dần
    # date_hierarchy = 'date'  # Hiển thị phân cấp theo ngày
    
    # Tùy chỉnh các trường hiển thị khi xem chi tiết đối tượng
    fieldsets = (
        (None, {
            'fields': ('ticker', 'date',  'close',  'date_time')
        }),
    )

admin.site.register(StockPriceFilter, StockPriceFilterAdmin)
admin.site.register(DividendManage)