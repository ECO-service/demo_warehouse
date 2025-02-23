from django.db import models
from django.contrib.auth.models import User, Group

    


class BotTelegram(models.Model):
    name = models.CharField(max_length=255, verbose_name="Tên bot")
    token = models.CharField(max_length=255, unique=True, verbose_name="Token Bot")
    bot_id = models.CharField(max_length=50, unique=True, verbose_name="ID Bot")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")

    class Meta:
        verbose_name = "Bot Telegram"
        verbose_name_plural = "Bots Telegram"

    def __str__(self):
        return self.name


