"""
核心数据模型
"""

from django.db import models
from django.contrib.auth.models import User


class BaseModel(models.Model):
    """基础模型类"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        abstract = True


class SystemLog(BaseModel):
    """系统日志模型"""
    
    LEVEL_CHOICES = [
        ('debug', '调试'),
        ('info', '信息'),
        ('warning', '警告'),
        ('error', '错误'),
    ]
    
    level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
        default='info',
        verbose_name="日志级别"
    )
    message = models.TextField(verbose_name="日志消息")
    module = models.CharField(max_length=100, verbose_name="模块名称")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="用户"
    )
    extra_data = models.JSONField(
        default=dict,
        verbose_name="额外数据"
    )
    
    class Meta:
        verbose_name = "系统日志"
        verbose_name_plural = "系统日志"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_level_display()}: {self.message[:50]}"


