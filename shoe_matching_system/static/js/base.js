/**
 * 3D鞋模匹配系统 - 基础JavaScript
 */

(function($) {
    'use strict';

    // 页面加载完成后初始化
    $(document).ready(function() {
        initializeApp();
    });

    /**
     * 初始化应用
     */
    function initializeApp() {
        // 初始化工具提示
        $('[data-toggle="tooltip"]').tooltip();
        
        // 初始化弹出框
        $('[data-toggle="popover"]').popover();
        
        // 初始化文件上传
        initializeFileUpload();
        
        // 初始化AJAX设置
        setupAjax();
        
        // 自动隐藏消息提示
        autoHideMessages();
    }

    /**
     * 设置AJAX默认配置
     */
    function setupAjax() {
        // 获取CSRF令牌
        function getCookie(name) {
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
        }

        // 设置AJAX请求头
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
                }
            }
        });
    }

    /**
     * 初始化文件上传功能
     */
    function initializeFileUpload() {
        // 拖拽上传
        $('.upload-area').on('dragover', function(e) {
            e.preventDefault();
            $(this).addClass('dragover');
        });

        $('.upload-area').on('dragleave', function(e) {
            e.preventDefault();
            $(this).removeClass('dragover');
        });

        $('.upload-area').on('drop', function(e) {
            e.preventDefault();
            $(this).removeClass('dragover');
            
            const files = e.originalEvent.dataTransfer.files;
            handleFileSelection(files, $(this));
        });

        // 点击上传
        $('.upload-area').on('click', function() {
            const fileInput = $(this).find('input[type="file"]');
            if (fileInput.length) {
                fileInput.click();
            }
        });

        // 文件选择
        $('input[type="file"]').on('change', function() {
            const files = this.files;
            handleFileSelection(files, $(this).closest('.upload-area'));
        });
    }

    /**
     * 处理文件选择
     */
    function handleFileSelection(files, container) {
        if (!files || files.length === 0) return;

        const fileList = container.find('.file-list');
        if (fileList.length === 0) {
            container.append('<div class="file-list mt-3"></div>');
        }

        Array.from(files).forEach(file => {
            displaySelectedFile(file, container.find('.file-list'));
        });
    }

    /**
     * 显示选中的文件
     */
    function displaySelectedFile(file, container) {
        const fileSize = formatFileSize(file.size);
        const fileExtension = file.name.split('.').pop().toLowerCase();
        
        let fileIcon = '📄';
        if (fileExtension === '3dm') fileIcon = '🏗️';
        else if (fileExtension === 'mod') fileIcon = '⚙️';

        const fileElement = $(`
            <div class="selected-file d-flex justify-content-between align-items-center py-2 px-3 mb-2 bg-light rounded">
                <div>
                    <span class="file-icon">${fileIcon}</span>
                    <span class="file-name ml-2">${file.name}</span>
                    <small class="text-muted ml-2">(${fileSize})</small>
                </div>
                <button type="button" class="btn btn-sm btn-outline-danger remove-file">
                    ×
                </button>
            </div>
        `);

        fileElement.find('.remove-file').on('click', function() {
            fileElement.remove();
        });

        container.append(fileElement);
    }

    /**
     * 格式化文件大小
     */
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 自动隐藏消息提示
     */
    function autoHideMessages() {
        setTimeout(function() {
            $('.alert').fadeOut('slow');
        }, 5000);
    }

    /**
     * 显示加载状态
     */
    function showLoading(container, message) {
        message = message || '加载中...';
        const loadingHtml = `
            <div class="loading-overlay">
                <div class="text-center">
                    <div class="spinner-border text-primary spinner-border-custom" role="status">
                        <span class="sr-only">Loading...</span>
                    </div>
                    <div class="mt-2">${message}</div>
                </div>
            </div>
        `;
        container.append(loadingHtml);
    }

    /**
     * 隐藏加载状态
     */
    function hideLoading(container) {
        container.find('.loading-overlay').remove();
    }

    /**
     * 显示进度条
     */
    function showProgress(container, progress) {
        let progressBar = container.find('.progress');
        if (progressBar.length === 0) {
            progressBar = $(`
                <div class="progress mt-3">
                    <div class="progress-bar" role="progressbar" style="width: 0%" 
                         aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                </div>
            `);
            container.append(progressBar);
        }

        const bar = progressBar.find('.progress-bar');
        bar.css('width', progress + '%')
           .attr('aria-valuenow', progress)
           .text(progress + '%');
    }

    /**
     * 显示错误消息
     */
    function showError(message, container) {
        const alertHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <strong>错误:</strong> ${message}
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `;
        
        if (container) {
            container.prepend(alertHtml);
        } else {
            $('.main-content').prepend(alertHtml);
        }
    }

    /**
     * 显示成功消息
     */
    function showSuccess(message, container) {
        const alertHtml = `
            <div class="alert alert-success alert-dismissible fade show" role="alert">
                <strong>成功:</strong> ${message}
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `;
        
        if (container) {
            container.prepend(alertHtml);
        } else {
            $('.main-content').prepend(alertHtml);
        }
    }

    /**
     * API请求封装
     */
    function apiRequest(url, method, data, successCallback, errorCallback) {
        $.ajax({
            url: url,
            method: method,
            data: data,
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    if (successCallback) successCallback(response);
                } else {
                    const message = response.error || '请求失败';
                    if (errorCallback) errorCallback(message);
                    else showError(message);
                }
            },
            error: function(xhr, status, error) {
                const message = xhr.responseJSON && xhr.responseJSON.error 
                    ? xhr.responseJSON.error 
                    : '网络请求失败: ' + error;
                if (errorCallback) errorCallback(message);
                else showError(message);
            }
        });
    }

    // 暴露全局函数
    window.ShoeMatchingSystem = {
        showLoading: showLoading,
        hideLoading: hideLoading,
        showProgress: showProgress,
        showError: showError,
        showSuccess: showSuccess,
        apiRequest: apiRequest,
        formatFileSize: formatFileSize
    };

})(jQuery);