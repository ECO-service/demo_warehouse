from django.contrib import admin
from .models import *

# Register your models here.


class OperationRegulationsAdmin(admin.ModelAdmin):
    model  = OperationRegulations
    list_display = ['name', 'parameters','description', 'user_created', 'user_modified', 'created_at']
    readonly_fields = ['user_created', 'user_modified']
    search_fields = ['name',]

    # def formatted_arameters(self, obj):
    #     return '{:,.5f}'.format(obj.parameters)

    # formatted_arameters.short_description = 'Thông số'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Kiểm tra xem có phải là tạo mới hay không
            obj.user_created = request.user
         # Check if the record is being edited
        else:
            obj.user_modified = request.user.username
                
        super().save_model(request, obj, form, change)

        


admin.site.register(OperationRegulations,OperationRegulationsAdmin)