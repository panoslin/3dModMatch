/**
 * 历史记录页面JavaScript
 */

class HistoryApp {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 20;
        this.filters = {};
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadHistory();
    }
    
    bindEvents() {
        // 筛选按钮
        $('#filter-btn').on('click', () => {
            $('#filter-panel').collapse('toggle');
        });
        
        // 应用筛选
        $('#apply-filter').on('click', () => {
            this.applyFilters();
        });
        
        // 导出历史
        $('#export-history-btn').on('click', () => {
            this.exportHistory();
        });
        
        // 查看完整结果
        $('#view-full-results').on('click', () => {
            const taskId = $('#taskDetailModal').data('task-id');
            if (taskId) {
                window.open(`/?task=${taskId}`, '_blank');
            }
        });
    }
    
    async loadHistory(page = 1) {
        try {
            this.showLoading();
            
            const params = new URLSearchParams({
                page: page,
                page_size: this.pageSize,
                ...this.filters
            });
            
            const response = await Utils.apiRequest(`/api/matching/history/?${params}`);
            
            // API返回的是分页响应，需要访问results.data
            if (response.results && response.results.success) {
                this.renderHistory(response.results.data);
                this.currentPage = page;
                
                // 更新分页信息
                this.totalCount = response.count || 0;
                this.hasNext = !!response.next;
                this.hasPrevious = !!response.previous;
                this.updatePagination();
            } else if (response.success) {
                // 兼容非分页响应
                this.renderHistory(response.data);
                this.currentPage = page;
            }
            
        } catch (error) {
            this.showError('加载历史记录失败: ' + error.message);
        }
    }
    
    renderHistory(data) {
        const tbody = $('#history-table tbody');
        tbody.empty();
        
        if (!data || data.length === 0) {
            this.showEmpty();
            return;
        }
        
        this.hideLoading();
        
        data.forEach(task => {
            const row = this.createHistoryRow(task);
            tbody.append(row);
        });
    }
    
    createHistoryRow(task) {
        const statusBadge = this.getStatusBadge(task.status);
        // API现在直接返回字段，不再嵌套在对象中
        const shoeModelName = task.shoe_model_name || '未知鞋模';
        
        return $(`
            <tr data-task-id="${task.task_id}">
                <td>
                    <code class="small">${task.task_id}</code>
                </td>
                <td>
                    <strong>${shoeModelName}</strong>
                    <br><small class="text-muted">分类: ${task.category_count}</small>
                </td>
                <td>
                    <span class="text-nowrap">${this.formatDateTime(task.created_at)}</span>
                </td>
                <td>${statusBadge}</td>
                <td>
                    <span class="badge bg-primary">${task.candidate_count || 0}</span>
                </td>
                <td>
                    <span class="badge bg-success">${task.passed_count || 0}</span>
                </td>
                <td>
                    <small>间隙: ${task.clearance}mm / ${task.threshold}</small>
                </td>
                <td>
                    <span class="text-muted">${task.processing_time ? task.processing_time.toFixed(1) + 's' : '--'}</span>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="historyApp.showTaskDetail('${task.task_id}')">
                            <i class="fas fa-eye"></i>
                        </button>
                        ${task.status === 'completed' ? `
                        <button class="btn btn-outline-success" onclick="historyApp.downloadResults('${task.task_id}')">
                            <i class="fas fa-download"></i>
                        </button>` : ''}
                    </div>
                </td>
            </tr>
        `);
    }
    
    getStatusBadge(status) {
        const badges = {
            'pending': '<span class="badge bg-secondary"><i class="fas fa-clock me-1"></i>等待中</span>',
            'processing': '<span class="badge bg-warning text-dark"><i class="fas fa-spinner fa-spin me-1"></i>处理中</span>',
            'completed': '<span class="badge bg-success"><i class="fas fa-check me-1"></i>已完成</span>',
            'failed': '<span class="badge bg-danger"><i class="fas fa-times me-1"></i>失败</span>'
        };
        return badges[status] || '<span class="badge bg-secondary">未知</span>';
    }
    
    formatDateTime(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    async showTaskDetail(taskId) {
        try {
            const response = await Utils.apiRequest(`/api/matching/${taskId}/result/`);
            
            if (response.success) {
                this.renderTaskDetail(response.data);
                $('#taskDetailModal').data('task-id', taskId);
                $('#taskDetailModal').modal('show');
            }
            
        } catch (error) {
            Utils.showNotification('加载任务详情失败: ' + error.message, 'error');
        }
    }
    
    renderTaskDetail(data) {
        // 基本信息
        $('#detail-task-id').text(data.task_id);
        $('#detail-shoe-name').text(data.shoe_model_name || '--');
        $('#detail-created').text(data.created_at ? this.formatDateTime(data.created_at) : '--');
        $('#detail-completed').text(data.completed_at ? this.formatDateTime(data.completed_at) : '--');
        $('#detail-status').html(this.getStatusBadge(data.status));
        
        // 计算处理时间
        if (data.created_at && data.completed_at) {
            const start = new Date(data.created_at);
            const end = new Date(data.completed_at);
            const duration = (end - start) / 1000; // 秒
            $('#detail-duration').text(`${duration.toFixed(1)}秒`);
        } else if (data.summary && data.summary.processing_time) {
            $('#detail-duration').text(`${data.summary.processing_time.toFixed(1)}秒`);
        } else {
            $('#detail-duration').text('--');
        }
        
        // 匹配参数
        if (data.parameters) {
            $('#detail-clearance').text(data.parameters.clearance ? `${data.parameters.clearance}mm` : '--');
            $('#detail-threshold').text(data.parameters.threshold || '--');
            $('#detail-scaling').text(data.parameters.auto_scale ? '是' : '否');
            $('#detail-multistart').text(data.parameters.multi_orientation ? '是' : '否');
            $('#detail-maxscale').text(data.parameters.max_scale || '1.03');
        } else {
            // 如果parameters不存在，从顶层数据获取
            $('#detail-clearance').text(data.clearance ? `${data.clearance}mm` : '--');
            $('#detail-threshold').text(data.threshold || '--');
            $('#detail-scaling').text('--');
            $('#detail-multistart').text('--');
            $('#detail-maxscale').text('--');
        }
        
        // 结果汇总
        const summary = data.summary || {};
        $('#detail-total').text(summary.total_candidates || 0);
        $('#detail-passed').text(summary.passed_p15 || 0);
        $('#detail-strict').text(summary.passed_strict || 0);
        $('#detail-p10').text(summary.passed_p10 || 0);
        $('#detail-p15').text(summary.passed_p15 || 0);
        $('#detail-p20').text(summary.passed_p20 || 0);
        
        // 通过率
        const passRate = summary.total_candidates > 0 ? 
            (summary.passed_p15 / summary.total_candidates * 100) : 0;
        $('#pass-rate-bar').css('width', `${passRate}%`);
        $('#pass-rate-text').text(`${passRate.toFixed(1)}%`);
        
        // 最佳匹配
        if (data.results && data.results.length > 0) {
            const best = data.results[0];
            
            // 使用实际的覆盖率，如果没有则基于P15间隙估算
            let coverageRate = 0;
            if (best.inside_ratio !== undefined && best.inside_ratio !== null) {
                // 使用原算法计算的实际覆盖率
                coverageRate = best.inside_ratio * 100;
            } else if (best.p15_clearance !== undefined) {
                // 仅在没有inside_ratio时才使用估算
                if (best.p15_clearance <= 2.0) {
                    coverageRate = 95 - (best.p15_clearance * 10);
                } else if (best.p15_clearance <= 5.0) {
                    coverageRate = 75 - ((best.p15_clearance - 2) * 10);
                } else {
                    coverageRate = Math.max(0, 45 - ((best.p15_clearance - 5) * 2));
                }
                coverageRate = Math.max(0, Math.min(100, coverageRate));
            }
            
            $('#best-match-info').html(`
                <strong>${best.blank_name}</strong><br>
                <small>覆盖率: ${coverageRate.toFixed(1)}%</small><br>
                <small>体积比: ${best.volume_ratio.toFixed(2)}x</small><br>
                <small>P15间隙: ${best.p15_clearance.toFixed(2)}mm</small>
            `);
        } else {
            $('#best-match-info').html('<span class="text-muted">无匹配结果</span>');
        }
    }
    
    applyFilters() {
        this.filters = {
            status: $('#status-filter').val(),
            date_from: $('#date-from').val(),
            date_to: $('#date-to').val()
        };
        
        // 移除空值
        Object.keys(this.filters).forEach(key => {
            if (!this.filters[key]) {
                delete this.filters[key];
            }
        });
        
        this.loadHistory(1);
        $('#filter-panel').collapse('hide');
    }
    
    async downloadResults(taskId) {
        try {
            // 创建下载链接
            const link = document.createElement('a');
            link.href = `/api/matching/${taskId}/export/`;
            link.download = `matching_result_${taskId}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            Utils.showNotification('开始下载结果文件', 'success');
            
        } catch (error) {
            Utils.showNotification('下载失败: ' + error.message, 'error');
        }
    }
    
    exportHistory() {
        // 导出历史记录功能
        Utils.showNotification('导出功能开发中...', 'info');
    }
    
    showLoading() {
        $('#history-loading').removeClass('d-none');
        $('#history-table').addClass('d-none');
        $('#history-empty').addClass('d-none');
    }
    
    hideLoading() {
        $('#history-loading').addClass('d-none');
        $('#history-table').removeClass('d-none');
    }
    
    showEmpty() {
        $('#history-loading').addClass('d-none');
        $('#history-table').addClass('d-none');
        $('#history-empty').removeClass('d-none');
    }
    
    showError(message) {
        this.hideLoading();
        Utils.showNotification(message, 'error');
    }
    
    updatePagination() {
        // 更新分页控件（如果页面上有的话）
        const paginationEl = $('#pagination');
        if (paginationEl.length === 0) return;
        
        paginationEl.empty();
        
        // 上一页按钮
        if (this.hasPrevious) {
            paginationEl.append(`
                <button class="btn btn-sm btn-outline-primary" onclick="historyApp.loadHistory(${this.currentPage - 1})">
                    <i class="fas fa-chevron-left"></i> 上一页
                </button>
            `);
        }
        
        // 页码信息
        if (this.totalCount > 0) {
            const totalPages = Math.ceil(this.totalCount / this.pageSize);
            paginationEl.append(`
                <span class="mx-3">第 ${this.currentPage} 页 / 共 ${totalPages} 页</span>
            `);
        }
        
        // 下一页按钮
        if (this.hasNext) {
            paginationEl.append(`
                <button class="btn btn-sm btn-outline-primary" onclick="historyApp.loadHistory(${this.currentPage + 1})">
                    下一页 <i class="fas fa-chevron-right"></i>
                </button>
            `);
        }
    }
}

// 全局变量
let historyApp;

// 页面加载完成后初始化
$(document).ready(function() {
    historyApp = new HistoryApp();
});
