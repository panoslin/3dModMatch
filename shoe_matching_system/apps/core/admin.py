"""
3D鞋模匹配系统管理后台配置
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from .models import ShoeModel, BlankModel, MatchingResult, ProcessingLog


@admin.register(ShoeModel)
class ShoeModelAdmin(admin.ModelAdmin):
    list_display = [
        'filename', 'file_format', 'volume', 'points_count', 
        'processing_status', 'is_processed', 'created_at'
    ]
    list_filter = ['file_format', 'processing_status', 'is_processed', 'created_at']
    search_fields = ['filename']
    readonly_fields = ['file_size', 'points_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('filename', 'file', 'file_format', 'uploaded_by')
        }),
        ('几何特征', {
            'fields': ('volume', 'points_count', 'bounding_box', 'key_features'),
            'classes': ('collapse',),
        }),
        ('处理状态', {
            'fields': ('processing_status', 'is_processed')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploaded_by')
    
    def volume_display(self, obj):
        if obj.volume:
            return f"{obj.volume} cm³"
        return "-"
    volume_display.short_description = "体积"


@admin.register(BlankModel)  
class BlankModelAdmin(admin.ModelAdmin):
    list_display = [
        'filename', 'file_format', 'volume', 'material_cost',
        'points_count', 'processing_status', 'created_at'
    ]
    list_filter = ['file_format', 'processing_status', 'is_processed']
    search_fields = ['filename']
    readonly_fields = ['file_size', 'points_count', 'created_at', 'updated_at']
    ordering = ['volume']  # 按体积排序，便于查找最小的粗胚
    
    fieldsets = (
        ('基本信息', {
            'fields': ('filename', 'file', 'file_format')
        }),
        ('几何特征', {
            'fields': ('volume', 'points_count', 'bounding_box', 'key_features'),
            'classes': ('collapse',),
        }),
        ('成本信息', {
            'fields': ('material_cost',)
        }),
        ('处理状态', {
            'fields': ('processing_status', 'is_processed')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def cost_per_volume(self, obj):
        if obj.volume and obj.material_cost:
            return f"¥{obj.material_cost/obj.volume:.2f}/cm³"
        return "-"
    cost_per_volume.short_description = "单位成本"


@admin.register(MatchingResult)
class MatchingResultAdmin(admin.ModelAdmin):
    list_display = [
        'shoe_model_link', 'blank_model_link', 'material_utilization',
        'average_margin', 'is_optimal', 'is_feasible', 'created_at'
    ]
    list_filter = [
        'is_optimal', 'is_feasible', 'margin_distance', 'created_at'
    ]
    search_fields = [
        'shoe_model__filename', 'blank_model__filename'
    ]
    readonly_fields = [
        'similarity_score', 'material_utilization', 'average_margin',
        'min_margin', 'max_margin', 'computation_time', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('匹配对象', {
            'fields': ('shoe_model', 'blank_model', 'margin_distance')
        }),
        ('匹配结果', {
            'fields': (
                'similarity_score', 'material_utilization', 
                'average_margin', 'min_margin', 'max_margin'
            )
        }),
        ('状态', {
            'fields': ('is_optimal', 'is_feasible')
        }),
        ('详细数据', {
            'fields': ('analysis_data', 'computation_time'),
            'classes': ('collapse',),
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'shoe_model', 'blank_model'
        )
    
    def shoe_model_link(self, obj):
        url = reverse('admin:core_shoemodel_change', args=[obj.shoe_model.pk])
        return format_html('<a href="{}">{}</a>', url, obj.shoe_model.filename)
    shoe_model_link.short_description = "鞋模"
    
    def blank_model_link(self, obj):
        url = reverse('admin:core_blankmodel_change', args=[obj.blank_model.pk])
        return format_html('<a href="{}">{}</a>', url, obj.blank_model.filename)
    blank_model_link.short_description = "粗胚"
    
    def utilization_display(self, obj):
        color = "green" if obj.material_utilization > 70 else "orange" if obj.material_utilization > 50 else "red"
        return format_html(
            '<span style="color: {};">{:.1f}%</span>', 
            color, obj.material_utilization
        )
    utilization_display.short_description = "材料利用率"


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    list_display = [
        'operation', 'level', 'message_preview', 'shoe_model', 
        'blank_model', 'created_at'
    ]
    list_filter = ['operation', 'level', 'created_at']
    search_fields = ['message', 'shoe_model__filename', 'blank_model__filename']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'shoe_model', 'blank_model'
        )
    
    def message_preview(self, obj):
        return obj.message[:100] + "..." if len(obj.message) > 100 else obj.message
    message_preview.short_description = "消息预览"
    
    def has_add_permission(self, request):
        return False  # 禁止手动添加日志
    
    def has_change_permission(self, request, obj=None):
        return False  # 禁止修改日志


# 自定义管理后台首页
class CustomAdminSite(admin.AdminSite):
    site_header = "3D鞋模智能匹配系统"
    site_title = "鞋模匹配管理"
    index_title = "系统管理面板"
    
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # 统计数据
        stats = {
            'shoe_models_count': ShoeModel.objects.count(),
            'blank_models_count': BlankModel.objects.count(),
            'matching_results_count': MatchingResult.objects.count(),
            'optimal_matches_count': MatchingResult.objects.filter(is_optimal=True).count(),
            'avg_utilization': MatchingResult.objects.aggregate(
                avg=Avg('material_utilization')
            )['avg'] or 0,
        }
        
        extra_context['stats'] = stats
        return super().index(request, extra_context)
