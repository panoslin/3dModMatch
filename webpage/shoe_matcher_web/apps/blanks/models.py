"""
粗胚管理数据模型
"""

from django.db import models
from apps.core.models import BaseModel


class BlankCategory(BaseModel):
    """粗胚分类模型"""
    name = models.CharField(max_length=50, verbose_name="分类名称")
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, blank=True,
        verbose_name="父分类"
    )
    description = models.TextField(blank=True, verbose_name="描述")
    sort_order = models.IntegerField(default=0, verbose_name="排序")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    
    class Meta:
        verbose_name = "粗胚分类"
        verbose_name_plural = "粗胚分类"
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_full_name(self):
        """获取完整分类路径"""
        if self.parent:
            return f"{self.parent.get_full_name()} > {self.name}"
        return self.name


class BlankModel(BaseModel):
    """粗胚文件模型"""
    name = models.CharField(max_length=255, verbose_name="粗胚名称")
    file = models.FileField(
        upload_to='blanks/%Y/%m/', 
        verbose_name="3DM文件"
    )
    categories = models.ManyToManyField(
        BlankCategory, 
        verbose_name="分类",
        blank=True
    )
    
    # 几何特征数据
    volume = models.FloatField(
        null=True, blank=True, 
        verbose_name="体积(mm³)"
    )
    bounding_box = models.JSONField(
        default=dict, 
        verbose_name="边界框"
    )
    vertex_count = models.IntegerField(
        default=0, 
        verbose_name="顶点数量"
    )
    face_count = models.IntegerField(
        default=0, 
        verbose_name="面数量"
    )
    
    # 预览数据
    preview_html = models.TextField(
        blank=True, 
        verbose_name="预览HTML"
    )
    thumbnail = models.ImageField(
        upload_to='blanks/thumbnails/',
        null=True, blank=True,
        verbose_name="缩略图"
    )
    
    # 状态
    is_active = models.BooleanField(
        default=True, 
        verbose_name="是否启用"
    )
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
    
    # 成本信息
    material_cost = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name="材料成本(元)"
    )
    
    class Meta:
        verbose_name = "粗胚文件"
        verbose_name_plural = "粗胚文件"
        ordering = ['volume', 'name']
    
    def __str__(self):
        return self.name
    
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
    
    @property
    def file_size_mb(self):
        """获取文件大小(MB)"""
        if self.file:
            return round(self.file.size / (1024 * 1024), 2)
        return 0


