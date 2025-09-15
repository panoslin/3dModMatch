"""
核心应用管理界面
"""

from django.contrib import admin
from .models import SystemLog


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ['level', 'message', 'module', 'user', 'created_at']
    list_filter = ['level', 'module', 'created_at']
    search_fields = ['message', 'module']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        return False  # 不允许手动添加日志


