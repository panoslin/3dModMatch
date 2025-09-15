"""
粗胚管理序列化器
"""

from rest_framework import serializers
from .models import BlankModel, BlankCategory


class BlankCategorySerializer(serializers.ModelSerializer):
    """粗胚分类序列化器"""
    children = serializers.SerializerMethodField()
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = BlankCategory
        fields = [
            'id', 'name', 'parent', 'description', 
            'sort_order', 'is_active', 'children', 'full_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_children(self, obj):
        """获取子分类"""
        children = obj.blankcategory_set.filter(is_active=True)
        return BlankCategorySerializer(children, many=True).data


class BlankModelSerializer(serializers.ModelSerializer):
    """粗胚模型序列化器"""
    categories_data = BlankCategorySerializer(
        source='categories', 
        many=True, 
        read_only=True
    )
    dimensions = serializers.ReadOnlyField()
    file_size_mb = serializers.ReadOnlyField()
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = BlankModel
        fields = [
            'id', 'name', 'file', 'file_url', 'file_size_mb',
            'categories', 'categories_data', 'volume', 'bounding_box',
            'vertex_count', 'face_count', 'dimensions',
            'preview_html', 'thumbnail', 'is_active', 'is_processed',
            'processing_status', 'material_cost',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'volume', 'bounding_box', 'vertex_count', 'face_count',
            'preview_html', 'is_processed', 'processing_status',
            'created_at', 'updated_at'
        ]
    
    def get_file_url(self, obj):
        """获取文件URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def validate_file(self, value):
        """验证文件格式"""
        if not value.name.lower().endswith('.3dm'):
            raise serializers.ValidationError("只支持.3dm格式文件")
        
        # 检查文件大小 (100MB)
        if value.size > 100 * 1024 * 1024:
            raise serializers.ValidationError("文件大小不能超过100MB")
        
        return value


