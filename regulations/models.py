from django.db import models
from django.contrib.auth.models import User, Group

# Create your models here.
class OperationRegulations (models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name= 'Tên')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    modified_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Ngày tạo' )
    description = models.TextField(max_length=255, verbose_name= 'Mô tả')
    parameters = models.FloatField(verbose_name= 'Tham số quy định')
    user_created = models.ForeignKey(User,on_delete=models.CASCADE,related_name='Regulatio_user',null=True, blank= True,verbose_name="Người tạo")
    user_modified = models.CharField(max_length=150, blank=True, null=True,verbose_name="Người chỉnh sửa")
    class Meta:
         verbose_name = 'Quy định hoạt động'
         verbose_name_plural = 'Quy định hoạt động'
    
    def __str__(self):
        return str(self.name) 
    


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


