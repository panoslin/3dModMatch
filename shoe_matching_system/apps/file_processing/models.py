"""
文件处理应用模型
"""

from django.db import models


class FileProcessingTask(models.Model):
    """文件处理任务模型"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '处理失败'),
    ]
    
    task_id = models.CharField(max_length=255, unique=True, verbose_name="任务ID")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    progress = models.IntegerField(default=0, verbose_name="进度(%)")
    
    # 关联的模型文件
    shoe_model = models.ForeignKey(
        'core.ShoeModel',
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name="鞋模文件"
    )
    blank_model = models.ForeignKey(
        'core.BlankModel', 
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name="粗胚文件"
    )
    
    # 处理结果
    result_data = models.JSONField(default=dict, verbose_name="处理结果数据")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    
    # 时间信息
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "文件处理任务"
        verbose_name_plural = "文件处理任务"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"处理任务: {self.task_id} - {self.get_status_display()}"
