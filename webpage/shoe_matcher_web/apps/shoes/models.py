"""
鞋模管理数据模型
"""

from django.db import models
from django.contrib.auth.models import User
from apps.core.models import BaseModel


class ShoeModel(BaseModel):
    """鞋模文件模型"""
    name = models.CharField(max_length=255, verbose_name="鞋模名称")
    file = models.FileField(
        upload_to='shoes/%Y/%m/', 
        verbose_name="3DM文件"
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
    
    # 预览数据 - 兼容旧系统
    preview_html = models.TextField(
        blank=True, 
        verbose_name="预览HTML"
    )
    thumbnail = models.ImageField(
        upload_to='shoes/thumbnails/',
        null=True, blank=True,
        verbose_name="缩略图"
    )
    
    # LOD (Level of Detail) 多精度文件系统
    lod_files = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="多精度文件路径",
        help_text="存储不同精度级别的GLB文件路径 {'preview': 'path/to/low.glb', 'detail': 'path/to/mid.glb', 'full': 'path/to/high.glb'}"
    )
    
    # 几何简化和压缩数据
    geometry_simplified = models.BooleanField(
        default=False,
        verbose_name="几何体已简化",
        help_text="标记是否已生成简化的几何体"
    )
    compression_ratio = models.FloatField(
        null=True, blank=True,
        verbose_name="压缩比",
        help_text="相对于原始文件的压缩比例 (0.0-1.0)"
    )
    
    # 渲染系统配置
    render_engine = models.CharField(
        max_length=20,
        choices=[
            ('plotly', 'Plotly (传统)'),
            ('threejs', 'Three.js (优化)'),
        ],
        default='plotly',
        verbose_name="渲染引擎"
    )
    supports_webgl = models.BooleanField(
        default=False,
        verbose_name="支持WebGL渲染",
        help_text="标记是否已生成WebGL兼容的数据格式"
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
    
    # 备注信息
    description = models.TextField(
        blank=True,
        verbose_name="描述"
    )
    
    class Meta:
        verbose_name = "鞋模文件"
        verbose_name_plural = "鞋模文件"
        ordering = ['-created_at']
    
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
    
    # ==================== LOD系统相关方法 ==================== #
    
    def get_lod_file_path(self, level: str) -> str:
        """
        获取指定精度级别的文件路径
        
        Args:
            level: 精度级别 ('preview', 'detail', 'full')
            
        Returns:
            str: 文件路径，如果不存在则返回空字符串
        """
        if not self.lod_files:
            return ""
        return self.lod_files.get(level, "")
    
    def has_lod_level(self, level: str) -> bool:
        """
        检查是否存在指定精度级别的文件
        
        Args:
            level: 精度级别 ('preview', 'detail', 'full')
            
        Returns:
            bool: 是否存在该精度级别
        """
        return bool(self.get_lod_file_path(level))
    
    @property
    def available_lod_levels(self) -> list:
        """
        获取所有可用的LOD精度级别
        
        Returns:
            list: 可用的精度级别列表
        """
        if not self.lod_files:
            return []
        return [level for level, path in self.lod_files.items() if path]
    
    @property
    def preferred_render_engine(self) -> str:
        """
        获取首选的渲染引擎
        优先使用Three.js如果支持WebGL，否则回退到Plotly
        
        Returns:
            str: 'threejs' 或 'plotly'
        """
        if self.supports_webgl and self.geometry_simplified:
            return 'threejs'
        return 'plotly'
    
    def is_ready_for_threejs(self) -> bool:
        """
        检查是否已准备好使用Three.js渲染
        
        Returns:
            bool: 是否可以使用Three.js渲染
        """
        return (
            self.supports_webgl and 
            self.geometry_simplified and 
            self.has_lod_level('preview')
        )
    
    @property
    def optimization_status(self) -> dict:
        """
        获取优化状态摘要
        
        Returns:
            dict: 包含各项优化状态的字典
        """
        return {
            'lod_generated': len(self.available_lod_levels) > 0,
            'geometry_simplified': self.geometry_simplified,
            'webgl_ready': self.supports_webgl,
            'compression_ratio': self.compression_ratio,
            'preferred_engine': self.preferred_render_engine,
            'ready_for_production': self.is_ready_for_threejs()
        }
