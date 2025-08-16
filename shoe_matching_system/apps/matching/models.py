"""
匹配算法应用模型
"""

from django.db import models


class MatchingTask(models.Model):
    """匹配任务模型"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '处理失败'),
    ]
    
    task_id = models.CharField(max_length=255, unique=True, verbose_name="任务ID")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    
    # 匹配参数
    margin_distance = models.DecimalField(
        max_digits=3, decimal_places=1, 
        default=2.5, verbose_name="余量距离"
    )
    
    # 关联模型
    shoe_model = models.ForeignKey(
        'core.ShoeModel',
        on_delete=models.CASCADE,
        verbose_name="鞋模"
    )
    
    # 结果数据
    result_data = models.JSONField(default=dict, verbose_name="匹配结果")
    
    # 时间信息
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    
    class Meta:
        verbose_name = "匹配任务"
        verbose_name_plural = "匹配任务"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"匹配任务: {self.task_id}"
