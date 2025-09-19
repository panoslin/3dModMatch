"""
匹配功能序列化器
"""

from rest_framework import serializers
from .models import MatchingTask
from apps.shoes.serializers import ShoeModelSerializer
from apps.shoes.models import ShoeModel
from apps.blanks.serializers import BlankCategorySerializer


class ShoeModelSimpleSerializer(serializers.ModelSerializer):
    """简化的鞋模序列化器（不包含HTML预览）"""
    dimensions = serializers.ReadOnlyField()
    file_size_mb = serializers.ReadOnlyField()
    
    class Meta:
        model = ShoeModel
        fields = [
            'id', 'name', 'file_size_mb', 'dimensions',
            'vertex_count', 'face_count', 'is_processed'
        ]


class MatchingTaskSerializer(serializers.ModelSerializer):
    """匹配任务序列化器"""
    shoe_model_data = ShoeModelSimpleSerializer(
        source='shoe_model', 
        read_only=True
    )
    categories_data = BlankCategorySerializer(
        source='selected_categories', 
        many=True, 
        read_only=True
    )
    candidate_count = serializers.ReadOnlyField()
    passed_count = serializers.ReadOnlyField()
    best_match = serializers.ReadOnlyField()
    
    class Meta:
        model = MatchingTask
        fields = [
            'id', 'task_id', 'shoe_model', 'shoe_model_data',
            'selected_categories', 'categories_data',
            'clearance', 'threshold', 'enable_scaling', 
            'enable_multi_start', 'max_scale',
            'status', 'progress', 'current_step',
            'result_data', 'summary_data',
            'started_at', 'completed_at', 'processing_time',
            'candidate_count', 'passed_count', 'best_match',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'task_id', 'status', 'progress', 'current_step',
            'result_data', 'summary_data', 'started_at', 
            'completed_at', 'processing_time',
            'created_at', 'updated_at'
        ]


class StartMatchingSerializer(serializers.Serializer):
    """开始匹配请求序列化器"""
    shoe_model_id = serializers.IntegerField()
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    clearance = serializers.FloatField(
        min_value=0.5, 
        max_value=10.0, 
        default=2.0
    )
    threshold = serializers.ChoiceField(
        choices=['min', 'p10', 'p15', 'p20'],
        default='p15'
    )
    enable_scaling = serializers.BooleanField(default=True)
    enable_multi_start = serializers.BooleanField(default=True)
    max_scale = serializers.FloatField(
        min_value=1.0,
        max_value=1.1,
        default=1.03
    )
    
    def validate_shoe_model_id(self, value):
        """验证鞋模ID"""
        from apps.shoes.models import ShoeModel
        try:
            shoe = ShoeModel.objects.get(id=value, is_processed=True)
            return value
        except ShoeModel.DoesNotExist:
            raise serializers.ValidationError("鞋模不存在或未处理完成")
    
    def validate_category_ids(self, value):
        """验证分类ID"""
        from apps.blanks.models import BlankCategory
        existing_ids = BlankCategory.objects.filter(
            id__in=value, 
            is_active=True
        ).values_list('id', flat=True)
        
        if len(existing_ids) != len(value):
            missing = set(value) - set(existing_ids)
            raise serializers.ValidationError(f"分类不存在: {list(missing)}")
        
        return value


class MatchingStatusSerializer(serializers.Serializer):
    """匹配状态序列化器"""
    task_id = serializers.CharField()
    status = serializers.CharField()
    progress = serializers.IntegerField()
    current_step = serializers.CharField()
    estimated_remaining = serializers.IntegerField(required=False)


class MatchingTaskListSerializer(serializers.ModelSerializer):
    """匹配任务列表序列化器（用于历史记录，不包含结果数据）"""
    shoe_model_name = serializers.CharField(
        source='shoe_model.name', 
        read_only=True
    )
    category_count = serializers.SerializerMethodField()
    candidate_count = serializers.ReadOnlyField()
    passed_count = serializers.ReadOnlyField()
    
    class Meta:
        model = MatchingTask
        fields = [
            'id', 'task_id', 'shoe_model_name',
            'category_count', 'clearance', 'threshold',
            'status', 'progress', 'processing_time',
            'candidate_count', 'passed_count',
            'created_at', 'completed_at'
        ]
    
    def get_category_count(self, obj):
        """获取选中的分类数量"""
        return obj.selected_categories.count()


class MatchingResultSerializer(serializers.Serializer):
    """匹配结果序列化器"""
    task_id = serializers.CharField()
    status = serializers.CharField()
    results = serializers.ListField()
    summary = serializers.DictField()
