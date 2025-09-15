"""
鞋模管理后台
"""

from django.contrib import admin
from .models import ShoeModel


@admin.register(ShoeModel)
class ShoeModelAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'volume', 'processing_status', 
        'uploaded_by', 'created_at'
    ]
    list_filter = [
        'processing_status', 'is_processed', 'uploaded_by', 'created_at'
    ]
    search_fields = ['name', 'description']
    readonly_fields = [
        'volume', 'bounding_box', 'vertex_count', 'face_count',
        'preview_html', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'file', 'description', 'uploaded_by')
        }),
        ('几何信息', {
            'fields': (
                'volume', 'bounding_box', 'vertex_count', 
                'face_count', 'preview_html'
            ),
            'classes': ('collapse',)
        }),
        ('状态', {
            'fields': ('is_processed', 'processing_status')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
