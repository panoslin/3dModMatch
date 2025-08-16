"""
3D鞋模匹配系统核心数据模型
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import json


class BaseModel(models.Model):
    """基础模型类"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        abstract = True


class ShoeModel(BaseModel):
    """鞋模文件模型"""
    
    filename = models.CharField(max_length=255, verbose_name="文件名")
    file = models.FileField(upload_to='shoes/', verbose_name="鞋模文件")
    file_size = models.BigIntegerField(verbose_name="文件大小(字节)")
    
    # 几何特征数据
    volume = models.DecimalField(
        max_digits=10, decimal_places=3, 
        null=True, blank=True, 
        verbose_name="体积(立方毫米)"
    )
    bounding_box = models.JSONField(
        default=dict, 
        verbose_name="边界框信息",
        help_text="存储x_min, x_max, y_min, y_max, z_min, z_max"
    )
    key_features = models.JSONField(
        default=dict, 
        verbose_name="关键特征",
        help_text="存储几何特征向量和分析数据"
    )
    
    # 元数据
    file_format = models.CharField(
        max_length=10, 
        choices=[('3dm', 'Rhino 3DM'), ('mod', 'MOD格式')],
        verbose_name="文件格式"
    )
    points_count = models.IntegerField(
        default=0, 
        verbose_name="点数量"
    )
    
    # 用户信息
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        verbose_name="上传者"
    )
    
    # 状态
    is_processed = models.BooleanField(
        default=False, 
        verbose_name="是否已处理"
    )
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '待处理'),
            ('processing', '处理中'),
            ('completed', '已完成'),
            ('failed', '处理失败'),
        ],
        default='pending',
        verbose_name="处理状态"
    )
    
    class Meta:
        verbose_name = "鞋模文件"
        verbose_name_plural = "鞋模文件"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"鞋模: {self.filename}"
    
    @property
    def dimensions(self):
        """获取模型尺寸"""
        if not self.bounding_box:
            return None
        bb = self.bounding_box
        return {
            'length': bb.get('x_max', 0) - bb.get('x_min', 0),
            'width': bb.get('y_max', 0) - bb.get('y_min', 0), 
            'height': bb.get('z_max', 0) - bb.get('z_min', 0),
        }


class BlankModel(BaseModel):
    """粗胚文件模型"""
    
    filename = models.CharField(max_length=255, verbose_name="文件名")
    file = models.FileField(upload_to='blanks/', verbose_name="粗胚文件")
    file_size = models.BigIntegerField(verbose_name="文件大小(字节)")
    
    # 几何特征数据
    volume = models.DecimalField(
        max_digits=10, decimal_places=3,
        null=True, blank=True,
        verbose_name="体积(立方毫米)"
    )
    bounding_box = models.JSONField(
        default=dict,
        verbose_name="边界框信息"
    )
    key_features = models.JSONField(
        default=dict,
        verbose_name="关键特征"
    )
    
    # 成本信息
    material_cost = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name="材料成本(元)"
    )
    
    # 元数据
    file_format = models.CharField(
        max_length=10,
        choices=[('3dm', 'Rhino 3DM'), ('mod', 'MOD格式')],
        verbose_name="文件格式"
    )
    points_count = models.IntegerField(
        default=0,
        verbose_name="点数量"
    )
    
    # 状态
    is_processed = models.BooleanField(
        default=False,
        verbose_name="是否已处理"
    )
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '待处理'),
            ('processing', '处理中'), 
            ('completed', '已完成'),
            ('failed', '处理失败'),
        ],
        default='pending',
        verbose_name="处理状态"
    )
    
    class Meta:
        verbose_name = "粗胚文件"
        verbose_name_plural = "粗胚文件"
        ordering = ['volume']  # 按体积升序排列，便于找到最小合适的粗胚
    
    def __str__(self):
        return f"粗胚: {self.filename}"
    
    @property
    def dimensions(self):
        """获取模型尺寸"""
        if not self.bounding_box:
            return None
        bb = self.bounding_box
        return {
            'length': bb.get('x_max', 0) - bb.get('x_min', 0),
            'width': bb.get('y_max', 0) - bb.get('y_min', 0),
            'height': bb.get('z_max', 0) - bb.get('z_min', 0),
        }


class MatchingResult(BaseModel):
    """匹配结果模型"""
    
    shoe_model = models.ForeignKey(
        ShoeModel, 
        on_delete=models.CASCADE,
        verbose_name="鞋模"
    )
    blank_model = models.ForeignKey(
        BlankModel,
        on_delete=models.CASCADE, 
        verbose_name="粗胚"
    )
    
    # 匹配参数
    margin_distance = models.DecimalField(
        max_digits=3, decimal_places=1,
        default=2.5,
        validators=[MinValueValidator(0.5), MaxValueValidator(10.0)],
        verbose_name="余量距离(mm)"
    )
    
    # 匹配结果评分
    total_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0.0,
        verbose_name="总匹配分数(%)"
    )
    similarity_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0.0,
        verbose_name="几何相似度(%)"
    )
    material_utilization = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0.0,
        verbose_name="材料利用率(%)"
    )
    coverage_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0.0,
        verbose_name="覆盖度评分(%)"
    )
    size_compatibility_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0.0,
        verbose_name="尺寸兼容性评分(%)"
    )
    cost_effectiveness_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0.0,
        verbose_name="成本效益评分(%)"
    )
    
    # 余量分析
    average_margin = models.DecimalField(
        max_digits=4, decimal_places=1,
        default=0.0,
        verbose_name="平均余量(mm)"
    )
    min_margin = models.DecimalField(
        max_digits=4, decimal_places=1,
        default=0.0,
        verbose_name="最小余量(mm)"
    )
    max_margin = models.DecimalField(
        max_digits=4, decimal_places=1,
        default=0.0,
        verbose_name="最大余量(mm)"
    )
    
    # 匹配状态
    is_optimal = models.BooleanField(
        default=False,
        verbose_name="是否为最优匹配"
    )
    is_feasible = models.BooleanField(
        default=True,
        verbose_name="是否可行（满足余量要求）"
    )
    
    # 详细分析数据
    analysis_details = models.JSONField(
        default=dict,
        verbose_name="详细分析数据",
        help_text="存储完整的几何分析和匹配数据"
    )
    
    # 计算时间
    computation_time = models.FloatField(
        null=True, blank=True,
        verbose_name="计算耗时(秒)"
    )
    
    class Meta:
        verbose_name = "匹配结果"
        verbose_name_plural = "匹配结果"
        unique_together = ['shoe_model', 'blank_model', 'margin_distance']
        ordering = ['-material_utilization', 'blank_model__volume']  # 优先材料利用率高，体积小的
        indexes = [
            models.Index(fields=['shoe_model', 'is_optimal']),
            models.Index(fields=['material_utilization']),
            models.Index(fields=['is_feasible']),
        ]
    
    def __str__(self):
        return f"匹配: {self.shoe_model.filename} → {self.blank_model.filename}"
    
    @property
    def cost_savings(self):
        """计算相对于次优方案的成本节省"""
        if not hasattr(self, '_cost_savings'):
            # 查找同一鞋模的次优方案
            alternatives = MatchingResult.objects.filter(
                shoe_model=self.shoe_model,
                is_feasible=True
            ).exclude(id=self.id).order_by('-material_utilization')[:1]
            
            if alternatives.exists():
                alt = alternatives.first()
                self._cost_savings = (
                    (alt.blank_model.volume - self.blank_model.volume) / 
                    alt.blank_model.volume * 100
                )
            else:
                self._cost_savings = 0.0
        
        return self._cost_savings


class ProcessingLog(BaseModel):
    """处理日志模型"""
    
    OPERATION_CHOICES = [
        ('upload', '文件上传'),
        ('parse', '文件解析'),
        ('analyze', '几何分析'),
        ('match', '匹配计算'),
    ]
    
    LEVEL_CHOICES = [
        ('info', '信息'),
        ('warning', '警告'),
        ('error', '错误'),
    ]
    
    operation = models.CharField(
        max_length=20,
        choices=OPERATION_CHOICES,
        verbose_name="操作类型"
    )
    level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
        default='info',
        verbose_name="日志级别"
    )
    message = models.TextField(verbose_name="日志消息")
    
    # 关联对象
    shoe_model = models.ForeignKey(
        ShoeModel,
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name="关联鞋模"
    )
    blank_model = models.ForeignKey(
        BlankModel,
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name="关联粗胚"
    )
    
    # 额外数据
    extra_data = models.JSONField(
        default=dict,
        verbose_name="额外数据"
    )
    
    class Meta:
        verbose_name = "处理日志"
        verbose_name_plural = "处理日志"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_level_display()}: {self.operation} - {self.message[:50]}"
