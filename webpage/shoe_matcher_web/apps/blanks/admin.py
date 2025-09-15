"""
粗胚管理后台
"""

from django.contrib import admin
from .models import BlankModel, BlankCategory


@admin.register(BlankCategory)
class BlankCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'sort_order', 'is_active', 'created_at']
    list_filter = ['is_active', 'parent', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['sort_order', 'name']
    list_editable = ['sort_order', 'is_active']


@admin.register(BlankModel)
class BlankModelAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'volume', 'processing_status', 
        'is_active', 'created_at'
    ]
    list_filter = [
        'processing_status', 'is_active', 'categories', 'created_at'
    ]
    search_fields = ['name']
    readonly_fields = [
        'volume', 'bounding_box', 'vertex_count', 'face_count',
        'preview_html', 'created_at', 'updated_at'
    ]
    filter_horizontal = ['categories']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'file', 'categories', 'material_cost')
        }),
        ('几何信息', {
            'fields': (
                'volume', 'bounding_box', 'vertex_count', 
                'face_count', 'preview_html'
            ),
            'classes': ('collapse',)
        }),
        ('状态', {
            'fields': ('is_active', 'processing_status')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


