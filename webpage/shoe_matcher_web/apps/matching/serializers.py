"""
匹配功能序列化器
"""

from rest_framework import serializers
from .models import MatchingTask
from apps.shoes.serializers import ShoeModelSerializer
from apps.blanks.serializers import BlankCategorySerializer


class MatchingTaskSerializer(serializers.ModelSerializer):
    """匹配任务序列化器"""
    shoe_model_data = ShoeModelSerializer(
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


class MatchingResultSerializer(serializers.Serializer):
    """匹配结果序列化器"""
    task_id = serializers.CharField()
    status = serializers.CharField()
    results = serializers.ListField()
    summary = serializers.DictField()
