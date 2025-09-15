"""
匹配功能数据模型
"""

from django.db import models
from apps.core.models import BaseModel
from apps.shoes.models import ShoeModel
from apps.blanks.models import BlankCategory
import uuid


class MatchingTask(BaseModel):
    """匹配任务模型"""
    
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    
    # 任务基本信息
    task_id = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="任务ID"
    )
    shoe_model = models.ForeignKey(
        ShoeModel, 
        on_delete=models.CASCADE,
        verbose_name="鞋模"
    )
    selected_categories = models.ManyToManyField(
        BlankCategory, 
        verbose_name="选择的粗胚分类"
    )
    
    # 匹配参数
    clearance = models.FloatField(
        default=2.0, 
        verbose_name="间隙要求(mm)"
    )
    threshold = models.CharField(
        max_length=10,
        choices=[
            ('min', '严格标准'),
            ('p10', 'P10标准'),
            ('p15', 'P15标准'),
            ('p20', 'P20标准'),
        ],
        default='p15',
        verbose_name="通过标准"
    )
    enable_scaling = models.BooleanField(
        default=True,
        verbose_name="启用自适应缩放"
    )
    enable_multi_start = models.BooleanField(
        default=True,
        verbose_name="启用多起点对齐"
    )
    max_scale = models.FloatField(
        default=1.03,
        verbose_name="最大缩放比例"
    )
    
    # 任务状态
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        verbose_name="状态"
    )
    progress = models.IntegerField(
        default=0,
        verbose_name="进度百分比"
    )
    current_step = models.TextField(
        blank=True,
        verbose_name="当前步骤"
    )
    
    # 结果数据
    result_data = models.JSONField(
        default=dict, 
        verbose_name="匹配结果"
    )
    summary_data = models.JSONField(
        default=dict,
        verbose_name="汇总数据"
    )
    
    # 时间信息
    started_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="开始时间"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, 
        verbose_name="完成时间"
    )
    processing_time = models.FloatField(
        null=True, blank=True,
        verbose_name="处理时间(秒)"
    )
    
    # 输出文件路径
    report_file = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="报告文件路径"
    )
    heatmap_dir = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="热图目录路径"
    )
    
    class Meta:
        verbose_name = "匹配任务"
        verbose_name_plural = "匹配任务"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"匹配任务: {self.task_id}"
    
    def save(self, *args, **kwargs):
        if not self.task_id:
            # 生成唯一任务ID
            self.task_id = f"match_{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)
    
    @property
    def candidate_count(self):
        """获取候选粗胚数量"""
        if self.result_data and 'results' in self.result_data:
            return len(self.result_data['results'])
        return 0
    
    @property
    def passed_count(self):
        """获取通过的候选数量"""
        if not self.result_data or 'results' not in self.result_data:
            return 0
        
        threshold_key = f'pass_{self.threshold}'
        return sum(1 for r in self.result_data['results'] if r.get(threshold_key, False))
    
    @property
    def best_match(self):
        """获取最佳匹配结果"""
        if not self.result_data or 'results' not in self.result_data:
            return None
        
        results = self.result_data['results']
        if not results:
            return None
        
        # 按覆盖率、体积比、P15间隙排序
        sorted_results = sorted(results, key=lambda x: (
            -x.get('inside_ratio', 0),
            x.get('volume_ratio', float('inf')),
            -x.get('p15_clearance', 0)
        ))
        
        return sorted_results[0] if sorted_results else None
