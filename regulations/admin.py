from django.contrib import admin
from .models import *

# Register your models here.



@admin.register(BotTelegram)
class BotTelegramAdmin(admin.ModelAdmin):
    list_display = ("name", "bot_id", "token", "created_at", "updated_at")
    search_fields = ("name", "bot_id")
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "updated_at")
