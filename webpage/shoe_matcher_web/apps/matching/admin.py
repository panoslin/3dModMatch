"""
匹配功能后台
"""

from django.contrib import admin
from .models import MatchingTask


@admin.register(MatchingTask)
class MatchingTaskAdmin(admin.ModelAdmin):
    list_display = [
        'task_id', 'shoe_model', 'status', 
        'candidate_count', 'passed_count', 'created_at'
    ]
    list_filter = [
        'status', 'threshold', 'enable_scaling', 
        'enable_multi_start', 'created_at'
    ]
    search_fields = ['task_id', 'shoe_model__name']
    readonly_fields = [
        'task_id', 'result_data', 'summary_data',
        'started_at', 'completed_at', 'processing_time',
        'created_at', 'updated_at'
    ]
    filter_horizontal = ['selected_categories']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('task_id', 'shoe_model', 'selected_categories')
        }),
        ('匹配参数', {
            'fields': (
                'clearance', 'threshold', 'enable_scaling',
                'enable_multi_start', 'max_scale'
            )
        }),
        ('任务状态', {
            'fields': ('status', 'progress', 'current_step')
        }),
        ('结果数据', {
            'fields': ('result_data', 'summary_data'),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': (
                'started_at', 'completed_at', 'processing_time',
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def candidate_count(self, obj):
        return obj.candidate_count
    candidate_count.short_description = '候选数量'
    
    def passed_count(self, obj):
        return obj.passed_count
    passed_count.short_description = '通过数量'
