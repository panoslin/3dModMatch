"""
鞋模管理序列化器
"""

from rest_framework import serializers
from .models import ShoeModel


class ShoeModelSerializer(serializers.ModelSerializer):
    """鞋模序列化器"""
    dimensions = serializers.ReadOnlyField()
    file_size_mb = serializers.ReadOnlyField()
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.username', 
        read_only=True
    )
    
    class Meta:
        model = ShoeModel
        fields = [
            'id', 'name', 'file', 'file_url', 'file_size_mb',
            'volume', 'bounding_box', 'vertex_count', 'face_count',
            'dimensions', 'preview_html', 'thumbnail',
            'uploaded_by', 'uploaded_by_name', 'is_processed',
            'processing_status', 'description',
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
    
    def create(self, validated_data):
        """创建鞋模时设置上传者"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['uploaded_by'] = request.user
        return super().create(validated_data)
