/**
 * 3D鞋模智能匹配工作台 - 基础JavaScript
 */

// 全局工具函数
window.ShoeMatching = {
    // 获取CSRF Token
    getCSRFToken: function() {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === ('csrftoken' + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                        break;
                    }
                }
            }
            return cookieValue;
    },

    // AJAX请求封装
    ajax: function(options) {
        const defaults = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            }
        };
        
        const config = Object.assign({}, defaults, options);
        
        return fetch(config.url, {
            method: config.method,
            headers: config.headers,
            body: config.body
        }).then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        });
    },

    // 显示加载状态
    showLoading: function(message = '处理中...') {
        const overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="sr-only">Loading...</span>
                </div>
                <p class="mb-0">${message}</p>
            </div>
        `;
        document.body.appendChild(overlay);
    },

    // 隐藏加载状态
    hideLoading: function() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    },

    // 显示消息提示
    showMessage: function(message, type = 'info', duration = 5000) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // 找到消息容器或创建一个
        let container = document.querySelector('.message-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'message-container';
            container.style.cssText = 'position: fixed; top: 80px; right: 20px; z-index: 1050; width: 300px;';
            document.body.appendChild(container);
        }
        
        container.appendChild(alertDiv);
        
        // 自动隐藏
        if (duration > 0) {
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.remove();
                }
            }, duration);
        }
    },

    // 格式化文件大小
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // 格式化时间
    formatTime: function(seconds) {
        if (seconds < 60) {
            return `${seconds.toFixed(1)}秒`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = Math.floor(seconds % 60);
            return `${minutes}分${remainingSeconds}秒`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}小时${minutes}分钟`;
        }
    },

    // 防抖函数
    debounce: function(func, wait, immediate) {
        let timeout;
        return function executedFunction() {
            const context = this;
            const args = arguments;
            const later = function() {
                timeout = null;
                if (!immediate) func.apply(context, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(context, args);
        };
    },

    // 节流函数
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    },

    // 验证文件类型
    validateFileType: function(file, allowedTypes = ['.3dm', '.mod', '.MOD']) {
        const fileName = file.name.toLowerCase();
        const extension = '.' + fileName.split('.').pop();
        return allowedTypes.some(type => fileName.endsWith(type.toLowerCase()));
    },

    // 验证文件大小
    validateFileSize: function(file, maxSize = 100 * 1024 * 1024) {
        return file.size <= maxSize;
    },

    // 生成唯一ID
    generateId: function() {
        return 'id_' + Math.random().toString(36).substr(2, 9);
    },

    // 深拷贝对象
    deepClone: function(obj) {
        if (obj === null || typeof obj !== "object") {
            return obj;
        }
        if (obj instanceof Date) {
            return new Date(obj.getTime());
        }
        if (obj instanceof Array) {
            return obj.map(item => this.deepClone(item));
        }
        if (typeof obj === "object") {
            const clonedObj = {};
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    clonedObj[key] = this.deepClone(obj[key]);
                }
            }
            return clonedObj;
        }
    },

    // 本地存储封装
    storage: {
        set: function(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
            } catch (e) {
                console.error('localStorage设置失败:', e);
            }
        },
        
        get: function(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch (e) {
                console.error('localStorage读取失败:', e);
                return defaultValue;
            }
        },
        
        remove: function(key) {
            try {
                localStorage.removeItem(key);
            } catch (e) {
                console.error('localStorage删除失败:', e);
            }
        },
        
        clear: function() {
            try {
                localStorage.clear();
            } catch (e) {
                console.error('localStorage清空失败:', e);
            }
        }
    }
};

// DOM加载完成后的初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化所有提示信息
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // 初始化所有弹出框
    if (typeof bootstrap !== 'undefined' && bootstrap.Popover) {
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }
    
    // 自动隐藏alert消息
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(alert => {
            if (alert.classList.contains('show')) {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            }
        });
    }, 5000);
    
    // 为所有表单添加基础验证
    const forms = document.querySelectorAll('form[data-validate="true"]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
                ShoeMatching.showMessage('请填写所有必填字段', 'warning');
            }
            form.classList.add('was-validated');
        });
    });
    
    // 为文件输入添加拖拽支持
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        const container = input.closest('.file-drop-zone') || input.parentElement;
        if (container) {
            container.addEventListener('dragover', function(e) {
                e.preventDefault();
                container.classList.add('dragover');
            });
            
            container.addEventListener('dragleave', function(e) {
                e.preventDefault();
                container.classList.remove('dragover');
            });
            
            container.addEventListener('drop', function(e) {
                e.preventDefault();
                container.classList.remove('dragover');
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    input.files = files;
                    const event = new Event('change', { bubbles: true });
                    input.dispatchEvent(event);
                }
            });
        }
    });
});

// 页面卸载前的清理
window.addEventListener('beforeunload', function() {
    ShoeMatching.hideLoading();
});

// 错误处理
window.addEventListener('error', function(e) {
    console.error('全局错误:', e.error);
    if (window.location.hostname !== 'localhost') {
        // 生产环境下可以发送错误到服务器
        // sendErrorToServer(e.error);
    }
});

// 未处理的Promise拒绝
window.addEventListener('unhandledrejection', function(e) {
    console.error('未处理的Promise拒绝:', e.reason);
    e.preventDefault();
});

// 导出给全局使用
window.SM = window.ShoeMatching;