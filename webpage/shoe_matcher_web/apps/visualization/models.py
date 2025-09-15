"""
3D可视化数据模型
"""

from django.db import models
from apps.core.models import BaseModel


class VisualizationCache(BaseModel):
    """可视化缓存模型"""
    
    CONTENT_TYPE_CHOICES = [
        ('shoe_preview', '鞋模预览'),
        ('blank_preview', '粗胚预览'),
        ('heatmap', '匹配热图'),
        ('comparison', '对比视图'),
    ]
    
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        verbose_name="内容类型"
    )
    object_id = models.PositiveIntegerField(
        verbose_name="对象ID"
    )
    cache_key = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="缓存键"
    )
    
    # 可视化数据
    html_content = models.TextField(
        verbose_name="HTML内容"
    )
    metadata = models.JSONField(
        default=dict,
        verbose_name="元数据"
    )
    
    # 缓存管理
    is_valid = models.BooleanField(
        default=True,
        verbose_name="是否有效"
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="过期时间"
    )
    access_count = models.IntegerField(
        default=0,
        verbose_name="访问次数"
    )
    last_accessed = models.DateTimeField(
        null=True, blank=True,
        verbose_name="最后访问时间"
    )
    
    class Meta:
        verbose_name = "可视化缓存"
        verbose_name_plural = "可视化缓存"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['cache_key']),
            models.Index(fields=['is_valid', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.get_content_type_display()} - {self.cache_key}"
