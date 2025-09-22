/**
 * 3D鞋模智能匹配系统 - 主JavaScript文件
 */

// 全局配置
const CONFIG = {
    API_BASE: '',  // 空字符串，因为API路径已经包含/api
    UPLOAD_MAX_SIZE: 100 * 1024 * 1024, // 100MB
    POLL_INTERVAL: 2000, // 2秒
};

// 工具函数
const Utils = {
    /**
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * 显示通知
     */
    showNotification(message, type = 'info') {
        // 防止递归调用
        if (this._notificationInProgress) {
            console.log('通知正在处理中，跳过:', message);
            return;
        }
        
        this._notificationInProgress = true;
        
        try {
            // 创建通知元素
            const alertClass = `alert-${type}`;
            const iconClass = {
                'success': 'fa-check-circle',
                'error': 'fa-exclamation-circle',
                'warning': 'fa-exclamation-triangle',
                'info': 'fa-info-circle'
            }[type] || 'fa-info-circle';

            const alert = $(`
                <div class="alert ${alertClass} alert-dismissible fade show position-fixed" 
                     style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
                    <i class="fas ${iconClass} me-2"></i>
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `);

            $('body').append(alert);

            // 自动移除
            setTimeout(() => {
                try {
                    alert.alert('close');
                } catch (e) {
                    alert.remove();
                }
                this._notificationInProgress = false;
            }, 5000);
            
        } catch (error) {
            console.error('显示通知失败:', error);
            this._notificationInProgress = false;
        }
    },

    /**
     * 显示加载状态
     */
    showLoading(element, text = '加载中...') {
        $(element).html(`
            <div class="text-center py-4">
                <div class="spinner-border text-primary mb-2" role="status">
                    <span class="visually-hidden">${text}</span>
                </div>
                <div class="text-muted">${text}</div>
            </div>
        `);
    },

    /**
     * 获取Cookie值
     */
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },

    /**
     * API请求封装
     */
    async apiRequest(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                              $('[name=csrfmiddlewaretoken]').val() ||
                              Utils.getCookie('csrftoken')
            }
        };

        const finalOptions = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(CONFIG.API_BASE + url, finalOptions);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.message || '请求失败');
            }
            
            return data;
        } catch (error) {
            console.error('API请求错误:', error);
            throw error;
        }
    }
};

// 页面初始化
$(document).ready(function() {
    console.log('3D鞋模智能匹配系统已加载');
    
    // 初始化工具提示
    try {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    } catch (error) {
        console.log('工具提示初始化失败:', error);
    }
    
    // 初始化弹出框
    try {
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    } catch (error) {
        console.log('弹出框初始化失败:', error);
    }
    
    console.log('页面初始化完成');
});

// 错误处理
window.addEventListener('error', function(e) {
    console.error('JavaScript错误:', e.error);
    
    // 避免无限递归，直接创建简单的错误提示
    try {
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show position-fixed';
        alert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alert.innerHTML = `
            <i class="fas fa-exclamation-circle me-2"></i>
            系统出现错误，请刷新页面重试
            <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
        `;
        document.body.appendChild(alert);
        
        // 自动移除
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    } catch (err) {
        console.error('错误处理失败:', err);
    }
});

// 导出工具函数供其他脚本使用
window.Utils = Utils;
window.CONFIG = CONFIG;
