/**
 * 3D鞋模智能匹配系统 - 前端JavaScript主控制器
 * 
 * 这个文件包含了匹配页面的所有核心功能：
 * - 鞋模文件上传和管理
 * - 粗胚分类选择和库管理
 * - 匹配任务创建和状态监控
 * - 批量匹配队列处理
 * - 匹配结果展示和热力图生成
 * - 3D模型预览和交互
 * - 数据导出功能
 * 
 * @author 3D ModMatch Team
 * @version 1.0.0
 */

class MatchingApp {
    /**
     * 初始化匹配应用
     * 
     * 设置应用的核心状态变量和初始化流程
     */
    constructor() {
        // ==================== 核心状态管理 ====================
        this.currentShoeModel = null;        // 当前选中的鞋模文件
        this.selectedCategories = [];        // 已选择的粗胚分类ID列表
        this.currentTask = null;             // 当前匹配任务信息
        this.pollTimer = null;               // 任务状态轮询定时器
        
        // ==================== 批量匹配队列管理 ====================
        this.queuedShoeModels = [];          // 待匹配的鞋模队列
        this.currentQueueIndex = -1;         // 当前处理的队列索引
        this.completedMatches = [];          // 已完成的匹配结果
        this.isQueueProcessing = false;      // 队列是否正在处理中
        
        // 启动应用初始化
        this.init();
    }
    
    /**
     * 初始化应用
     * 
     * 绑定事件监听器和加载初始数据
     */
    init() {
        this.bindEvents();
        this.loadInitialData();
    }
    
    /**
     * 绑定所有事件监听器
     * 
     * 使用事件委托避免重复绑定，提高性能和稳定性
     */
    bindEvents() {
        // 防止重复绑定事件，避免内存泄漏
        if (this._eventsBound) {
            console.log('事件已绑定，跳过');
            return;
        }
        
        // ==================== 核心匹配功能事件 ====================
        // 开始匹配按钮 - 触发匹配流程
        $('#startMatching').off('click').on('click', () => this.startMatching());
        
        // ==================== 鞋模文件上传事件 ====================
        // 文件选择按钮 - 触发文件选择对话框
        $(document).off('click', '#select-shoe-file').on('click', '#select-shoe-file', (e) => {
            e.preventDefault();
            e.stopPropagation();
            $('#shoe-file-input').click();
        });
        
        // 文件选择变化 - 处理用户选择的文件
        $(document).off('change', '#shoe-file-input').on('change', '#shoe-file-input', (e) => {
            this.handleShoeFileSelect(e);
        });
        
        // 确认上传按钮 - 开始上传文件
        $(document).off('click', '#confirm-shoe-upload').on('click', '#confirm-shoe-upload', () => {
            this.uploadShoeFile();
        });
        
        // 预览鞋模按钮 - 显示3D预览
        $(document).off('click', '#preview-shoe-btn').on('click', '#preview-shoe-btn', () => {
            this.previewShoeModel();
        });
        
        // ==================== 粗胚库管理事件 ====================
        // 管理粗胚库按钮 - 打开粗胚管理界面
        $(document).off('click', '#manage-blank-library-btn').on('click', '#manage-blank-library-btn', () => {
            this.showBlankManage();
        });
        
        // 上传粗胚按钮 - 打开批量上传界面
        $(document).off('click', '#upload-blank-btn').on('click', '#upload-blank-btn', () => {
            this.showBlankUpload();
        });
        
        // 管理分类按钮 - 打开分类管理界面
        $(document).off('click', '#manage-categories-btn').on('click', '#manage-categories-btn', () => {
            this.showCategoryManage();
        });
        
        // 应用粗胚选择按钮 - 确认选择的分类
        $(document).off('click', '#apply-blank-selection').on('click', '#apply-blank-selection', () => {
            this.applyBlankSelection();
        });
        
        // ==================== 匹配参数验证事件 ====================
        // 间隙参数输入 - 实时验证参数有效性
        $('#clearance').off('input').on('input', () => this.validateMatchingParams());
        // 阈值参数选择 - 更新参数说明
        $('#threshold').off('change').on('change', () => this.validateMatchingParams());
        // 启用缩放选项 - 控制缩放相关参数
        $('#enableScaling').off('change').on('change', () => this.toggleScalingOptions());
        // 最大缩放比例 - 验证缩放参数
        $('#maxScale').off('input').on('input', () => this.validateScalingParams());
        
        // ==================== 数据导出功能事件 ====================
        // 导出报告按钮 - 导出匹配结果报告
        $('#export-report-btn').off('click').on('click', () => this.exportReport());
        // 导出模型按钮 - 导出3D模型文件
        $('#export-models-btn').off('click').on('click', () => this.exportModels());
        
        // ==================== 文件拖拽上传功能 ====================
        // 设置拖拽上传区域
        this.setupDragAndDrop();
        
        // ==================== 3D预览控制事件 ====================
        // 全屏热力图按钮 - 切换全屏显示
        $(document).off('click', '#fullscreen-heatmap').on('click', '#fullscreen-heatmap', () => {
            this.toggleHeatmapFullscreen();
        });
        
        // 截图按钮 - 保存当前3D视图
        $(document).off('click', '#download-heatmap').on('click', '#download-heatmap', () => {
            this.downloadHeatmapScreenshot();
        });
        
        // ==================== 跨页面通信事件 ====================
        // 监听分类变化事件，当分类管理页面有变化时自动刷新主页面的分类选择
        $(document).off('categoryChanged.mainPage').on('categoryChanged.mainPage', () => {
            console.log('检测到分类变化，刷新主页面分类选择');
            this.loadCategories();
        });
        
        // 标记事件已绑定，防止重复绑定
        this._eventsBound = true;
        console.log('匹配页面事件绑定完成');
    }
    
    /**
     * 加载初始数据
     * 
     * 页面加载时获取必要的初始数据，包括分类信息和任务结果
     */
    loadInitialData() {
        // 加载粗胚分类数据
        this.loadCategories();
        
        // 检查URL参数，如果有task参数则加载任务结果
        // 支持通过URL直接访问特定任务的结果页面
        const urlParams = new URLSearchParams(window.location.search);
        const taskId = urlParams.get('task');
        if (taskId) {
            console.log('从URL加载任务结果:', taskId);
            this.loadTaskResults(taskId);
        }
    }
    
    /**
     * 异步加载粗胚分类数据
     * 
     * 从后端API获取所有可用的粗胚分类，用于用户选择匹配范围
     */
    async loadCategories() {
        try {
            // 显示加载状态
            Utils.showLoading('#category-selection');
            
            // 请求分类数据
            const response = await Utils.apiRequest('/api/blanks/categories/');
            if (response.success) {
                this.renderCategories(response.data);
            }
        } catch (error) {
            // 显示错误状态
            $('#category-selection').html(`
                <div class="text-danger text-center py-3">
                    <i class="fas fa-exclamation-triangle"></i>
                    <br>加载分类失败
                </div>
            `);
            Utils.showNotification('加载分类失败: ' + error.message, 'error');
        }
    }
    
    /**
     * 渲染分类选择界面
     * 
     * @param {Array} categories - 分类数据数组
     */
    renderCategories(categories) {
        if (!categories || categories.length === 0) {
            // 没有分类时显示提示信息
            $('#category-selection').html(`
                <div class="text-muted text-center py-3">
                    <i class="fas fa-folder-open"></i>
                    <br>暂无分类，请先管理粗胚库
                </div>
            `);
            return;
        }
        
        // 生成分类HTML
        let html = '';
        categories.forEach(category => {
            html += this.renderCategoryItem(category);
        });
        
        $('#category-selection').html(html);
        
        // 绑定分类选择事件
        $('.category-item').on('click', (e) => {
            const categoryId = $(e.currentTarget).data('category-id');
            this.toggleCategory(categoryId);
        });
    }
    
    /**
     * 递归渲染单个分类项
     * 
     * @param {Object} category - 分类对象
     * @param {number} level - 层级深度，用于缩进显示
     * @returns {string} 分类项的HTML字符串
     */
    renderCategoryItem(category, level = 0) {
        const marginLeft = level * 20; // 每级缩进20px
        const icon = level === 0 ? 'fa-folder' : 'fa-tag';  // 根分类用文件夹图标，子分类用标签图标
        const textClass = level === 0 ? 'fw-bold' : '';     // 根分类加粗显示
        
        let html = `
            <div class="category-item d-flex align-items-center py-2 px-2 border-bottom bg-light rounded mb-1" 
                 data-category-id="${category.id}" 
                 style="margin-left: ${marginLeft}px; cursor: pointer; transition: all 0.2s ease;"
                 title="${category.description || category.name}">
                <i class="fas ${icon} me-2 text-primary"></i>
                <span class="${textClass}">${category.name}</span>
                ${category.children && category.children.length > 0 ? 
                    `<small class="text-muted ms-auto">(${category.children.length})</small>` : ''}
            </div>
        `;
        
        // 递归渲染子分类
        if (category.children && category.children.length > 0) {
            category.children.forEach(child => {
                html += this.renderCategoryItem(child, level + 1);
            });
        }
        
        return html;
    }
    
    /**
     * 切换分类选择状态
     * 
     * 处理用户点击分类项时的选择/取消选择逻辑
     * 
     * @param {string} categoryId - 分类ID
     */
    toggleCategory(categoryId) {
        const index = this.selectedCategories.indexOf(categoryId);
        const element = $(`.category-item[data-category-id="${categoryId}"]`);
        
        if (index > -1) {
            // ==================== 取消选择 ====================
            // 从选中列表中移除该分类
            this.selectedCategories.splice(index, 1);
            // 更新UI样式为未选中状态
            element.removeClass('bg-primary text-white').addClass('bg-light');
        } else {
            // ==================== 添加选择 ====================
            // 将分类添加到选中列表
            this.selectedCategories.push(categoryId);
            // 更新UI样式为选中状态
            element.removeClass('bg-light').addClass('bg-primary text-white');
        }
        
        // 更新匹配按钮状态
        this.updateMatchingButton();
    }
    
    /**
     * 更新匹配按钮状态
     * 
     * 根据当前是否有鞋模文件和选择的分类来启用/禁用匹配按钮
     */
    updateMatchingButton() {
        const hasShoe = this.currentShoeModel !== null || (this.uploadedShoeModels && this.uploadedShoeModels.length > 0);
        const hasCategories = this.selectedCategories.length > 0;
        const isProcessing = this.isQueueProcessing;
        
        const button = $('#startMatching');
        if (isProcessing) {
            button.prop('disabled', true);
            button.removeClass('btn-warning btn-secondary').addClass('btn-info');
            button.html('<i class="fas fa-spinner fa-spin me-2"></i>队列匹配中...');
        } else if (hasShoe && hasCategories) {
            button.prop('disabled', false);
            button.removeClass('btn-secondary btn-info').addClass('btn-warning');
            button.html('<i class="fas fa-play me-2"></i>开始匹配');
        } else {
            button.prop('disabled', true);
            button.removeClass('btn-warning btn-info').addClass('btn-secondary');
            button.html('<i class="fas fa-play me-2"></i>开始匹配');
        }
    }
    
    /**
     * 开始匹配任务
     * 
     * 这是匹配流程的入口点，处理单文件匹配和批量匹配的逻辑分发
     */
    async startMatching() {
        // ==================== 批量匹配检查 ====================
        // 检查是否有多个鞋模文件，如果有则显示批量匹配选项
        if (this.uploadedShoeModels && this.uploadedShoeModels.length > 1) {
            // 检查是否选择了分类
            if (this.selectedCategories.length === 0) {
                Utils.showNotification('请先选择粗胚分类', 'warning');
                return;
            }
            // 显示批量匹配选项Modal
            this.showBatchMatchingOptions();
            return;
        }
        
        // ==================== 单文件匹配验证 ====================
        // 验证是否有鞋模文件和选择的分类
        if (!this.currentShoeModel || this.selectedCategories.length === 0) {
            Utils.showNotification('请先上传鞋模文件并选择粗胚分类', 'warning');
            return;
        }
        
        try {
            // ==================== 参数验证 ====================
            // 验证匹配参数的有效性
            if (!this.validateMatchingParams()) {
                return;
            }
            
            // ==================== 准备匹配参数 ====================
            // 收集所有匹配参数
            const params = {
                shoe_model_id: this.currentShoeModel.id,    // 目标鞋模ID
                category_ids: this.selectedCategories,      // 选择的分类ID列表
                ...this.getMatchingParams()                 // 其他匹配参数（间隙、阈值等）
            };
            
            // ==================== 显示匹配状态 ====================
            // 切换到匹配进行中的UI状态
            this.showMatchingStatus();
            
            // ==================== 检查鞋模处理状态 ====================
            // 确保鞋模文件已完全处理完成
            await this.checkShoeProcessingStatus();
            
            // ==================== 发起匹配请求 ====================
            // 向后端API发送匹配任务请求
            const response = await Utils.apiRequest('/api/matching/start/', {
                method: 'POST',
                body: JSON.stringify(params)
            });
            
            if (response.success) {
                // 保存任务信息并开始状态轮询
                this.currentTask = response.data;
                this.matchingStartTime = Date.now(); // 记录开始时间，用于进度估算
                this.startPolling(this.currentTask);
                Utils.showNotification('匹配任务已开始', 'success');
            }
            
        } catch (error) {
            // 匹配启动失败，恢复UI状态
            this.hideMatchingStatus();
            Utils.showNotification('启动匹配失败: ' + error.message, 'error');
        }
    }
    
    /**
     * 显示匹配状态界面
     * 
     * 切换到匹配进行中的UI状态，显示进度条和状态信息
     */
    showMatchingStatus() {
        // ==================== 切换UI状态 ====================
        // 隐藏默认状态和结果容器，显示匹配状态
        $('#default-state').addClass('d-none');
        $('#results-container').addClass('d-none');
        $('#matching-status').removeClass('d-none');
        
        // ==================== 初始化状态信息 ====================
        // 设置初始状态消息和进度
        $('#status-message').text('正在初始化匹配任务...');
        $('#progress-bar').css('width', '0%');
        $('#progress-detail').text('准备中...');
    }
    
    /**
     * 隐藏匹配状态界面
     * 
     * 从匹配状态切换回默认状态
     */
    hideMatchingStatus() {
        // 隐藏匹配状态，显示默认状态
        $('#matching-status').addClass('d-none');
        $('#default-state').removeClass('d-none');
    }
    
    /**
     * 开始任务状态轮询
     * 
     * 定期检查匹配任务的执行状态，更新进度显示
     * 
     * @param {Object} task - 要轮询的任务对象
     */
    startPolling(task) {
        // 清除之前的轮询定时器，避免重复轮询
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
        }
        
        // 设置新的轮询定时器，传入任务对象
        this.pollTimer = setInterval(() => {
            this.checkTaskStatus(task);
        }, CONFIG.POLL_INTERVAL);
    }
    
    /**
     * 停止任务状态轮询
     * 
     * 清理轮询定时器并更新UI状态
     */
    stopPolling() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
        
        // 更新匹配按钮状态
        this.updateMatchingButton();
    }
    
    /**
     * 检查任务执行状态
     * 
     * 向后端查询指定任务的执行状态，更新进度并处理完成/失败状态
     * 
     * @param {Object} currentTask - 要检查的任务对象
     */
    async checkTaskStatus(currentTask) {
        try {
            // 请求任务状态
            const response = await Utils.apiRequest(`/api/matching/${currentTask.task_id}/status/`);
            
            if (response.success) {
                const status = response.data;
                this.updateProgress(status);
                
                if (status.status === 'completed') {
                    // 任务完成
                    this.stopPolling();
                    if (this.isQueueProcessing) {
                        // 队列模式：加载结果并继续下一个任务
                        await this.handleQueueTaskComplete(currentTask);
                    } else {
                        // 单任务模式：正常加载结果
                        this.loadResults();
                    }
                } else if (status.status === 'failed') {
                    // 任务失败
                    this.stopPolling();
                    if (this.isQueueProcessing) {
                        // 队列模式：记录失败并继续下一个任务
                        await this.handleQueueTaskFailed();
                    } else {
                        // 单任务模式：显示错误信息
                        this.showError('匹配任务失败');
                    }
                }
            }
        } catch (error) {
            console.error('检查任务状态失败:', error);
        }
    }
    
    /**
     * 更新匹配进度显示
     * 
     * 根据任务状态更新进度条、当前步骤和预计剩余时间
     * 
     * @param {Object} status - 任务状态对象
     */
    updateProgress(status) {
        const progress = status.progress || 0;                    // 进度百分比
        const currentStep = status.current_step || '处理中...';    // 当前执行步骤
        const estimatedRemaining = status.estimated_remaining;    // 服务器提供的预计剩余时间
        
        // ==================== 更新进度条 ====================
        // 更新进度条的宽度和数值
        $('#progress-bar').css('width', `${progress}%`).attr('aria-valuenow', progress);
        
        // ==================== 更新状态消息 ====================
        // 显示当前正在执行的步骤
        $('#status-message').text(currentStep);
        
        // ==================== 更新预计剩余时间 ====================
        let detailText = '';
        if (estimatedRemaining && estimatedRemaining > 0) {
            // 优先使用服务器提供的预计时间
            const minutes = Math.floor(estimatedRemaining / 60);
            const seconds = estimatedRemaining % 60;
            if (minutes > 0) {
                detailText = `预计剩余: ${minutes}分${seconds}秒`;
            } else {
                detailText = `预计剩余: ${seconds}秒`;
            }
        } else {
            // 根据进度估算时间（本地计算）
            if (progress > 0 && progress < 100) {
                const estimatedTotal = (Date.now() - this.matchingStartTime) / progress * 100;
                const remaining = Math.max(0, estimatedTotal - (Date.now() - this.matchingStartTime));
                const remainingSeconds = Math.round(remaining / 1000);
                
                if (remainingSeconds > 60) {
                    const mins = Math.floor(remainingSeconds / 60);
                    const secs = remainingSeconds % 60;
                    detailText = `预计剩余: 约${mins}分${secs}秒`;
                } else {
                    detailText = `预计剩余: 约${remainingSeconds}秒`;
                }
            } else {
                detailText = '处理中...';
            }
        }
        
        $('#progress-detail').text(detailText);
        
        // 添加进度百分比显示
        if ($('#progress-percentage').length === 0) {
            $('#progress-bar').after('<div id="progress-percentage" class="text-center mt-1 small text-muted"></div>');
        }
        $('#progress-percentage').text(`${progress.toFixed(1)}%`);
    }
    
    /**
     * 检查鞋模文件处理状态
     * 
     * 确保鞋模文件已完全处理完成，可以用于匹配
     * 如果未处理完成，会轮询等待直到处理完成或超时
     */
    async checkShoeProcessingStatus() {
        try {
            console.log(`检查鞋模处理状态: shoe_id=${this.currentShoeModel.id}`);
            
            // ==================== 初始状态检查 ====================
            // 检查鞋模处理状态
            const response = await Utils.apiRequest(`/api/shoes/${this.currentShoeModel.id}/`);
            console.log('鞋模状态响应:', response);
            
            if (response.success && response.data.is_processed) {
                console.log('鞋模已处理完成，可以开始匹配');
                return; // 已处理完成
            }
            
            // 如果未处理完成，显示等待状态并轮询
            this.updateProgress({ 
                progress: 0, 
                current_step: '等待鞋模处理完成...' 
            });
            
            let attempts = 0;
            const maxAttempts = 30; // 最多等待30秒
            
            while (attempts < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 1000)); // 等待1秒
                
                console.log(`轮询检查鞋模状态 (第${attempts + 1}次)`);
                const statusResponse = await Utils.apiRequest(`/api/shoes/${this.currentShoeModel.id}/`);
                
                if (statusResponse.success && statusResponse.data.is_processed) {
                    console.log('鞋模处理完成！');
                    this.updateProgress({ 
                        progress: 5, 
                        current_step: '鞋模处理完成，准备开始匹配...' 
                    });
                    return; // 处理完成
                }
                
                attempts++;
                console.log(`鞋模仍在处理中... (${attempts}/${maxAttempts}), status=${statusResponse.data?.processing_status}`);
                this.updateProgress({ 
                    progress: Math.min(attempts * 2, 10), 
                    current_step: `等待鞋模处理完成... (${attempts}/${maxAttempts})` 
                });
            }
            
            throw new Error('鞋模处理超时，请稍后重试');
            
        } catch (error) {
            throw new Error(`检查鞋模状态失败: ${error.message}`);
        }
    }
    
    /**
     * 加载当前任务的匹配结果
     * 
     * 从后端获取当前匹配任务的详细结果数据
     */
    async loadResults() {
        try {
            const response = await Utils.apiRequest(`/api/matching/${this.currentTask.task_id}/result/`);
            
            if (response.success) {
                this.showResults(response.data);
            }
        } catch (error) {
            this.showError('加载结果失败: ' + error.message);
        }
    }
    
    /**
     * 加载指定任务的匹配结果
     * 
     * 用于从URL参数或历史记录中加载特定任务的结果
     * 
     * @param {string} taskId - 任务ID
     */
    async loadTaskResults(taskId) {
        try {
            console.log('加载任务结果:', taskId);
            
            // ==================== 显示加载状态 ====================
            // 显示加载中状态
            $('#matching-status').removeClass('d-none');
            $('#status-message').text('正在加载任务结果...');
            $('#progress-bar').css('width', '100%').addClass('progress-bar-striped progress-bar-animated');
            
            // ==================== 请求任务结果 ====================
            const response = await Utils.apiRequest(`/api/matching/${taskId}/result/`);
            
            if (response.success) {
                // 设置当前任务信息
                this.currentTask = {
                    task_id: taskId,
                    status: response.data.status
                };
                
                // 设置鞋模信息
                if (response.data.shoe_model_name) {
                    this.currentShoeModel = {
                        name: response.data.shoe_model_name
                    };
                }
                
                // 显示结果
                this.showResults(response.data);
                
                // 更新参数显示
                if (response.data.parameters) {
                    $('#clearance').val(response.data.parameters.clearance);
                    $('#threshold').val(response.data.parameters.threshold);
                    $('#auto-scale').prop('checked', response.data.parameters.auto_scale);
                    $('#multi-orientation').prop('checked', response.data.parameters.multi_orientation);
                }
            } else {
                this.showError('任务不存在或已过期');
            }
        } catch (error) {
            this.showError('加载任务结果失败: ' + error.message);
        }
    }
    
    /**
     * 显示匹配结果
     * 
     * 切换到结果展示界面，显示匹配结果和统计信息
     * 
     * @param {Object} data - 匹配结果数据
     */
    showResults(data) {
        // ==================== 切换UI状态 ====================
        // 隐藏匹配状态，显示结果容器
        $('#matching-status').addClass('d-none');
        $('#results-container').removeClass('d-none');
        $('#result-actions').removeClass('d-none');
        
        // ==================== 保存结果数据 ====================
        // 保存结果数据供后续操作使用
        this.currentResults = data.results;
        this.currentSummary = data.summary;
        
        // ==================== 更新统计信息 ====================
        // 更新结果数量和处理时间
        $('#results-count').text(data.results.length);
        $('#processing-time').text(data.summary.processing_time ? data.summary.processing_time.toFixed(2) : '--');
        
        // ==================== 渲染结果表格 ====================
        // 渲染结果表格
        this.renderResultsTable(data.results);
        
        // 显示汇总信息
        this.showResultsSummary(data.summary);
        
        Utils.showNotification('匹配完成！', 'success');
    }
    
    /**
     * 显示匹配结果汇总信息
     * 
     * 在结果页面顶部显示匹配统计信息，包括各种通过标准的数量
     * 
     * @param {Object} summary - 匹配汇总数据
     */
    showResultsSummary(summary) {
        // ==================== 构建汇总HTML ====================
        // 创建统计信息展示区域
        const summaryHtml = `
            <div class="row mb-3">
                <div class="col-md-3 text-center">
                    <div class="border rounded p-2">
                        <h6 class="text-primary mb-1">${summary.total_candidates || 0}</h6>
                        <small class="text-muted">总候选数</small>
                    </div>
                </div>
                <div class="col-md-3 text-center">
                    <div class="border rounded p-2">
                        <h6 class="text-success mb-1">${summary.passed_p15 || 0}</h6>
                        <small class="text-muted">P15通过</small>
                    </div>
                </div>
                <div class="col-md-3 text-center">
                    <div class="border rounded p-2">
                        <h6 class="text-warning mb-1">${summary.passed_p10 || 0}</h6>
                        <small class="text-muted">P10通过</small>
                    </div>
                </div>
                <div class="col-md-3 text-center">
                    <div class="border rounded p-2">
                        <h6 class="text-danger mb-1">${summary.passed_strict || 0}</h6>
                        <small class="text-muted">严格通过</small>
                    </div>
                </div>
            </div>
        `;
        
        // 在结果表格前插入汇总信息
        if ($('#results-summary').length === 0) {
            $('#results-table').before('<div id="results-summary"></div>');
        }
        $('#results-summary').html(summaryHtml);
    }
    
    /**
     * 渲染匹配结果表格
     * 
     * 将匹配结果数据渲染为HTML表格，包括状态徽章、覆盖率等信息
     * 
     * @param {Array} results - 匹配结果数组
     */
    renderResultsTable(results) {
        // ==================== 清空表格 ====================
        // 清空现有表格内容
        const tbody = $('#results-table tbody');
        tbody.empty();
        
        // ==================== 渲染结果行 ====================
        // 遍历每个匹配结果，生成表格行
        results.forEach((result, index) => {
            const statusBadge = this.getStatusBadge(result);
            
            // ==================== 计算覆盖率 ====================
            // 使用实际的覆盖率，如果没有则基于P15间隙估算
            let coverageRate = 0;
            if (result.inside_ratio !== undefined && result.inside_ratio !== null) {
                // 使用原算法计算的实际覆盖率
                coverageRate = result.inside_ratio * 100;
            } else if (result.p15_clearance !== undefined) {
                // // 仅在没有inside_ratio时才使用估算
                // if (result.p15_clearance <= 2.0) {
                //     coverageRate = 95 - (result.p15_clearance * 10);
                // } else if (result.p15_clearance <= 5.0) {
                //     coverageRate = 75 - ((result.p15_clearance - 2) * 10);
                // } else {
                //     coverageRate = Math.max(0, 45 - ((result.p15_clearance - 5) * 2));
                // }
                coverageRate = 0;
            }
            
            const row = $(`
                <tr data-result-index="${index}">
                    <td>
                        <strong>${result.blank_name}</strong>
                        <br><small class="text-muted">缩放: ${result.scale_used.toFixed(3)}</small>
                    </td>
                    <td>
                        <span class="badge bg-info">${coverageRate.toFixed(1)}%</span>
                    </td>
                    <td>
                        <span class="badge bg-success">${result.volume_ratio.toFixed(2)}x</span>
                    </td>
                    <td>
                        <span class="badge bg-warning text-dark">${result.p15_clearance.toFixed(2)}mm</span>
                    </td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="matchingApp.showResultDetail(${index})">
                            <i class="fas fa-eye"></i> 详情
                        </button>
                    </td>
                </tr>
            `);
            tbody.append(row);
        });
    }
    
    /**
     * 获取状态徽章HTML
     * 
     * 根据匹配结果生成相应的状态徽章，用于在表格中显示
     * 
     * @param {Object} result - 匹配结果对象
     * @returns {string} 状态徽章的HTML字符串
     */
    getStatusBadge(result) {
        if (result.pass_p15) {
            return '<span class="badge status-pass"><i class="fas fa-check"></i> 通过</span>';
        } else if (result.inside_ratio >= 0.95) {
            return '<span class="badge status-warning"><i class="fas fa-exclamation"></i> 间隙不足</span>';
        } else {
            return '<span class="badge status-fail"><i class="fas fa-times"></i> 不匹配</span>';
        }
    }
    
    /**
     * 显示结果详情
     * 
     * 打开结果详情模态框，显示指定索引的匹配结果详细信息
     * 
     * @param {number} index - 结果索引
     */
    showResultDetail(index) {
        // ==================== 验证结果数据 ====================
        // 检查结果数据是否存在
        if (!this.currentResults || !this.currentResults[index]) {
            Utils.showNotification('结果数据不存在', 'error');
            return;
        }
        
        const result = this.currentResults[index];
        
        // 更新结果详情Modal
        this.updateResultDetailModal(result, index);
        
        // 显示Modal
        $('#resultDetailModal').modal('show');
        
        // 加载3D预览（透明叠加视图）- 支持所有结果
        if (this.currentTask) {
            // 确保传递的是 task_id 字符串，而不是整个对象
            const taskId = typeof this.currentTask === 'string' ? this.currentTask : this.currentTask.task_id;
            if (taskId) {
                this.loadTransparentOverlay(taskId, index);
            }
        }
    }
    
    updateResultDetailModal(result) {
        // 使用实际的覆盖率，如果没有则基于P15间隙估算
        let coverageRate = 0;
        if (result.inside_ratio !== undefined && result.inside_ratio !== null) {
            // 使用原算法计算的实际覆盖率
            coverageRate = result.inside_ratio * 100;
        } else if (result.p15_clearance !== undefined) {
            // 仅在没有inside_ratio时才使用估算
            if (result.p15_clearance <= 2.0) {
                coverageRate = 95 - (result.p15_clearance * 10);
            } else if (result.p15_clearance <= 5.0) {
                coverageRate = 75 - ((result.p15_clearance - 2) * 10);
            } else {
                coverageRate = Math.max(0, 45 - ((result.p15_clearance - 5) * 2));
            }
            coverageRate = Math.max(0, Math.min(100, coverageRate));
        }
        
        // 更新指标
        $('#metric-coverage').text(coverageRate.toFixed(1));
        $('#progress-coverage').css('width', `${coverageRate}%`);
        
        $('#metric-volume').text(result.volume_ratio.toFixed(2));
        $('#metric-p15').text(result.p15_clearance.toFixed(2));
        $('#metric-min').text(result.min_clearance.toFixed(2));
        $('#metric-chamfer').text(result.chamfer.toFixed(2));
        
        // 更新整体状态
        const overallStatus = this.getOverallStatus(result);
        $('#overall-status').removeClass().addClass(`badge fs-6 p-2 ${overallStatus.class}`)
                           .html(`<i class="fas ${overallStatus.icon} me-1"></i>${overallStatus.text}`);
        
        // 注意：3D预览在 showResultDetail 方法中调用 loadTransparentOverlay 加载
    }
    
    getOverallStatus(result) {
        if (result.pass_strict) {
            return {
                class: 'bg-success',
                icon: 'fa-check-circle',
                text: '严格标准通过'
            };
        } else if (result.pass_p15) {
            return {
                class: 'bg-warning text-dark',
                icon: 'fa-exclamation-circle',
                text: 'P15标准通过'
            };
        } else if (result.inside_ratio >= 0.95) {
            return {
                class: 'bg-info',
                icon: 'fa-info-circle',
                text: '覆盖良好，间隙不足'
            };
        } else {
            return {
                class: 'bg-danger',
                icon: 'fa-times-circle',
                text: '不匹配'
            };
        }
    }
    
    /**
     * 加载透明叠加3D预览
     * 
     * 加载鞋模和粗胚的透明叠加视图，支持所有匹配结果
     * 
     * @param {string} taskId - 任务ID
     * @param {number} resultIndex - 结果索引
     */
    async loadTransparentOverlay(taskId, resultIndex) {
        try {
            // ==================== 清空并准备容器 ====================
            const container = document.getElementById('heatmap-preview');
            container.innerHTML = '';
            
            // 清空容器后，重置 viewer 引用（因为 DOM 元素已被移除）
            this.transparentViewer = null;
            
            // ==================== 创建 Three.js 查看器 ====================
            // 每次都重新创建 viewer，确保 DOM 元素正确关联
            const viewer = new ThreeModelViewer(container, {
                antialias: true,
                alpha: true
            });
            this.transparentViewer = viewer;
            
            // ==================== 创建透明叠加查看器 ====================
            const overlayViewer = new TransparentOverlayViewer(viewer, {
                targetColor: 0x808080,      // 灰色鞋模
                candidateColor: 0x4080FF,   // 蓝色粗胚
                candidateOpacity: 0.5        // 半透明
            });
            
            // ==================== 加载透明叠加视图 ====================
            await overlayViewer.loadTransparentOverlay(taskId, resultIndex);
            
            console.log(`透明叠加视图加载完成: ${taskId}/${resultIndex}`);
            
        } catch (error) {
            console.error('加载透明叠加视图失败:', error);
            
            // ==================== 显示错误信息 ====================
            $('#heatmap-preview').html(`
                <div class="d-flex align-items-center justify-content-center h-100">
                    <div class="text-center text-danger">
                        <i class="fas fa-exclamation-triangle fa-3x mb-3"></i>
                        <h5>加载失败</h5>
                        <p>${error.message || '无法加载3D预览'}</p>
                        <button class="btn btn-sm btn-outline-primary mt-2" 
                                onclick="matchingApp.loadTransparentOverlay('${taskId}', ${resultIndex})">
                            <i class="fas fa-redo me-1"></i>重试
                        </button>
                    </div>
                </div>
            `);
        }
    }
    
    /**
     * 加载热力图并检查生成状态（已弃用，保留用于向后兼容）
     * 
     * 检查热力图的生成状态，如果正在生成则显示进度，如果已完成则加载热力图
     * 
     * @param {string} taskId - 任务ID
     * @param {number} resultIndex - 结果索引
     * @deprecated 使用 loadTransparentOverlay 替代
     */
    async loadHeatmapWithStatus(taskId, resultIndex) {
        try {
            // ==================== 检查热力图状态 ====================
            // 首先检查热力图生成状态
            const statusResponse = await Utils.apiRequest(`/api/matching/${taskId}/heatmap-status/`);
            
            if (statusResponse.success) {
                const heatmapStatus = statusResponse.data.heatmap_status;
                const heatmapData = statusResponse.data.heatmap_data || {};
                
                if (heatmapStatus === 'not_started') {
                    // ==================== 热力图未开始 ====================
                    $('#heatmap-preview').html(`
                        <div class="d-flex align-items-center justify-content-center h-100">
                            <div class="text-center text-muted">
                                <i class="fas fa-clock fa-2x mb-2"></i>
                                <p>热力图待生成</p>
                                <small>热力图将在后台自动生成</small>
                            </div>
                        </div>
                    `);
                    // 延迟后再次检查
                    setTimeout(() => this.loadHeatmapWithStatus(taskId, resultIndex), 3000);
                    
                } else if (heatmapStatus === 'generating') {
                    const progress = heatmapData.progress || 0;
                    const message = heatmapData.message || '生成中...';
                    
                    $('#heatmap-preview').html(`
                        <div class="d-flex align-items-center justify-content-center h-100">
                            <div class="text-center">
                                <i class="fas fa-spinner fa-spin fa-2x text-primary mb-2"></i>
                                <p>${message}</p>
                                <div class="progress" style="width: 200px;">
                                    <div class="progress-bar" role="progressbar" 
                                         style="width: ${progress}%" 
                                         aria-valuenow="${progress}" 
                                         aria-valuemin="0" 
                                         aria-valuemax="100">${progress}%</div>
                                </div>
                            </div>
                        </div>
                    `);
                    // 定期检查状态
                    setTimeout(() => this.loadHeatmapWithStatus(taskId, resultIndex), 2000);
                    
                } else if (heatmapStatus === 'completed') {
                    // 热力图已生成，显示热力图
                    const heatmaps = heatmapData.heatmaps || [];
                    const heatmap = heatmaps[resultIndex];
                    
                    if (heatmap && heatmap.url) {
                        $('#heatmap-preview').html(`
                            <iframe src="${heatmap.url}" 
                                    style="width: 100%; height: 600px; border: none;"
                                    title="热力图"></iframe>
                        `);
                    } else {
                        // 尝试从可视化API加载
                        this.loadHeatmap(taskId, resultIndex);
                    }
                    
                } else if (heatmapStatus === 'failed') {
                    const error = heatmapData.error || '生成失败';
                    $('#heatmap-preview').html(`
                        <div class="d-flex align-items-center justify-content-center h-100">
                            <div class="text-center text-danger">
                                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                                <p>热力图生成失败</p>
                                <small>${error}</small>
                            </div>
                        </div>
                    `);
                }
            } else {
                // 状态查询失败，尝试直接加载
                this.loadHeatmap(taskId, resultIndex);
            }
            
        } catch (error) {
            console.error('加载热力图状态失败:', error);
            this.loadHeatmap(taskId, resultIndex);
        }
    }
    
    async loadHeatmap(taskId, resultIndex) {
        try {
            const response = await Utils.apiRequest(`/api/visualization/heatmap/${taskId}/${resultIndex}/`);
            
            if (response.success) {
                $('#heatmap-preview').html(response.data.html);
            } else {
                $('#heatmap-preview').html(`
                    <div class="d-flex align-items-center justify-content-center h-100">
                        <div class="text-center text-muted">
                            <i class="fas fa-image fa-2x mb-2"></i>
                            <p>热力图暂不可用</p>
                        </div>
                    </div>
                `);
            }
            
        } catch (error) {
            $('#heatmap-preview').html(`
                <div class="d-flex align-items-center justify-content-center h-100">
                    <div class="text-center text-muted">
                        <i class="fas fa-times fa-2x mb-2"></i>
                        <p>加载错误</p>
                    </div>
                </div>
            `);
        }
    }
    
    /**
     * 显示错误信息
     * 
     * 当匹配过程中出现错误时，切换回默认状态并显示错误通知
     * 
     * @param {string} message - 错误消息
     */
    showError(message) {
        // ==================== 恢复UI状态 ====================
        // 隐藏匹配状态，显示默认状态
        $('#matching-status').addClass('d-none');
        $('#default-state').removeClass('d-none');
        
        // ==================== 显示错误通知 ====================
        // 显示错误通知
        Utils.showNotification(message, 'error');
    }
    
    // ========== 鞋模上传功能 ==========
    
    /**
     * 设置拖拽上传功能
     * 
     * 为文件上传区域添加拖拽上传支持，包括拖拽悬停效果和文件处理
     */
    setupDragAndDrop() {
        // ==================== 拖拽悬停效果 ====================
        // 使用事件委托避免重复绑定
        $(document).off('dragover', '#shoe-upload-zone').on('dragover', '#shoe-upload-zone', (e) => {
            e.preventDefault();
            e.stopPropagation();
            $('#shoe-upload-zone').addClass('dragover');
        });
        
        // ==================== 拖拽离开效果 ====================
        $(document).off('dragleave', '#shoe-upload-zone').on('dragleave', '#shoe-upload-zone', (e) => {
            e.preventDefault();
            e.stopPropagation();
            $('#shoe-upload-zone').removeClass('dragover');
        });
        
        // ==================== 文件拖拽放置 ====================
        $(document).off('drop', '#shoe-upload-zone').on('drop', '#shoe-upload-zone', (e) => {
            e.preventDefault();
            e.stopPropagation();
            $('#shoe-upload-zone').removeClass('dragover');
            
            // 处理拖拽的文件
            const files = e.originalEvent.dataTransfer.files;
            if (files.length > 0) {
                this.handleShoeFile(files[0]);
            }
        });
        
        // ==================== 清理冲突事件 ====================
        // 移除可能导致冲突的click事件
        $(document).off('click', '#shoe-upload-zone');
    }
    
    /**
     * 处理鞋模文件选择事件
     * 
     * 当用户通过文件选择对话框选择文件时触发
     * 
     * @param {Event} e - 文件选择事件
     */
    handleShoeFileSelect(e) {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            this.handleShoeFiles(files);
        }
    }
    
    /**
     * 处理多个鞋模文件
     * 
     * 验证文件格式和大小，支持批量上传
     * 
     * @param {File[]} files - 文件对象数组
     */
    handleShoeFiles(files) {
        // ==================== 文件验证 ====================
        // 验证所有文件
        const validFiles = [];
        const errors = [];
        
        let hasStlFiles = false;
        
        for (let file of files) {
            // 检查文件格式 - 支持.3dm和.stl
            const fileName = file.name.toLowerCase();
            if (!fileName.endsWith('.3dm') && !fileName.endsWith('.stl')) {
                errors.push(`${file.name}: 只支持.3dm和.stl格式`);
                continue;
            }
            
            // 检测是否有STL文件
            if (fileName.endsWith('.stl')) {
                hasStlFiles = true;
            }
            
            // 检查文件大小
            if (file.size > CONFIG.UPLOAD_MAX_SIZE) {
                errors.push(`${file.name}: 文件过大 (${Utils.formatFileSize(file.size)})`);
                continue;
            }
            
            validFiles.push(file);
        }
        
        // 显示错误
        if (errors.length > 0) {
            Utils.showNotification(`文件验证失败:\n${errors.join('\n')}`, 'error');
        }
        
        if (validFiles.length === 0) {
            return;
        }
        
        // 存储选中的文件
        this.selectedShoeFiles = validFiles;
        
        // 显示文件列表
        this.displayFileList(validFiles);
        $('#shoe-file-info').removeClass('d-none');
        $('#confirm-shoe-upload').prop('disabled', false);
        
        // 显示转换提示（如果有STL文件）
        if (hasStlFiles) {
            $('#format-conversion-notice').removeClass('d-none');
        } else {
            $('#format-conversion-notice').addClass('d-none');
        }
        
        // 更新按钮文本
        if (validFiles.length > 1) {
            $('#confirm-shoe-upload').text(`上传 ${validFiles.length} 个文件`);
        } else {
            $('#confirm-shoe-upload').text('确认上传');
        }
    }
    
    /**
     * 显示文件列表
     * 
     * 在文件上传界面显示已选择的文件列表，包括文件名、大小和操作按钮
     * 
     * @param {File[]} files - 文件对象数组
     */
    displayFileList(files) {
        // ==================== 生成文件列表HTML ====================
        // 为每个文件创建列表项，包含文件名、大小和删除按钮
        const fileListHtml = files.map((file, index) => `
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                    <strong>${file.name}</strong>
                    <br>
                    <small class="text-muted">${Utils.formatFileSize(file.size)}</small>
                </div>
                <div>
                    <span class="badge bg-warning" id="file-status-${index}">待上传</span>
                    <button class="btn btn-sm btn-outline-danger ms-2" onclick="matchingApp.removeFile(${index})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `).join('');
        
        // ==================== 更新UI ====================
        // 更新文件列表和文件计数
        $('#shoe-file-list').html(fileListHtml);
        $('#file-count-badge').text(files.length);
    }
    
    /**
     * 移除文件
     * 
     * 从已选择的文件列表中移除指定索引的文件
     * 
     * @param {number} index - 要移除的文件索引
     */
    removeFile(index) {
        if (this.selectedShoeFiles && index < this.selectedShoeFiles.length) {
            // ==================== 移除文件 ====================
            // 从数组中移除指定文件
            this.selectedShoeFiles.splice(index, 1);
            
            if (this.selectedShoeFiles.length === 0) {
                // ==================== 清空状态 ====================
                // 如果没有文件了，隐藏文件信息区域
                $('#shoe-file-info').addClass('d-none');
                $('#confirm-shoe-upload').prop('disabled', true);
            } else {
                // ==================== 更新显示 ====================
                // 重新显示文件列表
                this.displayFileList(this.selectedShoeFiles);
                $('#confirm-shoe-upload').text(
                    this.selectedShoeFiles.length > 1 ? 
                    `上传 ${this.selectedShoeFiles.length} 个文件` : 
                    '确认上传'
                );
            }
        }
    }
    
    handleShoeFile(file) {
        // 兼容单文件处理
        this.handleShoeFiles([file]);
    }
    
    async uploadShoeFile() {
        const files = this.selectedShoeFiles || [this.selectedShoeFile];
        if (!files || files.length === 0) {
            Utils.showNotification('请先选择文件', 'warning');
            return;
        }
        
        try {
            $('#confirm-shoe-upload').prop('disabled', true);
            $('#shoe-progress').show();
            
            const uploadedShoes = [];
            const totalFiles = files.length;
            
            // 批量上传文件
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                
                // 更新当前文件状态
                $(`#file-status-${i}`).removeClass().addClass('badge bg-info')
                    .html('<i class="fas fa-spinner fa-spin me-1"></i>上传中');
                
                // 更新总进度
                const progress = Math.round((i / totalFiles) * 100);
                $('.progress-bar').css('width', `${progress}%`).text(`${progress}%`);
                
                try {
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('name', file.name.replace('.3dm', ''));
                    
                    const response = await fetch('/api/shoes/upload/', {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                                          Utils.getCookie('csrftoken') || ''
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        $(`#file-status-${i}`).removeClass().addClass('badge bg-success')
                            .html('<i class="fas fa-check me-1"></i>成功');
                        uploadedShoes.push(data.data);
                    } else {
                        throw new Error(data.message || '上传失败');
                    }
                    
                } catch (error) {
                    $(`#file-status-${i}`).removeClass().addClass('badge bg-danger')
                        .html('<i class="fas fa-times me-1"></i>失败');
                    console.error(`文件 ${file.name} 上传失败:`, error);
                }
            }
            
            // 完成进度
            $('.progress-bar').css('width', '100%').text('100%');
            
            if (uploadedShoes.length > 0) {
                // ==================== 存储上传的鞋模列表 ====================
                // 存储上传的鞋模列表
                this.uploadedShoeModels = uploadedShoes;
                
                // ==================== 重置队列状态 ====================
                // 重置队列状态
                this.resetQueue();
                
                // ==================== 处理单个和批量鞋模 ====================
                // 如果只有一个文件，设置为当前鞋模
                if (uploadedShoes.length === 1) {
                    this.currentShoeModel = uploadedShoes[0];
                } else {
                    // 批量上传时，清空当前鞋模，让界面显示批量信息
                    this.currentShoeModel = null;
                }
                
                // ==================== 更新鞋模显示 ====================
                // 更新鞋模显示信息（支持单个和批量显示）
                this.updateShoeModelDisplay();
                
                // ==================== 关闭Modal ====================
                // 关闭Modal
                $('#shoeUploadModal').modal('hide');
                
                // ==================== 显示成功通知 ====================
                if (uploadedShoes.length === 1) {
                    Utils.showNotification('鞋模上传成功！', 'success');
                } else {
                    Utils.showNotification(`成功上传 ${uploadedShoes.length} 个鞋模文件！`, 'success');
                    // 不在这里显示批量匹配选项，等用户点击匹配按钮时再显示
                }
                
                // ==================== 更新匹配按钮状态 ====================
                // 更新匹配按钮状态
                this.updateMatchingButton();
            } else {
                throw new Error('所有文件上传失败');
            }
            
        } catch (error) {
            $('#shoe-status').removeClass().addClass('badge bg-danger').html('<i class="fas fa-times me-1"></i>上传失败');
            Utils.showNotification('上传失败: ' + error.message, 'error');
        } finally {
            $('#confirm-shoe-upload').prop('disabled', false);
            $('#shoe-progress').hide();
        }
    }
    
    /**
     * 显示批量匹配选项Modal
     * 
     * 当用户上传了多个鞋模文件时，提供批量匹配或单独匹配的选择
     */
    showBatchMatchingOptions() {
        // ==================== 构建Modal HTML ====================
        // 显示批量匹配选项
        const modalHtml = `
            <div class="modal fade" id="batchMatchingModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-layer-group me-2"></i>批量匹配选项
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i>
                                您已上传 <strong>${this.uploadedShoeModels.length}</strong> 个鞋模文件，可以选择批量匹配或单独匹配。
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-body text-center">
                                            <i class="fas fa-rocket fa-3x text-primary mb-3"></i>
                                            <h6>批量匹配</h6>
                                            <p class="text-muted small">
                                                依次匹配所有鞋模，生成统一的匹配报告
                                            </p>
                                            <button class="btn btn-primary" onclick="matchingApp.startQueueMatching()">
                                                开始队列匹配
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-body text-center">
                                            <i class="fas fa-mouse-pointer fa-3x text-secondary mb-3"></i>
                                            <h6>单独选择</h6>
                                            <p class="text-muted small">
                                                从列表中选择一个鞋模进行匹配
                                            </p>
                                            <button class="btn btn-outline-secondary" onclick="matchingApp.showShoeSelection()">
                                                选择鞋模
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 移除已存在的modal
        $('#batchMatchingModal').remove();
        $('body').append(modalHtml);
        $('#batchMatchingModal').modal('show');
    }
    
    /**
     * 开始队列匹配
     * 
     * 启动批量匹配流程，依次处理队列中的所有鞋模文件
     */
    async startQueueMatching() {
        // ==================== 验证队列数据 ====================
        // 检查是否有可用的鞋模文件
        if (!this.uploadedShoeModels || this.uploadedShoeModels.length === 0) {
            Utils.showNotification('没有可用的鞋模文件', 'error');
            return;
        }
        
        // 获取选中的分类
        const selectedCategories = this.selectedCategories;
        if (selectedCategories.length === 0) {
            Utils.showNotification('请先选择粗胚分类', 'warning');
            return;
        }
        
        // 关闭选择modal
        $('#batchMatchingModal').modal('hide');
        
        // 初始化队列
        this.queuedShoeModels = [...this.uploadedShoeModels];
        this.currentQueueIndex = 0;
        this.completedMatches = [];
        this.isQueueProcessing = true;
        
        console.log('开始队列匹配:', this.queuedShoeModels.length, '个鞋模');
        
        // 显示队列进度
        this.displayQueueProgress();
        
        // 开始处理第一个鞋模
        this.processNextInQueue();
        
        Utils.showNotification(`队列匹配已启动，将依次匹配 ${this.queuedShoeModels.length} 个鞋模`, 'success');
    }
    
    async processNextInQueue() {
        if (!this.isQueueProcessing || this.currentQueueIndex >= this.queuedShoeModels.length) {
            // 队列处理完成
            this.handleQueueComplete();
            return;
        }
        
        const currentShoe = this.queuedShoeModels[this.currentQueueIndex];
        console.log(`处理队列中的鞋模 ${this.currentQueueIndex + 1}/${this.queuedShoeModels.length}:`, currentShoe.name);
        
        // 设置当前鞋模
        this.currentShoeModel = currentShoe;
        
        // 更新队列进度显示
        this.updateQueueProgress(this.currentQueueIndex, currentShoe.name);
        
        try {
            // 确保有选中的分类
            const categoryIds = this.selectedCategories && this.selectedCategories.length > 0 ? 
                this.selectedCategories : 
                (this.categoryManager ? this.categoryManager.getSelectedCategoryIds() : []);
            
            if (!categoryIds || categoryIds.length === 0) {
                throw new Error('未选择粗胚分类');
            }
            
            // 启动单个匹配任务
            const params = {
                shoe_model_id: currentShoe.id,
                category_ids: categoryIds,
                ...this.getMatchingParams()
            };
            
            console.log('队列匹配参数:', params);
            
            const response = await Utils.apiRequest('/api/matching/start/', {
                method: 'POST',
                body: JSON.stringify(params)
            });
            
            if (response.success) {
                this.currentTask = response.data;
                this.startPolling(this.currentTask);
            } else {
                throw new Error(response.message || '启动匹配失败');
            }
            
        } catch (error) {
            console.error(`鞋模 ${currentShoe.name} 匹配启动失败:`, error);
            
            // 记录失败的匹配
            this.completedMatches.push({
                shoe: currentShoe,
                status: 'failed',
                error: error.message,
                index: this.currentQueueIndex
            });
            
            // 继续处理下一个
            this.currentQueueIndex++;
            setTimeout(() => this.processNextInQueue(), 1000);
        }
    }
    
    /**
     * 处理队列任务完成
     * 
     * 当队列中的某个匹配任务完成时，加载结果并继续下一个任务
     */
    async handleQueueTaskComplete(currentTask) {
        try {
            // ==================== 加载任务结果 ====================
            // 加载当前任务结果
            const response = await Utils.apiRequest(`/api/matching/${currentTask.task_id}/result/`);
            
            if (response.success) {
                const currentShoe = this.queuedShoeModels[this.currentQueueIndex];
                
                // 将结果添加到完成列表
                this.addMatchToResults(currentShoe, response.data, this.currentQueueIndex);
                
                console.log(`鞋模 ${currentShoe.name} 匹配完成`);
            }
            
        } catch (error) {
            console.error('获取队列任务结果失败:', error);
        }
        
        // ==================== 继续下一个任务 ====================
        // 继续下一个鞋模
        this.currentQueueIndex++;
        setTimeout(() => this.processNextInQueue(), 1000);
    }
    
    async handleQueueTaskFailed() {
        const currentShoe = this.queuedShoeModels[this.currentQueueIndex];
        
        // 记录失败的匹配
        this.completedMatches.push({
            shoe: currentShoe,
            status: 'failed',
            error: '匹配任务失败',
            index: this.currentQueueIndex
        });
        
        console.log(`鞋模 ${currentShoe.name} 匹配失败`);
        
        // 继续下一个鞋模
        this.currentQueueIndex++;
        setTimeout(() => this.processNextInQueue(), 1000);
    }
    
    addMatchToResults(shoe, resultData, index) {
        const matchResult = {
            shoe: shoe,
            status: 'completed',
            taskId: resultData.task_id,
            results: resultData.results,
            summary: resultData.summary,
            bestMatch: resultData.results && resultData.results.length > 0 ? resultData.results[0] : null,
            index: index,
            completedAt: new Date()
        };
        
        this.completedMatches.push(matchResult);
        
        // 更新队列结果显示
        this.updateQueueResultsDisplay();
    }
    
    handleQueueComplete() {
        this.isQueueProcessing = false;
        this.stopPolling();
        
        console.log('队列匹配完成，总共完成:', this.completedMatches.length);
        
        // 显示最终结果
        this.displayQueueResults();
        
        const successCount = this.completedMatches.filter(m => m.status === 'completed').length;
        const totalCount = this.queuedShoeModels.length;
        
        Utils.showNotification(`队列匹配完成！成功匹配 ${successCount}/${totalCount} 个鞋模`, 'success');
    }
    
    displayQueueProgress() {
        // 切换到匹配状态显示
        $('#default-state').addClass('d-none');
        $('#results-container').addClass('d-none');
        $('#matching-status').removeClass('d-none');
        
        // 更新状态标题
        $('#status-message').text('正在初始化队列匹配...');
        $('#progress-bar').css('width', '0%').attr('aria-valuenow', 0);
    }
    
    updateQueueProgress(currentIndex, currentShoeName) {
        const totalShoes = this.queuedShoeModels.length;
        const overallProgress = Math.round((currentIndex / totalShoes) * 100);
        
        // 更新整体进度
        $('#progress-bar').css('width', `${overallProgress}%`).attr('aria-valuenow', overallProgress);
        
        // 更新状态消息
        $('#status-message').html(`
            正在匹配鞋模 ${currentIndex + 1}/${totalShoes}: <strong>${currentShoeName}</strong>
            <br><small class="text-muted">已完成: ${this.completedMatches.length} 个</small>
        `);
    }
    
    updateQueueResultsDisplay() {
        // 在匹配进行中也显示已完成的结果
        if (this.completedMatches.length > 0) {
            // 在状态区域下方显示已完成的结果概览
            let resultsHtml = `
                <div class="mt-4">
                    <h6><i class="fas fa-check-circle text-success me-2"></i>已完成的匹配 (${this.completedMatches.length})</h6>
                    <div class="row">
            `;
            
            this.completedMatches.forEach((match, index) => {
                const bestMatch = match.bestMatch;
                const statusIcon = match.status === 'completed' ? 'fa-check text-success' : 'fa-times text-danger';
                
                resultsHtml += `
                    <div class="col-md-6 mb-2">
                        <div class="card card-sm">
                            <div class="card-body p-2">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <strong>${match.shoe.name}</strong>
                                        <br><small class="text-muted">
                                            ${bestMatch ? 
                                                `最佳: ${bestMatch.blank_name} (${(bestMatch.inside_ratio * 100).toFixed(1)}%)` : 
                                                '无匹配结果'
                                            }
                                        </small>
                                    </div>
                                    <div>
                                        <i class="fas ${statusIcon}"></i>
                                        ${match.status === 'completed' ? 
                                            `<button class="btn btn-sm btn-outline-primary ms-2" onclick="matchingApp.showQueueResultDetail(${index})">
                                                <i class="fas fa-eye"></i>
                                            </button>` : ''
                                        }
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            resultsHtml += `
                    </div>
                </div>
            `;
            
            // 在匹配状态下方显示
            if ($('#queue-results-preview').length === 0) {
                $('#matching-status').after('<div id="queue-results-preview"></div>');
            }
            $('#queue-results-preview').html(resultsHtml);
        }
    }
    
    displayQueueResults() {
        // 隐藏匹配状态，显示最终结果
        $('#matching-status').addClass('d-none');
        $('#queue-results-preview').remove();
        $('#results-container').removeClass('d-none');
        $('#result-actions').removeClass('d-none');
        
        // 更新结果标题
        $('#results-count').text(`${this.completedMatches.length} 个鞋模`);
        $('#processing-time').text('--');
        
        // 显示队列结果汇总
        this.showQueueResultsSummary();
        
        // 显示所有匹配结果
        this.renderQueueResultsTable();
    }
    
    showQueueResultsSummary() {
        const totalMatches = this.completedMatches.length;
        const successfulMatches = this.completedMatches.filter(m => m.status === 'completed');
        const failedMatches = this.completedMatches.filter(m => m.status === 'failed');
        
        // 计算总的匹配统计
        let totalCandidates = 0;
        let totalPassed = 0;
        
        successfulMatches.forEach(match => {
            if (match.summary) {
                totalCandidates += match.summary.total_candidates || 0;
                totalPassed += match.summary.passed_p15 || 0;
            }
        });
        
        const summaryHtml = `
            <div class="row mb-3">
                <div class="col-md-3 text-center">
                    <div class="border rounded p-2">
                        <h6 class="text-primary mb-1">${totalMatches}</h6>
                        <small class="text-muted">总鞋模数</small>
                    </div>
                </div>
                <div class="col-md-3 text-center">
                    <div class="border rounded p-2">
                        <h6 class="text-success mb-1">${successfulMatches.length}</h6>
                        <small class="text-muted">成功匹配</small>
                    </div>
                </div>
                <div class="col-md-3 text-center">
                    <div class="border rounded p-2">
                        <h6 class="text-warning mb-1">${totalCandidates}</h6>
                        <small class="text-muted">总候选数</small>
                    </div>
                </div>
                <div class="col-md-3 text-center">
                    <div class="border rounded p-2">
                        <h6 class="text-info mb-1">${totalPassed}</h6>
                        <small class="text-muted">通过总数</small>
                    </div>
                </div>
            </div>
        `;
        
        // 在结果表格前插入汇总信息
        if ($('#results-summary').length === 0) {
            $('#results-table').before('<div id="results-summary"></div>');
        }
        $('#results-summary').html(summaryHtml);
    }
    
    renderQueueResultsTable() {
        const tbody = $('#results-table tbody');
        tbody.empty();
        
        this.completedMatches.forEach((match, index) => {
            const shoe = match.shoe;
            const bestMatch = match.bestMatch;
            const statusBadge = match.status === 'completed' ? 
                '<span class="badge status-pass"><i class="fas fa-check"></i> 完成</span>' :
                '<span class="badge status-fail"><i class="fas fa-times"></i> 失败</span>';
            
            let coverageRate = 0;
            let volumeRatio = '--';
            let p15Clearance = '--';
            
            if (bestMatch) {
                // 使用实际的覆盖率
                if (bestMatch.inside_ratio !== undefined && bestMatch.inside_ratio !== null) {
                    coverageRate = bestMatch.inside_ratio * 100;
                } else if (bestMatch.p15_clearance !== undefined) {
                    // 估算覆盖率
                    if (bestMatch.p15_clearance <= 2.0) {
                        coverageRate = 95 - (bestMatch.p15_clearance * 10);
                    } else if (bestMatch.p15_clearance <= 5.0) {
                        coverageRate = 75 - ((bestMatch.p15_clearance - 2) * 10);
                    } else {
                        coverageRate = Math.max(0, 45 - ((bestMatch.p15_clearance - 5) * 2));
                    }
                    coverageRate = Math.max(0, Math.min(100, coverageRate));
                }
                
                volumeRatio = bestMatch.volume_ratio ? bestMatch.volume_ratio.toFixed(2) + 'x' : '--';
                p15Clearance = bestMatch.p15_clearance ? bestMatch.p15_clearance.toFixed(2) + 'mm' : '--';
            }
            
            const row = $(`
                <tr data-queue-index="${index}">
                    <td>
                        <strong>${shoe.name}</strong>
                        <br><small class="text-muted">${bestMatch ? bestMatch.blank_name : '无匹配'}</small>
                    </td>
                    <td>
                        <span class="badge bg-info">${coverageRate.toFixed(1)}%</span>
                    </td>
                    <td>
                        <span class="badge bg-success">${volumeRatio}</span>
                    </td>
                    <td>
                        <span class="badge bg-warning text-dark">${p15Clearance}</span>
                    </td>
                    <td>${statusBadge}</td>
                    <td>
                        ${match.status === 'completed' ? 
                            `<button class="btn btn-sm btn-outline-primary" onclick="matchingApp.showQueueResultDetail(${index})">
                                <i class="fas fa-eye"></i> 详情
                            </button>` : 
                            '<span class="text-muted">无详情</span>'
                        }
                    </td>
                </tr>
            `);
            tbody.append(row);
        });
    }
    
    showQueueResultDetail(queueIndex) {
        if (!this.completedMatches || queueIndex >= this.completedMatches.length) {
            Utils.showNotification('结果数据不存在', 'error');
            return;
        }
        
        const match = this.completedMatches[queueIndex];
        if (match.status !== 'completed' || !match.results) {
            Utils.showNotification('该匹配无可用结果', 'warning');
            return;
        }
        
        // 设置当前结果数据
        this.currentResults = match.results;
        this.currentSummary = match.summary;
        this.currentTask = { task_id: match.taskId };
        this.currentShoeModel = match.shoe;
        
        // 显示该鞋模的完整匹配结果
        this.showQueueShoeResults(match);
    }
    
    showQueueShoeResults(match) {
        // 隐藏其他区域，显示结果容器
        $('#matching-status').addClass('d-none');
        $('#queue-results-preview').addClass('d-none');
        $('#results-container').removeClass('d-none');
        $('#result-actions').removeClass('d-none');
        
        // 更新结果标题，显示当前鞋模信息
        $('#results-count').text(`${match.results.length} 个匹配结果`);
        $('#processing-time').text(match.summary.processing_time ? match.summary.processing_time.toFixed(2) + '秒' : '--');
        
        // 添加鞋模信息到标题
        const resultsTitle = $('#results-container .card-header h5');
        resultsTitle.html(`
            <i class="fas fa-chart-line me-2"></i>匹配结果 - ${match.shoe.name}
            <small class="text-muted ms-2">(${match.results.length} 个候选)</small>
        `);
        
        // 显示该鞋模的汇总信息
        this.showResultsSummary(match.summary);
        
        // 显示该鞋模的所有匹配结果
        this.renderResultsTable(match.results);
        
        // 添加返回按钮
        if ($('#back-to-queue-btn').length === 0) {
            $('#result-actions').prepend(`
                <button class="btn btn-sm btn-outline-secondary me-2" id="back-to-queue-btn">
                    <i class="fas fa-arrow-left me-1"></i>返回队列结果
                </button>
            `);
            
            $('#back-to-queue-btn').on('click', () => {
                this.displayQueueResults();
                $('#back-to-queue-btn').remove();
            });
        }
        
        Utils.showNotification(`显示鞋模 ${match.shoe.name} 的完整匹配结果`, 'info');
    }
    
    resetQueue() {
        this.queuedShoeModels = [];
        this.currentQueueIndex = -1;
        this.completedMatches = [];
        this.isQueueProcessing = false;
        $('#queue-results-preview').remove();
    }
    
    /**
     * 显示批量匹配进度
     * 
     * 切换到批量匹配状态界面，显示进度和当前步骤
     */
    showBatchMatchingProgress() {
        // ==================== 切换UI状态 ====================
        // 切换到匹配状态显示
        $('#default-state').addClass('d-none');
        $('#matching-status').removeClass('d-none');
        
        // ==================== 更新状态信息 ====================
        // 更新状态显示
        $('#status-title').html('<i class="fas fa-layer-group me-2"></i>批量匹配进行中');
        $('#current-step').text('准备批量匹配...');
        
        // ==================== 开始状态轮询 ====================
        // 开始轮询状态
        this.pollBatchMatchingStatus();
    }
    
    /**
     * 轮询批量匹配状态
     * 
     * 定期检查批量匹配任务的执行状态，更新进度显示
     */
    async pollBatchMatchingStatus() {
        if (!this.currentBatchTask) return;
        
        try {
            // ==================== 获取状态信息 ====================
            // 请求批量匹配任务状态
            const response = await Utils.apiRequest(`/api/matching/batch/${this.currentBatchTask.batch_id}/status/`);
            
            if (response.success) {
                const data = response.data;
                
                // ==================== 更新进度显示 ====================
                // 更新进度
                $('#progress-bar').css('width', `${data.progress}%`).text(`${data.progress}%`);
                $('#current-step').text(data.current_step);
                
                // 显示当前处理的鞋模
                if (data.current_shoe_index >= 0 && data.shoe_models_data) {
                    const currentShoe = data.shoe_models_data[data.current_shoe_index];
                    if (currentShoe) {
                        $('#current-step').html(`
                            ${data.current_step}<br>
                            <small class="text-muted">正在处理: ${currentShoe.name}</small>
                        `);
                    }
                }
                
                if (data.status === 'completed') {
                    // 批量匹配完成
                    this.handleBatchMatchingComplete(data);
                } else if (data.status === 'failed') {
                    // 批量匹配失败
                    this.showError('批量匹配失败: ' + data.current_step);
                } else {
                    // 继续轮询
                    setTimeout(() => this.pollBatchMatchingStatus(), 2000);
                }
            }
            
        } catch (error) {
            console.error('获取批量匹配状态失败:', error);
            setTimeout(() => this.pollBatchMatchingStatus(), 5000);
        }
    }
    
    async handleBatchMatchingComplete(batchData) {
        try {
            // 获取批量匹配结果
            const response = await Utils.apiRequest(`/api/matching/batch/${batchData.batch_id}/result/`);
            
            if (response.success) {
                this.currentBatchResults = response.data;
                this.displayBatchMatchingResults();
                Utils.showNotification(`批量匹配完成！成功匹配 ${batchData.completed_count}/${batchData.total_shoe_count} 个鞋模`, 'success');
            } else {
                throw new Error(response.message || '获取批量结果失败');
            }
            
        } catch (error) {
            console.error('获取批量匹配结果失败:', error);
            this.showError('获取批量匹配结果失败: ' + error.message);
        }
    }
    
    displayBatchMatchingResults() {
        if (!this.currentBatchResults) return;
        
        // 切换到结果显示
        $('#matching-status').addClass('d-none');
        $('#matching-results').removeClass('d-none');
        
        // 更新结果标题
        $('#results-title').html(`
            <i class="fas fa-layer-group me-2"></i>批量匹配结果
            <span class="badge bg-primary ms-2">${this.currentBatchResults.summary.completed_shoes} 个鞋模</span>
        `);
        
        // 显示汇总信息
        const summary = this.currentBatchResults.summary;
        $('#results-summary').html(`
            <div class="row">
                <div class="col-md-3">
                    <div class="text-center">
                        <h4 class="text-primary">${summary.total_shoes}</h4>
                        <small class="text-muted">总鞋模数</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="text-center">
                        <h4 class="text-success">${summary.completed_shoes}</h4>
                        <small class="text-muted">成功匹配</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="text-center">
                        <h4 class="text-info">${summary.total_results}</h4>
                        <small class="text-muted">总匹配结果</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="text-center">
                        <h4 class="text-warning">${(this.currentBatchResults.total_processing_time / 60).toFixed(1)}</h4>
                        <small class="text-muted">处理时间(分钟)</small>
                    </div>
                </div>
            </div>
        `);
        
        // 显示所有结果
        this.renderBatchResultsTable();
    }
    
    /**
     * 渲染批量匹配结果表格
     * 
     * 将批量匹配的所有结果渲染为HTML表格
     */
    renderBatchResultsTable() {
        const results = this.currentBatchResults.all_results || [];
        
        // ==================== 生成表格行 ====================
        // 为每个结果生成表格行HTML
        const tableHtml = results.map((result, index) => {
            // ==================== 计算覆盖率 ====================
            // 计算覆盖率
            let coverageRate = 0;
            if (result.inside_ratio !== undefined && result.inside_ratio !== null) {
                coverageRate = result.inside_ratio * 100;
            } else {
                const p15 = result.p15_clearance || 0;
                if (p15 < 0) {
                    coverageRate = Math.min(99, 95 + Math.abs(p15) * 2);
                } else if (p15 < 2) {
                    coverageRate = Math.max(80, 95 - p15 * 5);
                } else {
                    coverageRate = Math.max(0, 80 - (p15 - 2) * 10);
                }
            }
            
            const statusBadge = this.getMatchingStatusBadge(result);
            
            return `
                <tr>
                    <td>${index + 1}</td>
                    <td>
                        <strong>${result.shoe_model_name}</strong>
                        <br>
                        <small class="text-muted">任务: ${result.task_id}</small>
                    </td>
                    <td>${result.blank_name}</td>
                    <td>
                        <span class="badge bg-info">${coverageRate.toFixed(1)}%</span>
                    </td>
                    <td>
                        <span class="badge bg-success">${result.p15_clearance?.toFixed(2) || 0}mm</span>
                    </td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="matchingApp.showBatchResultDetail(${index})">
                            <i class="fas fa-eye"></i> 详情
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        
        $('#results-table tbody').html(tableHtml);
        
        // 更新结果统计
        $('#results-count').text(`找到 ${results.length} 个匹配结果`);
    }
    
    showBatchResultDetail(index) {
        if (!this.currentBatchResults || !this.currentBatchResults.all_results[index]) {
            Utils.showNotification('结果数据不存在', 'error');
            return;
        }
        
        const result = this.currentBatchResults.all_results[index];
        
        // 更新结果详情Modal
        this.updateResultDetailModal(result, index);
        
        // 显示Modal
        $('#resultDetailModal').modal('show');
        
        // 加载热力图（如果有对应的单个任务）
        if (result.task_id && index < 4) {
            this.loadHeatmapWithStatus(result.task_id, 0); // 使用该鞋模的第一个结果
        }
    }
    
    /**
     * 更新鞋模显示信息
     * 
     * 在界面上显示当前选中鞋模或批量鞋模的详细信息
     */
    updateShoeModelDisplay() {
        // ==================== 检查鞋模数据 ====================
        // 优先显示当前选中的鞋模，如果没有则显示批量鞋模信息
        if (this.currentShoeModel) {
            // ==================== 显示单个鞋模信息 ====================
            // 显示鞋模名称、体积和文件大小
            $('#shoe-model-name').text(this.currentShoeModel.name);
            $('#shoe-model-volume').text(`体积: ${this.currentShoeModel.volume?.toFixed(0) || '--'} mm³`);
            $('#shoe-model-size').text(`大小: ${this.currentShoeModel.file_size_mb}MB`);
            $('#shoe-model-info').removeClass('d-none');
            
        } else if (this.uploadedShoeModels && this.uploadedShoeModels.length > 0) {
            // ==================== 显示批量鞋模信息 ====================
            // 显示批量鞋模的汇总信息
            const totalSize = this.uploadedShoeModels.reduce((sum, shoe) => sum + (shoe.file_size_mb || 0), 0);
            const totalVolume = this.uploadedShoeModels.reduce((sum, shoe) => sum + (shoe.volume || 0), 0);
            
            $('#shoe-model-name').text(`批量鞋模 (${this.uploadedShoeModels.length} 个文件)`);
            $('#shoe-model-volume').text(`总体积: ${totalVolume.toFixed(0)} mm³`);
            $('#shoe-model-size').text(`总大小: ${totalSize.toFixed(1)}MB`);
            $('#shoe-model-info').removeClass('d-none');
            
            // ==================== 显示批量鞋模列表 ====================
            // 创建批量鞋模列表显示
            this.displayBatchShoeModels();
            
        } else {
            // ==================== 隐藏鞋模信息 ====================
            // 没有鞋模时隐藏信息区域
            $('#shoe-model-info').addClass('d-none');
        }
        
        // ==================== 更新匹配按钮 ====================
        // 更新匹配按钮状态
        this.updateMatchingButton();
    }
    
    /**
     * 显示批量鞋模列表
     * 
     * 在界面上显示批量上传的鞋模文件列表
     */
    displayBatchShoeModels() {
        if (!this.uploadedShoeModels || this.uploadedShoeModels.length <= 1) return;
        
        // ==================== 创建批量鞋模列表HTML ====================
        // 生成批量鞋模列表的HTML
        const shoeListHtml = `
            <div class="mt-2">
                <small class="text-muted">已上传的鞋模文件：</small>
                <div class="mt-1">
                    ${this.uploadedShoeModels.map((shoe, index) => `
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <div class="flex-grow-1">
                                <small class="text-primary">${shoe.name}</small>
                                <br>
                                <small class="text-muted">${shoe.file_size_mb}MB</small>
                            </div>
                            <div>
                                <button class="btn btn-sm btn-outline-info" id="preview-btn-${shoe.id}" onclick="matchingApp.previewShoeModelById(${shoe.id})">
                                    <i class="fas fa-eye"></i>
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        // ==================== 更新界面显示 ====================
        // 在鞋模信息区域添加批量列表
        if ($('#batch-shoe-list').length === 0) {
            $('#shoe-model-info').append('<div id="batch-shoe-list"></div>');
        }
        $('#batch-shoe-list').html(shoeListHtml);
    }
    
    // /**
    //  * 选择鞋模
    //  * 
    //  * 从批量鞋模中选择一个作为当前鞋模
    //  * 
    //  * @param {number} index - 鞋模在批量列表中的索引
    //  */
    // selectShoeModel(index) {
    //     if (this.uploadedShoeModels && this.uploadedShoeModels[index]) {
    //         // ==================== 设置当前鞋模 ====================
    //         // 将选中的鞋模设置为当前鞋模
    //         this.currentShoeModel = this.uploadedShoeModels[index];
            
    //         // ==================== 更新显示 ====================
    //         // 重新更新鞋模显示
    //         this.updateShoeModelDisplay();
            
    //         // ==================== 显示确认信息 ====================
    //         // 显示选择确认信息
    //         Utils.showNotification(`已选择鞋模: ${this.currentShoeModel.name}`, 'success');
    //     }
    // }
    
    /**
     * 通过ID预览鞋模
     * 
     * 根据鞋模ID预览指定的鞋模3D模型，包含加载状态和动画效果
     * 
     * @param {number} shoeId - 鞋模ID
     */
    async previewShoeModelById(shoeId) {
        const previewBtn = $(`#preview-btn-${shoeId}`);
        const originalContent = previewBtn.html();
        
        try {
            // ==================== 显示加载状态 ====================
            // 禁用按钮并显示加载动画
            previewBtn.prop('disabled', true);
            previewBtn.html('<i class="fas fa-spinner fa-spin"></i>');
            
            // ==================== 检查Three.js预览可用性 ====================
            console.log(`准备预览鞋模 ID: ${shoeId}`);
            
            // 检查鞋模是否支持Three.js预览
            const statusResponse = await Utils.apiRequest(`/api/lod/shoe/${shoeId}/status/`);
            
            if (statusResponse.success && statusResponse.data && statusResponse.data.webgl_ready) {
                // ==================== 使用Three.js预览 ====================
                console.log('鞋模支持Three.js预览，跳转到新预览页面');
                
                // 更新按钮状态为预览完成
                if (previewBtn.length > 0) {
                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                }
                
                // 在新标签页中打开Three.js预览页面
                const previewUrl = `/api/three/shoe/${shoeId}/`;
                window.open(previewUrl, '_blank');
                
                Utils.showNotification('正在新标签页中打开3D预览...', 'success');
                
                // 1秒后恢复按钮原始状态
                setTimeout(() => {
                    if (previewBtn.length > 0) {
                previewBtn.prop('disabled', false);
                        previewBtn.html('<i class="fas fa-eye"></i>');
                    }
                }, 1000);
                
            } else if (statusResponse.success && statusResponse.data && statusResponse.data.has_3dm_file) {
                // ==================== 需要生成GLB文件 ====================
                console.log('鞋模暂不支持Three.js预览，尝试生成GLB文件...');
                
                // 更新按钮状态显示正在生成GLB
                previewBtn.html('<i class="fas fa-cogs fa-spin me-1"></i>生成GLB中...');
                
                Utils.showNotification('正在生成3D预览文件，请稍候...', 'info');
                
                try {
                    // 触发LOD处理
                    const processResponse = await Utils.apiRequest(`/api/lod/shoe/${shoeId}/process/`, {
                        method: 'POST'
                    });
                    
                    if (processResponse.success) {
                        console.log('LOD处理任务已启动，等待完成...');
                        previewBtn.html('<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中...');
                        
                        // 轮询检查处理状态（最多等待3分钟）
                        const maxAttempts = 36; // 3分钟，每5秒检查一次
                        let attempts = 0;
                        
                        const checkStatus = async () => {
                            attempts++;
                            if (attempts > maxAttempts) {
                                Utils.showNotification('预览文件生成时间较长，请稍后再试', 'warning');
                                return;
                            }
                            
                            const checkResponse = await Utils.apiRequest(`/api/lod/shoe/${shoeId}/status/`);
                            
                            if (checkResponse.success && checkResponse.data && checkResponse.data.webgl_ready) {
                                // GLB文件已准备好，更新按钮状态为完成
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                                }
                                
                                console.log('GLB文件生成完成，打开预览页面');
                                const previewUrl = `/api/three/shoe/${shoeId}/`;
                                window.open(previewUrl, '_blank');
                                Utils.showNotification('3D预览文件生成完成！', 'success');
                                
                                // 1秒后恢复按钮原始状态
                                setTimeout(() => {
                                    if (previewBtn.length > 0) {
                                        previewBtn.html('<i class="fas fa-eye me-1"></i>预览');
                                    }
                                }, 1000);
                                
                                return;
            } else {
                                // 继续等待，更新进度提示
                                const progress = Math.round((attempts / maxAttempts) * 100);
                                previewBtn.html(`<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中 ${progress}%`);
                                
                                // 5秒后再次检查
                                setTimeout(checkStatus, 5000);
                            }
                        };
                        
                        // 开始状态检查
                        setTimeout(checkStatus, 5000);
                        
                    } else {
                        throw new Error(processResponse.message || 'LOD处理启动失败');
                    }
                } catch (processError) {
                    console.error('启动LOD处理失败:', processError);
                    Utils.showNotification('生成3D预览文件失败: ' + processError.message, 'error');
                    // 回退到Plotly预览
                    throw new Error('LOD处理失败，使用Plotly预览');
                }
                
            } else {
                // ==================== 强制生成GLB文件 ====================
                console.log('鞋模没有GLB文件，强制生成GLB文件...');
                
                // 更新按钮状态显示正在生成GLB
                previewBtn.html('<i class="fas fa-cogs fa-spin me-1"></i>生成GLB中...');
                
                Utils.showNotification('鞋模文件需要处理，正在生成3D预览文件...', 'info');
                
                try {
                    // 触发LOD处理
                    const processResponse = await Utils.apiRequest(`/api/lod/shoe/${shoeId}/process/`, {
                        method: 'POST'
                    });
                    
                    if (processResponse.success) {
                        console.log('LOD处理任务已启动，等待完成...');
                        previewBtn.html('<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中...');
                        
                        // 轮询检查处理状态（最多等待5分钟）
                        const maxAttempts = 60; // 5分钟，每5秒检查一次
                        let attempts = 0;
                        
                        const checkStatus = async () => {
                            attempts++;
                            if (attempts > maxAttempts) {
                                Utils.showNotification('预览文件生成超时，请检查文件是否过大或稍后重试', 'error');
                                previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                                return;
                            }
                            
                            const checkResponse = await Utils.apiRequest(`/api/lod/shoe/${shoeId}/status/`);
                            
                            if (checkResponse.success && checkResponse.data && checkResponse.data.webgl_ready) {
                                // GLB文件已准备好，更新按钮状态为完成
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                                }
                                
                                console.log('GLB文件生成完成，打开预览页面');
                                const previewUrl = `/api/three/shoe/${shoeId}/`;
                                window.open(previewUrl, '_blank');
                                Utils.showNotification('3D预览文件生成完成！正在打开预览...', 'success');
                                
                                // 1秒后恢复按钮原始状态
                                setTimeout(() => {
                                    if (previewBtn.length > 0) {
                                        previewBtn.html('<i class="fas fa-eye me-1"></i>预览');
                                    }
                                }, 1000);
                                
                                return;
                            } else {
                                // 继续等待，更新进度提示
                                const progress = Math.round((attempts / maxAttempts) * 100);
                                previewBtn.html(`<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中 ${progress}%`);
                                
                                // 显示详细的处理状态
                                if (checkResponse.data && checkResponse.data.processing_status) {
                                    const status = checkResponse.data.processing_status;
                                    if (status === 'processing') {
                                        // 显示处理中状态
                                    } else if (status === 'failed') {
                                        Utils.showNotification('3D预览文件生成失败，请检查文件格式或稍后重试', 'error');
                                        previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                                        return;
                                    }
                                }
                                
                                // 5秒后再次检查
                                setTimeout(checkStatus, 5000);
                            }
                        };
                        
                        // 开始状态检查
                        setTimeout(checkStatus, 5000);
                        
                    } else {
                        throw new Error(processResponse.message || 'LOD处理启动失败');
                    }
                } catch (processError) {
                    console.error('启动LOD处理失败:', processError);
                    Utils.showNotification('生成3D预览文件失败: ' + processError.message, 'error');
                    previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                }
            }
            
        } catch (error) {
            // ==================== 错误处理 ====================
            console.error('预览加载失败:', error);
            Utils.showNotification('预览加载失败: ' + error.message, 'error');
        } finally {
            // ==================== 恢复按钮状态 ====================
            // 恢复按钮原始状态
            previewBtn.prop('disabled', false);
            previewBtn.html(originalContent);
        }
    }
    
    /**
     * 预览鞋模3D模型
     * 
     * 在3D预览模态框中显示当前鞋模的3D可视化，包含加载状态和动画效果
     */
    async previewShoeModel() {
        if (!this.currentShoeModel) return;
        
        // ==================== 查找预览按钮 ====================
        // 查找主要的预览按钮（可能在多个位置）
        const previewBtn = $('#preview-shoe-btn, .preview-shoe-btn, [onclick*="previewShoeModel"]').first();
        const originalContent = previewBtn.length > 0 ? previewBtn.html() : '';
        
        try {
            // ==================== 显示加载状态 ====================
            // 如果找到预览按钮，显示加载动画
            if (previewBtn.length > 0) {
                previewBtn.prop('disabled', true);
                previewBtn.html('<i class="fas fa-spinner fa-spin me-1"></i>生成中...');
            }
            
            // ==================== 检查Three.js预览可用性 ====================
            console.log(`准备预览当前鞋模 ID: ${this.currentShoeModel.id}`);
            
            // 检查鞋模是否支持Three.js预览
            const statusResponse = await Utils.apiRequest(`/api/lod/shoe/${this.currentShoeModel.id}/status/`);
            
            if (statusResponse.success && statusResponse.data && statusResponse.data.webgl_ready) {
                // ==================== 使用Three.js预览 ====================
                console.log('当前鞋模支持Three.js预览，跳转到新预览页面');
                
                // 更新按钮状态为预览完成
                if (previewBtn.length > 0) {
                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                }
                
                // 在新标签页中打开Three.js预览页面
                const previewUrl = `/api/three/shoe/${this.currentShoeModel.id}/`;
                window.open(previewUrl, '_blank');
                
                Utils.showNotification('正在新标签页中打开3D预览...', 'success');
                
                // 1秒后恢复按钮原始状态
                setTimeout(() => {
                if (previewBtn.length > 0) {
                    previewBtn.prop('disabled', false);
                        previewBtn.html('<i class="fas fa-eye me-1"></i>预览');
                    }
                }, 1000);
                
            } else if (statusResponse.success && statusResponse.data && statusResponse.data.has_3dm_file) {
                // ==================== 需要生成GLB文件 ====================
                console.log('当前鞋模暂不支持Three.js预览，尝试生成GLB文件...');
                
                // 更新按钮状态显示正在生成GLB
                if (previewBtn.length > 0) {
                    previewBtn.html('<i class="fas fa-cogs fa-spin me-1"></i>生成GLB中...');
                }
                
                Utils.showNotification('正在生成3D预览文件，请稍候...', 'info');
                
                try {
                    // 触发LOD处理
                    const processResponse = await Utils.apiRequest(`/api/lod/shoe/${this.currentShoeModel.id}/process/`, {
                        method: 'POST'
                    });
                    
                    if (processResponse.success) {
                        console.log('LOD处理任务已启动，等待完成...');
                        if (previewBtn.length > 0) {
                            previewBtn.html('<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中...');
                        }
                        
                        // 轮询检查处理状态（最多等待5分钟）
                        const maxAttempts = 60; // 5分钟，每5秒检查一次
                        let attempts = 0;
                        
                        const checkStatus = async () => {
                            attempts++;
                            if (attempts > maxAttempts) {
                                Utils.showNotification('预览文件生成超时，请检查文件是否过大或稍后重试', 'error');
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                                }
                                return;
                            }
                            
                            const checkResponse = await Utils.apiRequest(`/api/lod/shoe/${this.currentShoeModel.id}/status/`);
                            
                            if (checkResponse.success && checkResponse.data && checkResponse.data.webgl_ready) {
                                // GLB文件已准备好，更新按钮状态为完成
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                                }
                                
                                console.log('GLB文件生成完成，打开预览页面');
                                const previewUrl = `/api/three/shoe/${this.currentShoeModel.id}/`;
                                window.open(previewUrl, '_blank');
                                Utils.showNotification('3D预览文件生成完成！正在打开预览...', 'success');
                                
                                // 1秒后恢复按钮原始状态
                                setTimeout(() => {
                                    if (previewBtn.length > 0) {
                                        previewBtn.html('<i class="fas fa-eye me-1"></i>预览');
                                    }
                                }, 1000);
                                
                                return;
            } else {
                                // 继续等待，更新进度提示
                                const progress = Math.round((attempts / maxAttempts) * 100);
                                if (previewBtn.length > 0) {
                                    previewBtn.html(`<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中 ${progress}%`);
                                }
                                
                                // 显示详细的处理状态
                                if (checkResponse.data && checkResponse.data.processing_status) {
                                    const status = checkResponse.data.processing_status;
                                    if (status === 'processing') {
                                        // 显示处理中状态
                                    } else if (status === 'failed') {
                                        Utils.showNotification('3D预览文件生成失败，请检查文件格式或稍后重试', 'error');
                                        if (previewBtn.length > 0) {
                                            previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                                        }
                                        return;
                                    }
                                }
                                
                                // 5秒后再次检查
                                setTimeout(checkStatus, 5000);
                            }
                        };
                        
                        // 开始状态检查
                        setTimeout(checkStatus, 5000);
                        
                    } else {
                        throw new Error(processResponse.message || 'LOD处理启动失败');
                    }
                } catch (processError) {
                    console.error('启动LOD处理失败:', processError);
                    Utils.showNotification('生成3D预览文件失败: ' + processError.message, 'error');
                    if (previewBtn.length > 0) {
                        previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                    }
                }
                
            } else {
                // ==================== 强制生成GLB文件 ====================
                console.log('当前鞋模没有GLB文件，强制生成GLB文件...');
                
                // 更新按钮状态显示正在生成GLB
                if (previewBtn.length > 0) {
                    previewBtn.html('<i class="fas fa-cogs fa-spin me-1"></i>生成GLB中...');
                }
                
                Utils.showNotification('鞋模文件需要处理，正在生成3D预览文件...', 'info');
                
                try {
                    // 触发LOD处理
                    const processResponse = await Utils.apiRequest(`/api/lod/shoe/${this.currentShoeModel.id}/process/`, {
                        method: 'POST'
                    });
                    
                    if (processResponse.success) {
                        console.log('LOD处理任务已启动，等待完成...');
                        if (previewBtn.length > 0) {
                            previewBtn.html('<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中...');
                        }
                        
                        // 轮询检查处理状态（最多等待5分钟）
                        const maxAttempts = 60; // 5分钟，每5秒检查一次
                        let attempts = 0;
                        
                        const checkStatus = async () => {
                            attempts++;
                            if (attempts > maxAttempts) {
                                Utils.showNotification('预览文件生成超时，请检查文件是否过大或稍后重试', 'error');
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                                }
                                return;
                            }
                            
                            const checkResponse = await Utils.apiRequest(`/api/lod/shoe/${this.currentShoeModel.id}/status/`);
                            
                            if (checkResponse.success && checkResponse.data && checkResponse.data.webgl_ready) {
                                // GLB文件已准备好，更新按钮状态为完成
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                                }
                                
                                console.log('GLB文件生成完成，打开预览页面');
                                const previewUrl = `/api/three/shoe/${this.currentShoeModel.id}/`;
                                window.open(previewUrl, '_blank');
                                Utils.showNotification('3D预览文件生成完成！正在打开预览...', 'success');
                                
                                // 1秒后恢复按钮原始状态
                                setTimeout(() => {
                                    if (previewBtn.length > 0) {
                                        previewBtn.html('<i class="fas fa-eye me-1"></i>预览');
                                    }
                                }, 1000);
                                
                                return;
                            } else {
                                // 继续等待，更新进度提示
                                const progress = Math.round((attempts / maxAttempts) * 100);
                                if (previewBtn.length > 0) {
                                    previewBtn.html(`<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中 ${progress}%`);
                                }
                                
                                // 显示详细的处理状态
                                if (checkResponse.data && checkResponse.data.processing_status) {
                                    const status = checkResponse.data.processing_status;
                                    if (status === 'processing') {
                                        // 显示处理中状态
                                    } else if (status === 'failed') {
                                        Utils.showNotification('3D预览文件生成失败，请检查文件格式或稍后重试', 'error');
                                        if (previewBtn.length > 0) {
                                            previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                                        }
                                        return;
                                    }
                                }
                                
                                // 5秒后再次检查
                                setTimeout(checkStatus, 5000);
                            }
                        };
                        
                        // 开始状态检查
                        setTimeout(checkStatus, 5000);
                        
                    } else {
                        throw new Error(processResponse.message || 'LOD处理启动失败');
                    }
                } catch (processError) {
                    console.error('启动LOD处理失败:', processError);
                    Utils.showNotification('生成3D预览文件失败: ' + processError.message, 'error');
                    if (previewBtn.length > 0) {
                        previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                    }
                }
            }
            
        } catch (error) {
            // ==================== 错误处理 ====================
            console.error('预览加载失败:', error);
            Utils.showNotification('预览加载失败: ' + error.message, 'error');
        } finally {
            // ==================== 恢复按钮状态 ====================
            // 恢复按钮原始状态
            if (previewBtn.length > 0) {
                previewBtn.prop('disabled', false);
                previewBtn.html(originalContent);
            }
        }
    }
    
    // ========== 粗胚管理功能 ==========
    
    /**
     * 显示粗胚上传界面
     * 
     * 打开粗胚批量上传模态框，允许用户选择多个粗胚文件进行上传
     */
    showBlankUpload() {
        // ==================== 构建上传界面HTML ====================
        // 显示粗胚批量上传界面
        const uploadHtml = `
            <div class="modal fade" id="blankUploadModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">批量上传粗胚文件</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="upload-zone" id="blank-upload-zone">
                                <i class="fas fa-cloud-upload-alt fa-3x text-muted mb-3"></i>
                                <h6>拖拽多个文件到此处或点击选择</h6>
                                <p class="text-muted small">支持.3dm和.stl格式，最大100MB每个文件</p>
                                <input type="file" id="blank-file-input" accept=".3dm,.stl" multiple style="display: none;">
                                <button type="button" class="btn btn-outline-primary" id="select-blank-file">
                                    选择多个文件
                                </button>
                            </div>
                            
                            <!-- 格式转换提示 -->
                            <div id="blank-format-conversion-notice" class="alert alert-info d-none mt-3">
                                <i class="fas fa-info-circle me-2"></i>
                                <strong>自动转换：</strong>检测到STL文件，将自动转换为3DM格式后处理，转换过程可能需要一些时间。
                            </div>
                            
                            <div id="blank-file-info" class="mt-3 d-none">
                                <div class="card">
                                    <div class="card-body">
                                        <h6>批量文件信息</h6>
                                        <p><strong>文件数量:</strong> <span id="blank-file-count">--</span></p>
                                        <p><strong>总大小:</strong> <span id="blank-total-size">--</span></p>
                                        <div class="mb-3">
                                            <label class="form-label">文件列表</label>
                                            <div id="blank-file-list" class="border rounded p-2" style="max-height: 200px; overflow-y: auto;">
                                                <!-- 文件列表将动态加载 -->
                                            </div>
                                        </div>
                                        <div class="mb-3">
                                            <label class="form-label">选择分类（应用到所有文件）</label>
                                            <div id="blank-categories-selection">
                                                <!-- 分类选择将动态加载 -->
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div id="batch-upload-progress" class="mt-3 d-none">
                                <div class="card">
                                    <div class="card-body">
                                        <h6>上传进度</h6>
                                        <div class="mb-2">
                                            <span id="current-upload-info">准备上传...</span>
                                        </div>
                                        <div class="progress mb-2">
                                            <div class="progress-bar" id="upload-progress-bar" role="progressbar" 
                                                 style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                                                0%
                                            </div>
                                        </div>
                                        <div class="d-flex justify-content-between">
                                            <small class="text-muted">
                                                成功: <span id="upload-success-count">0</span> | 
                                                失败: <span id="upload-error-count">0</span>
                                            </small>
                                            <small class="text-muted">
                                                <span id="current-file-index">0</span> / <span id="total-file-count">0</span>
                                            </small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" id="confirm-blank-upload" disabled>
                                <i class="fas fa-check me-2"></i>开始批量上传
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 移除现有的modal
        $('#blankUploadModal').remove();
        
        // 添加新的modal
        $('body').append(uploadHtml);
        
        // 绑定事件
        $('#select-blank-file').on('click', () => $('#blank-file-input').click());
        $('#blank-file-input').on('change', (e) => this.handleBlankFileSelect(e));
        $('#confirm-blank-upload').on('click', () => this.uploadBlankFiles());
        
        // 加载分类
        this.loadCategoriesForBlank();
        
        // 显示modal
        $('#blankUploadModal').modal('show');
    }
    
    async loadCategoriesForBlank() {
        try {
            const response = await Utils.apiRequest('/api/blanks/categories/');
            if (response.success) {
                this.renderCategoriesForBlank(response.data);
            }
        } catch (error) {
            console.error('加载分类失败:', error);
        }
    }
    
    renderCategoriesForBlank(categories) {
        let html = '';
        categories.forEach(category => {
            html += `
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" value="${category.id}" id="cat_${category.id}">
                    <label class="form-check-label" for="cat_${category.id}">
                        ${category.name}
                    </label>
                </div>
            `;
            
            if (category.children) {
                category.children.forEach(child => {
                    html += `
                        <div class="form-check ms-3">
                            <input class="form-check-input" type="checkbox" value="${child.id}" id="cat_${child.id}">
                            <label class="form-check-label" for="cat_${child.id}">
                                ${child.name}
                            </label>
                        </div>
                    `;
                });
            }
        });
        
        $('#blank-categories-selection').html(html);
    }
    
    handleBlankFileSelect(e) {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            this.selectedBlankFiles = files;
            this.handleBlankFiles(files);
        }
    }
    
    handleBlankFiles(files) {
        // 验证所有文件
        const validFiles = [];
        const invalidFiles = [];
        let totalSize = 0;
        
        let hasStlFiles = false;
        
        files.forEach(file => {
            const fileName = file.name.toLowerCase();
            if (!fileName.endsWith('.3dm') && !fileName.endsWith('.stl')) {
                invalidFiles.push(`${file.name}: 只支持.3dm和.stl格式`);
                return;
            }
            
            // 检测是否有STL文件
            if (fileName.endsWith('.stl')) {
                hasStlFiles = true;
            }
            
            if (file.size > CONFIG.UPLOAD_MAX_SIZE) {
                invalidFiles.push(`${file.name}: 文件大小超过100MB`);
                return;
            }
            
            validFiles.push(file);
            totalSize += file.size;
        });
        
        // 显示验证错误
        if (invalidFiles.length > 0) {
            Utils.showNotification(`以下文件无效:\n${invalidFiles.join('\n')}`, 'error');
        }
        
        if (validFiles.length === 0) {
            return;
        }
        
        // 更新选中的文件为有效文件
        this.selectedBlankFiles = validFiles;
        
        // 显示批量文件信息
        $('#blank-file-count').text(validFiles.length);
        $('#blank-total-size').text(Utils.formatFileSize(totalSize));
        
        // 生成文件列表
        let fileListHtml = '';
        validFiles.forEach((file, index) => {
            const fileName = file.name.replace('.3dm', '');
            fileListHtml += `
                <div class="d-flex justify-content-between align-items-center py-1 ${index > 0 ? 'border-top' : ''}">
                    <div>
                        <strong>${fileName}</strong>
                        <small class="text-muted d-block">${file.name}</small>
                    </div>
                    <span class="badge bg-secondary">${Utils.formatFileSize(file.size)}</span>
                </div>
            `;
        });
        
        $('#blank-file-list').html(fileListHtml);
        $('#blank-file-info').removeClass('d-none');
        $('#confirm-blank-upload').prop('disabled', false);
        
        // 显示转换提示（如果有STL文件）
        if (hasStlFiles) {
            $('#blank-format-conversion-notice').removeClass('d-none');
        } else {
            $('#blank-format-conversion-notice').addClass('d-none');
        }
    }
    
    async uploadBlankFiles() {
        if (!this.selectedBlankFiles || this.selectedBlankFiles.length === 0) {
            Utils.showNotification('请先选择文件', 'warning');
            return;
        }
        
        // 获取选中的分类
        const selectedCategories = [];
        $('#blank-categories-selection input:checked').each(function() {
            selectedCategories.push(parseInt($(this).val()));
        });
        
        if (selectedCategories.length === 0) {
            Utils.showNotification('请至少选择一个分类', 'warning');
            return;
        }
        
        try {
            // 禁用上传按钮并显示进度
            $('#confirm-blank-upload').prop('disabled', true);
            $('#batch-upload-progress').removeClass('d-none');
            
            const totalFiles = this.selectedBlankFiles.length;
            let successCount = 0;
            let errorCount = 0;
            const errors = [];
            
            // 初始化进度显示
            $('#total-file-count').text(totalFiles);
            $('#current-file-index').text(0);
            $('#upload-success-count').text(0);
            $('#upload-error-count').text(0);
            
            // 逐个上传文件
            for (let i = 0; i < this.selectedBlankFiles.length; i++) {
                const file = this.selectedBlankFiles[i];
                const fileName = file.name.replace('.3dm', '');
                
                // 更新进度显示
                const progress = ((i) / totalFiles) * 100;
                $('#upload-progress-bar').css('width', `${progress}%`).attr('aria-valuenow', progress).text(`${Math.round(progress)}%`);
                $('#current-file-index').text(i + 1);
                $('#current-upload-info').text(`正在上传: ${fileName}`);
                
                try {
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('name', fileName);
                    selectedCategories.forEach(catId => {
                        formData.append('categories', catId);
                    });
                    
                    const response = await fetch('/api/blanks/', {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                                          Utils.getCookie('csrftoken') || ''
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        successCount++;
                        $('#upload-success-count').text(successCount);
                    } else {
                        throw new Error(data.message || '上传失败');
                    }
                    
                } catch (error) {
                    errorCount++;
                    errors.push(`${fileName}: ${error.message}`);
                    $('#upload-error-count').text(errorCount);
                }
            }
            
            // 完成进度显示
            $('#upload-progress-bar').css('width', '100%').attr('aria-valuenow', 100).text('100%');
            $('#current-upload-info').text('上传完成');
            
            // 显示最终结果
            let message = `批量上传完成！成功: ${successCount}, 失败: ${errorCount}`;
            if (errors.length > 0) {
                message += `\n\n失败详情:\n${errors.join('\n')}`;
            }
            
            if (successCount > 0) {
                Utils.showNotification(message, successCount === totalFiles ? 'success' : 'warning');
                // 重新加载数据
                this.showBlankManage();
            } else {
                Utils.showNotification(message, 'error');
            }
            
            // 延迟关闭modal以显示完成状态
            setTimeout(() => {
                $('#blankUploadModal').modal('hide');
            }, 2000);
            
        } catch (error) {
            Utils.showNotification('批量上传失败: ' + error.message, 'error');
        } finally {
            // 重新启用上传按钮（如果用户没有关闭modal）
            setTimeout(() => {
                $('#confirm-blank-upload').prop('disabled', false);
            }, 3000);
        }
    }
    
    async showCategoryManage() {
        console.log('showCategoryManage 被调用');
        console.log('window.categoryManager 状态:', window.categoryManager);
        
        // 使用新的分类管理界面
        if (window.categoryManager) {
            console.log('调用 categoryManager.show()');
            await window.categoryManager.show();
        } else {
            console.error('分类管理模块未加载');
            Utils.showNotification('分类管理模块未加载', 'error');
        }
    }
    
    async showBlankManage() {
        console.log('showBlankManage 被调用');
        
        // 显示粗胚管理Modal
        $('#blankManageModal').modal('show');
        
        // 显示加载状态
        $('#category-tree').html(`
            <div class="text-center py-3">
                <i class="fas fa-spinner fa-spin"></i>
                <br>加载分类中...
            </div>
        `);
        
        $('#blank-list').html(`
            <div class="text-center py-4">
                <i class="fas fa-spinner fa-spin"></i>
                <br>加载粗胚中...
            </div>
        `);
        
        // 加载现有粗胚和分类
        try {
            console.log('开始加载分类和粗胚数据...');
            
            const [categoriesResponse, blanksResponse] = await Promise.all([
                Utils.apiRequest('/api/blanks/categories/'),
                Utils.apiRequest('/api/blanks/')
            ]);
            
            console.log('分类响应:', categoriesResponse);
            console.log('粗胚响应:', blanksResponse);
            
            // 检查分类API响应
            const categoriesOk = categoriesResponse.success && categoriesResponse.data;
            
            // 检查粗胚API响应 - 可能是DRF分页格式或success格式
            const blanksOk = (blanksResponse.success && blanksResponse.data) || 
                           (blanksResponse.results !== undefined); // DRF分页格式
            
            if (categoriesOk && blanksOk) {
                const categoriesData = categoriesResponse.data;
                const blanksData = blanksResponse.data || blanksResponse; // 兼容两种格式
                
                this.renderBlankManagement(categoriesData, blanksData);
            } else {
                const errorMsg = `分类API: ${categoriesOk ? '成功' : '失败'}, 粗胚API: ${blanksOk ? '成功' : '失败'}`;
                throw new Error(`API响应失败 - ${errorMsg}`);
            }
        } catch (error) {
            console.error('加载数据失败:', error);
            
            // 显示错误状态
            $('#category-tree').html(`
                <div class="text-danger text-center py-3">
                    <i class="fas fa-exclamation-triangle"></i>
                    <br>加载失败
                    <br><small>${error.message}</small>
                </div>
            `);
            
            $('#blank-list').html(`
                <div class="text-danger text-center py-4">
                    <i class="fas fa-exclamation-triangle"></i>
                    <br>加载失败
                    <br><small>请检查网络连接</small>
                </div>
            `);
            
            // 使用简单的alert避免递归
            alert('加载粗胚数据失败: ' + error.message);
        }
        
        // 监听分类变化事件，当分类管理页面有变化时自动刷新
        $(document).off('categoryChanged.blankManage').on('categoryChanged.blankManage', () => {
            console.log('检测到分类变化，刷新粗胚管理页面数据');
            // 重新加载数据
            this.refreshBlankManagementData();
        });
    }
    
    async refreshBlankManagementData() {
        console.log('刷新粗胚管理页面数据');
        
        // 显示加载状态
        $('#category-tree').html(`
            <div class="text-center py-3">
                <i class="fas fa-spinner fa-spin"></i>
                <br>刷新分类中...
            </div>
        `);
        
        $('#blank-list').html(`
            <div class="text-center py-4">
                <i class="fas fa-spinner fa-spin"></i>
                <br>刷新粗胚中...
            </div>
        `);
        
        try {
            const [categoriesResponse, blanksResponse] = await Promise.all([
                Utils.apiRequest('/api/blanks/categories/'),
                Utils.apiRequest('/api/blanks/')
            ]);
            
            // 检查API响应
            const categoriesOk = categoriesResponse.success && categoriesResponse.data;
            const blanksOk = (blanksResponse.success && blanksResponse.data) || 
                           (blanksResponse.results !== undefined);
            
            if (categoriesOk && blanksOk) {
                const categoriesData = categoriesResponse.data;
                const blanksData = blanksResponse.data || blanksResponse;
                
                this.renderBlankManagement(categoriesData, blanksData);
                console.log('粗胚管理页面数据刷新完成');
            } else {
                throw new Error('API响应失败');
            }
        } catch (error) {
            console.error('刷新数据失败:', error);
            Utils.showNotification('刷新数据失败: ' + error.message, 'error');
        }
    }
    
    renderBlankManagement(categories, blanks) {
        console.log('渲染粗胚管理数据:', categories, blanks);
        
        // 处理API响应格式 - blanks可能包装在results中
        const actualBlanks = blanks.results || blanks;
        
        // 更新分类树
        let categoryHtml = '';
        if (!categories || categories.length === 0) {
            categoryHtml = `
                <div class="text-muted text-center py-3">
                    <i class="fas fa-folder-open"></i>
                    <br>暂无分类
                </div>
            `;
        } else {
            // 递归渲染分类树
            const renderCategoryTree = (category, level = 0) => {
                const blankCount = actualBlanks.filter(blank => 
                    blank.categories_data && blank.categories_data.some(cat => cat.id === category.id)
                ).length;
                
                const marginLeft = level * 20; // 每级缩进20px
                const badgeClass = level === 0 ? 'bg-primary' : (level === 1 ? 'bg-secondary' : 'bg-info');
                const fontWeight = level === 0 ? 'fw-bold' : '';
                const icon = level === 0 ? 'fa-folder' : 'fa-tag';
                
                categoryHtml += `
                    <div class="category-item d-flex align-items-center p-2 border rounded mb-1 cursor-pointer" 
                         data-category-id="${category.id}"
                         style="margin-left: ${marginLeft}px;"
                         title="${category.description || category.name}">
                        <i class="fas ${icon} me-2 text-primary"></i>
                        <span class="${fontWeight}">${category.name}</span>
                        <span class="badge ${badgeClass} ms-auto">${blankCount}</span>
                    </div>
                `;
                
                // 递归渲染子分类
                if (category.children && category.children.length > 0) {
                    category.children.forEach(child => {
                        renderCategoryTree(child, level + 1);
                    });
                }
            };
            
            categories.forEach(category => {
                renderCategoryTree(category, 0);
            });
        }
        
        $('#category-tree').html(categoryHtml);
        
        // 更新粗胚列表
        this.renderBlankList(actualBlanks);
        
        // 绑定分类点击事件 - 使用事件委托
        $(document).off('click', '.category-item').on('click', '.category-item', (e) => {
            const categoryId = $(e.currentTarget).data('category-id');
            this.filterBlanksByCategory(categoryId, actualBlanks);
        });
    }
    
    renderBlankList(blanks) {
        console.log('渲染粗胚列表:', blanks);
        
        let html = '';
        
        if (!blanks || blanks.length === 0) {
            html = `
                <div class="text-muted text-center py-4">
                    <i class="fas fa-box-open fa-2x mb-2"></i>
                    <br>暂无粗胚文件
                    <br><small>点击"上传粗胚"添加文件</small>
                </div>
            `;
        } else {
            blanks.forEach(blank => {
                const categories = blank.categories_data ? 
                    blank.categories_data.map(cat => cat.name).join(', ') : '未分类';
                
                html += `
                    <div class="list-group-item list-group-item-action" data-blank-id="${blank.id}">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">${blank.name}</h6>
                            <small class="text-muted">${blank.file_size_mb || 0}MB</small>
                        </div>
                        <p class="mb-1 small text-muted">分类: ${categories}</p>
                        <small>体积: ${blank.volume ? blank.volume.toFixed(0) + ' mm³' : '--'}</small>
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-primary me-1" onclick="matchingApp.previewBlank(${blank.id})">
                                <i class="fas fa-eye"></i> 预览
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="matchingApp.deleteBlank(${blank.id})">
                                <i class="fas fa-trash"></i> 删除
                            </button>
                        </div>
                    </div>
                `;
            });
        }
        
        $('#blank-list').html(html);
        $('#blank-count').text(blanks ? blanks.length : 0);
    }
    
    filterBlanksByCategory(categoryId, allBlanks) {
        const filteredBlanks = allBlanks.filter(blank => 
            blank.categories_data.some(cat => cat.id === categoryId)
        );
        
        this.renderBlankList(filteredBlanks);
        
        // 高亮选中的分类
        $('.category-item').removeClass('bg-primary text-white');
        $(`.category-item[data-category-id="${categoryId}"]`).addClass('bg-primary text-white');
    }
    
    async previewBlank(blankId) {
        // ==================== 查找预览按钮 ====================
        // 查找粗胚预览按钮
        const previewBtn = $(`[onclick*="previewBlank(${blankId})"]`).first();
        const originalContent = previewBtn.length > 0 ? previewBtn.html() : '';
        
        try {
            // ==================== 显示按钮加载状态 ====================
            // 如果找到预览按钮，显示加载动画
            if (previewBtn.length > 0) {
                previewBtn.prop('disabled', true);
                previewBtn.html('<i class="fas fa-spinner fa-spin me-1"></i>生成中...');
            }
            
            // ==================== 检查Three.js预览可用性 ====================
            console.log('开始预览粗胚，ID:', blankId);
            
            // 检查粗胚是否支持Three.js预览
            const statusResponse = await Utils.apiRequest(`/api/lod/blank/${blankId}/status/`);
            console.log('粗胚状态API响应:', statusResponse);
            
            if (statusResponse.success && statusResponse.data && statusResponse.data.webgl_ready) {
                // ==================== 使用Three.js预览 ====================
                console.log('粗胚支持Three.js预览，跳转到新预览页面');
                
                // 更新按钮状态为预览完成
                if (previewBtn.length > 0) {
                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                }
                
                // 在新标签页中打开Three.js预览页面
                const previewUrl = `/api/three/blank/${blankId}/`;
                window.open(previewUrl, '_blank');
                
                Utils.showNotification('正在新标签页中打开3D预览...', 'success');
                
                // 1秒后恢复按钮原始状态
                setTimeout(() => {
                    if (previewBtn.length > 0) {
                        previewBtn.prop('disabled', false);
                        previewBtn.html('<i class="fas fa-eye"></i> 预览');
                    }
                }, 1000);
                
            } else if (statusResponse.success && statusResponse.data && statusResponse.data.has_3dm_file) {
                // ==================== 需要生成GLB文件 ====================
                console.log('粗胚暂不支持Three.js预览，尝试生成GLB文件...');
                
                // 更新按钮状态显示正在生成GLB
                if (previewBtn.length > 0) {
                    previewBtn.html('<i class="fas fa-cogs fa-spin me-1"></i>生成GLB中...');
                }
                
                Utils.showNotification('正在生成3D预览文件，请稍候...', 'info');
                
                try {
                    // 触发LOD处理
                    const processResponse = await Utils.apiRequest(`/api/lod/blank/${blankId}/process/`, {
                        method: 'POST'
                    });
                    
                    if (processResponse.success) {
                        console.log('LOD处理任务已启动，等待完成...');
                        if (previewBtn.length > 0) {
                            previewBtn.html('<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中...');
                        }
                        
                        // 轮询检查处理状态（最多等待3分钟）
                        const maxAttempts = 36; // 3分钟，每5秒检查一次
                        let attempts = 0;
                        
                        const checkStatus = async () => {
                            attempts++;
                            if (attempts > maxAttempts) {
                                Utils.showNotification('预览文件生成时间较长，请稍后再试', 'warning');
                                return;
                            }
                            
                            const checkResponse = await Utils.apiRequest(`/api/lod/blank/${blankId}/status/`);
                            
                            if (checkResponse.success && checkResponse.data && checkResponse.data.webgl_ready) {
                                // GLB文件已准备好，更新按钮状态为完成
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                                }
                                
                                console.log('GLB文件生成完成，打开预览页面');
                                const previewUrl = `/api/three/blank/${blankId}/`;
                                window.open(previewUrl, '_blank');
                                Utils.showNotification('3D预览文件生成完成！', 'success');
                                
                                // 1秒后恢复按钮原始状态
                setTimeout(() => {
                                    if (previewBtn.length > 0) {
                                        previewBtn.html('<i class="fas fa-eye me-1"></i>预览');
                                    }
                                }, 1000);
                                
                                return;
                            } else {
                                // 继续等待，更新进度提示
                                const progress = Math.round((attempts / maxAttempts) * 100);
                                if (previewBtn.length > 0) {
                                    previewBtn.html(`<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中 ${progress}%`);
                                }
                                
                                // 5秒后再次检查
                                setTimeout(checkStatus, 5000);
                            }
                        };
                        
                        // 开始状态检查
                        setTimeout(checkStatus, 5000);
                        
                    } else {
                        throw new Error(processResponse.message || 'LOD处理启动失败');
                    }
                } catch (processError) {
                    console.error('启动LOD处理失败:', processError);
                    Utils.showNotification('生成3D预览文件失败: ' + processError.message, 'error');
                if (previewBtn.length > 0) {
                        previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                    }
                }
                
            } else {
                // ==================== 强制生成GLB文件 ====================
                console.log('粗胚没有GLB文件，强制生成GLB文件...');
                
                // 更新按钮状态显示正在生成GLB
                if (previewBtn.length > 0) {
                    previewBtn.html('<i class="fas fa-cogs fa-spin me-1"></i>生成GLB中...');
                }
                
                Utils.showNotification('粗胚文件需要处理，正在生成3D预览文件...', 'info');
                
                try {
                    // 触发LOD处理
                    const processResponse = await Utils.apiRequest(`/api/lod/blank/${blankId}/process/`, {
                        method: 'POST'
                    });
                    
                    if (processResponse.success) {
                        console.log('LOD处理任务已启动，等待完成...');
                        if (previewBtn.length > 0) {
                            previewBtn.html('<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中...');
                        }
                        
                        // 轮询检查处理状态（最多等待5分钟）
                        const maxAttempts = 60; // 5分钟，每5秒检查一次
                        let attempts = 0;
                        
                        const checkStatus = async () => {
                            attempts++;
                            if (attempts > maxAttempts) {
                                Utils.showNotification('预览文件生成超时，请检查文件是否过大或稍后重试', 'error');
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                                }
                                return;
                            }
                            
                            const checkResponse = await Utils.apiRequest(`/api/lod/blank/${blankId}/status/`);
                            
                            if (checkResponse.success && checkResponse.data && checkResponse.data.webgl_ready) {
                                // GLB文件已准备好，更新按钮状态为完成
                                if (previewBtn.length > 0) {
                                    previewBtn.html('<i class="fas fa-check me-1"></i>预览完成');
                                }
                                
                                console.log('GLB文件生成完成，打开预览页面');
                                const previewUrl = `/api/three/blank/${blankId}/`;
                                window.open(previewUrl, '_blank');
                                Utils.showNotification('3D预览文件生成完成！正在打开预览...', 'success');
                                
                                // 1秒后恢复按钮原始状态
                                setTimeout(() => {
                                    if (previewBtn.length > 0) {
                                        previewBtn.html('<i class="fas fa-eye me-1"></i>预览');
                                    }
                                }, 1000);
                                
                                return;
                            } else {
                                // 继续等待，更新进度提示
                                const progress = Math.round((attempts / maxAttempts) * 100);
                                if (previewBtn.length > 0) {
                                    previewBtn.html(`<i class="fas fa-hourglass-half fa-spin me-1"></i>处理中 ${progress}%`);
                                }
                                
                                // 显示详细的处理状态
                                if (checkResponse.data && checkResponse.data.processing_status) {
                                    const status = checkResponse.data.processing_status;
                                    if (status === 'processing') {
                                        // 显示处理中状态
                                    } else if (status === 'failed') {
                                        Utils.showNotification('3D预览文件生成失败，请检查文件格式或稍后重试', 'error');
                                        if (previewBtn.length > 0) {
                                            previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                                        }
                                        return;
                                    }
                                }
                                
                                // 5秒后再次检查
                                setTimeout(checkStatus, 5000);
                            }
                        };
                        
                        // 开始状态检查
                        setTimeout(checkStatus, 5000);
                        
                    } else {
                        throw new Error(processResponse.message || 'LOD处理启动失败');
                    }
                } catch (processError) {
                    console.error('启动LOD处理失败:', processError);
                    Utils.showNotification('生成3D预览文件失败: ' + processError.message, 'error');
                    if (previewBtn.length > 0) {
                        previewBtn.html('<i class="fas fa-exclamation-triangle me-1"></i>生成失败');
                    }
                }
            }
            
        } catch (error) {
            console.error('预览加载失败:', error);
            Utils.showNotification('预览加载失败: ' + error.message, 'error');
            
        } finally {
            // ==================== 恢复按钮状态 ====================
            // 恢复按钮原始状态
            if (previewBtn.length > 0) {
                previewBtn.prop('disabled', false);
                previewBtn.html(originalContent);
            }
        }
    }
    
    adjustSceneSize() {
        console.log('开始调整#scene元素大小...');
        
        // 查找#scene元素
        const sceneElement = $('#preview-3d-content #scene');
        if (sceneElement.length > 0) {
            console.log('找到#scene元素，调整大小...');
            
            // 获取容器尺寸
            const container = $('#preview-3d-content');
            const containerWidth = container.width();
            const containerHeight = container.height();
            
            console.log(`容器尺寸: ${containerWidth} x ${containerHeight}`);
            
            // 设置#scene元素样式，让它占据更大空间
            sceneElement.css({
                'width': Math.max(containerWidth - 40, 800) + 'px',  // 减去一些边距，最小800px
                'height': Math.max(containerHeight - 40, 600) + 'px', // 减去一些边距，最小600px
                'max-width': '100%',
                'max-height': '100%',
                'margin': '0 auto',
                'display': 'block'
            });
            
            // 同时调整内部的canvas元素
            const canvasElements = sceneElement.find('canvas');
            if (canvasElements.length > 0) {
                console.log(`找到${canvasElements.length}个canvas元素，调整大小...`);
                canvasElements.each(function() {
                    $(this).css({
                        'width': '100%',
                        'height': '100%',
                        'max-width': '100%',
                        'max-height': '100%'
                    });
                });
            }
            
            console.log('#scene元素大小调整完成');
        } else {
            console.log('未找到#scene元素');
        }
        
        // 也尝试调整plotly相关的元素
        const plotlyDiv = $('#preview-3d-content .plotly-graph-div');
        if (plotlyDiv.length > 0) {
            console.log('找到Plotly容器，调整大小...');
            plotlyDiv.css({
                'width': '100%',
                'height': '100%',
                'min-height': '600px'
            });
        }
    }
    
    waitForPlotlyAndAdjust(maxAttempts = 10, attempt = 1) {
        console.log(`等待Plotly加载，尝试 ${attempt}/${maxAttempts}...`);
        
        const plotlyDiv = $('#preview-3d-content .plotly-graph-div')[0];
        
        if (plotlyDiv && window.Plotly && plotlyDiv._fullLayout) {
            // Plotly已完全加载
            console.log('Plotly已完全加载，开始调整尺寸...');
            this.adjustPreviewContent();
        } else if (attempt < maxAttempts) {
            // 继续等待
            setTimeout(() => {
                this.waitForPlotlyAndAdjust(maxAttempts, attempt + 1);
            }, 200);
        } else {
            console.warn('Plotly加载超时，跳过尺寸调整');
        }
    }
    
    adjustPreviewContent() {
        console.log('确保预览内容适配容器...');
        
        try {
            // 只确保容器样式正确，不强制调整Plotly尺寸
            $('#preview-3d-content').css({
                'width': '100%',
                'height': '600px',
                'overflow': 'hidden',
                'position': 'relative'
            });
            
            // 确保所有子元素不超出容器
            $('#preview-3d-content > *').css({
                'max-width': '100%',
                'max-height': '100%',
                'box-sizing': 'border-box'
            });
            
            console.log('预览容器样式调整完成');
            
        } catch (error) {
            console.error('调整预览内容时出错:', error);
        }
    }
    
    async deleteBlank(blankId) {
        if (!confirm('确定要删除这个粗胚文件吗？')) {
            return;
        }
        
        try {
            const response = await Utils.apiRequest(`/api/blanks/${blankId}/`, {
                method: 'DELETE'
            });
            
            if (response.success) {
                Utils.showNotification('粗胚删除成功', 'success');
                // 重新加载粗胚管理界面
                this.showBlankManage();
            }
            
        } catch (error) {
            Utils.showNotification('删除失败: ' + error.message, 'error');
        }
    }
    
    applyBlankSelection() {
        // 获取选中的分类
        const selectedCategories = [];
        $('#category-tree .category-item.bg-primary').each(function() {
            selectedCategories.push({
                id: $(this).data('category-id'),
                name: $(this).find('strong').text() || $(this).text().trim().split(' ')[0]
            });
        });
        
        if (selectedCategories.length === 0) {
            Utils.showNotification('请至少选择一个分类', 'warning');
            return;
        }
        
        // 更新主页面的分类选择显示
        this.updateCategorySelection(selectedCategories);
        
        // 关闭Modal
        $('#blankManageModal').modal('hide');
        
        // 清理事件监听器
        $(document).off('categoryChanged.blankManage');
        
        Utils.showNotification(`已选择 ${selectedCategories.length} 个分类`, 'success');
    }
    
    updateCategorySelection(categories) {
        this.selectedCategories = categories.map(cat => cat.id);
        
        let html = '';
        if (categories.length === 0) {
            html = `
                <div class="text-muted text-center py-3">
                    请先选择粗胚分类
                </div>
            `;
        } else {
            html = `
                <div class="mb-2">
                    <h6 class="small mb-2">已选择的分类:</h6>
                </div>
            `;
            
            categories.forEach(category => {
                html += `
                    <div class="selected-category-item border rounded p-2 mb-2 bg-light">
                        <div class="d-flex justify-content-between align-items-center">
                            <span><i class="fas fa-tag me-2 text-primary"></i>${category.name}</span>
                            <button class="btn btn-sm btn-outline-danger" onclick="matchingApp.removeCategory(${category.id})">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
            
            html += `
                <div class="mt-2">
                    <small class="text-muted">共选择 ${categories.length} 个分类</small>
                </div>
            `;
        }
        
        $('#category-selection').html(html);
        this.updateMatchingButton();
    }
    
    removeCategory(categoryId) {
        this.selectedCategories = this.selectedCategories.filter(id => id !== categoryId);
        
        // 重新获取分类信息并更新显示
        Utils.apiRequest('/api/blanks/categories/').then(response => {
            if (response.success) {
                const selectedCategoryData = [];
                response.data.forEach(category => {
                    if (this.selectedCategories.includes(category.id)) {
                        selectedCategoryData.push(category);
                    }
                    if (category.children) {
                        category.children.forEach(child => {
                            if (this.selectedCategories.includes(child.id)) {
                                selectedCategoryData.push(child);
                            }
                        });
                    }
                });
                
                this.updateCategorySelection(selectedCategoryData);
            }
        });
    }
    
    // ========== 匹配参数管理 ==========
    
    /**
     * 验证匹配参数
     * 
     * 检查用户输入的匹配参数是否有效，包括间隙要求和阈值设置
     * 
     * @returns {boolean} 参数是否有效
     */
    validateMatchingParams() {
        const clearance = parseFloat($('#clearance').val());
        const threshold = $('#threshold').val();
        
        // ==================== 验证间隙要求 ====================
        // 检查间隙值是否在有效范围内
        if (isNaN(clearance) || clearance < 0.5 || clearance > 10.0) {
            $('#clearance').addClass('is-invalid');
            this.showParamError('间隙要求必须在0.5-10.0mm之间');
            return false;
        } else {
            $('#clearance').removeClass('is-invalid');
        }
        
        // ==================== 更新阈值说明 ====================
        // 根据选择的阈值更新说明文字
        this.updateThresholdDescription(threshold);
        
        // 更新匹配按钮状态
        this.updateMatchingButton();
        return true;
    }
    
    /**
     * 更新阈值参数说明
     * 
     * 根据用户选择的阈值标准显示相应的说明文字
     * 
     * @param {string} threshold - 阈值标准
     */
    updateThresholdDescription(threshold) {
        // 阈值标准说明映射
        const descriptions = {
            'min': '严格标准：所有点间隙 ≥ 设定值',
            'p10': 'P10标准：90%的点间隙 ≥ 设定值',
            'p15': 'P15标准：85%的点间隙 ≥ 设定值（推荐）',
            'p20': 'P20标准：80%的点间隙 ≥ 设定值'
        };
        
        const description = descriptions[threshold] || '';
        
        // 如果没有说明元素，创建一个
        if ($('#threshold-description').length === 0) {
            $('#threshold').after('<small id="threshold-description" class="form-text text-muted"></small>');
        }
        
        $('#threshold-description').text(description);
    }
    
    /**
     * 切换缩放选项显示
     * 
     * 根据是否启用缩放来控制相关参数的显示/隐藏
     */
    toggleScalingOptions() {
        const isEnabled = $('#enableScaling').is(':checked');
        $('#maxScale').prop('disabled', !isEnabled);
        
        if (isEnabled) {
            $('#maxScale').removeClass('disabled');
            this.validateScalingParams();
        } else {
            $('#maxScale').addClass('disabled');
            $('#maxScale').removeClass('is-invalid');
        }
    }
    
    validateScalingParams() {
        const maxScale = parseFloat($('#maxScale').val());
        
        if (isNaN(maxScale) || maxScale < 1.0 || maxScale > 1.1) {
            $('#maxScale').addClass('is-invalid');
            this.showParamError('最大缩放比例必须在1.0-1.1之间');
            return false;
        } else {
            $('#maxScale').removeClass('is-invalid');
        }
        
        return true;
    }
    
    /**
     * 显示参数错误提示
     * 
     * 在界面上显示参数验证错误信息，3秒后自动隐藏
     * 
     * @param {string} message - 错误消息
     */
    showParamError(message) {
        // ==================== 创建错误提示元素 ====================
        // 显示参数错误提示
        if ($('#param-error').length === 0) {
            $('#advancedOptions').after('<div id="param-error" class="alert alert-warning alert-sm mt-2"></div>');
        }
        
        // ==================== 显示错误信息 ====================
        // 设置错误消息内容
        $('#param-error').html(`<i class="fas fa-exclamation-triangle me-2"></i>${message}`);
        
        // ==================== 自动隐藏 ====================
        // 3秒后自动隐藏
        setTimeout(() => {
            $('#param-error').fadeOut();
        }, 3000);
    }
    
    /**
     * 获取匹配参数
     * 
     * 从表单中收集所有匹配参数，用于发送到后端
     * 
     * @returns {Object} 匹配参数字典
     */
    getMatchingParams() {
        return {
            clearance: parseFloat($('#clearance').val()),
            threshold: $('#threshold').val(),
            enable_scaling: $('#enableScaling').is(':checked'),
            enable_multi_start: $('#enableMultiStart').is(':checked'),
            max_scale: parseFloat($('#maxScale').val())
        };
    }
    
    // ========== 3D预览功能 ==========
    
    resetPreviewView() {
        // 重置3D视图到默认角度
        if (window.currentPlotlyDiv) {
            const update = {
                'scene.camera': {
                    eye: {x: 1.5, y: -1.8, z: 1.2},
                    center: {x: 0, y: 0, z: 0},
                    up: {x: 0, y: 0, z: 1}
                }
            };
            
            Plotly.relayout(window.currentPlotlyDiv, update);
            Utils.showNotification('视角已重置', 'info');
        }
    }
    
    takeScreenshot() {
        // 截取3D预览截图
        if (window.currentPlotlyDiv) {
            Plotly.toImage(window.currentPlotlyDiv, {
                format: 'png',
                width: 1200,
                height: 800
            }).then(function(dataURL) {
                // 创建下载链接
                const link = document.createElement('a');
                link.download = `3d_preview_${Date.now()}.png`;
                link.href = dataURL;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                Utils.showNotification('截图已保存', 'success');
            }).catch(function(error) {
                Utils.showNotification('截图失败: ' + error.message, 'error');
            });
        }
    }
    
    toggleFullscreen() {
        // 切换全屏模式
        const modal = document.getElementById('preview3DModal');
        
        if (!document.fullscreenElement) {
            modal.requestFullscreen().then(() => {
                $('#fullscreen-preview').html('<i class="fas fa-compress"></i> 退出全屏');
                
                // 调整3D视图大小
                if (window.currentPlotlyDiv) {
                    Plotly.Plots.resize(window.currentPlotlyDiv);
                }
            }).catch(err => {
                Utils.showNotification('全屏模式失败: ' + err.message, 'error');
            });
        } else {
            document.exitFullscreen().then(() => {
                $('#fullscreen-preview').html('<i class="fas fa-expand"></i> 全屏');
            });
        }
    }
    
    /**
     * 切换热力图预览全屏模式
     */
    toggleHeatmapFullscreen() {
        const modal = document.getElementById('resultDetailModal');
        const button = document.getElementById('fullscreen-heatmap');
        const metricsPanel = document.getElementById('metrics-panel');
        const previewPanel = document.getElementById('preview-panel');
        const modalHeader = modal.querySelector('.modal-header');
        const modalFooter = modal.querySelector('.modal-footer');
        
        if (!document.fullscreenElement) {
            // 进入全屏
            modal.requestFullscreen().then(() => {
                button.innerHTML = '<i class="fas fa-compress"></i>';
                button.title = '退出全屏';
                console.log('已进入全屏模式');
                
                // 隐藏左侧指标面板，让3D预览居中
                if (metricsPanel) metricsPanel.style.display = 'none';
                
                // 让预览面板占满整个宽度
                if (previewPanel) {
                    previewPanel.classList.remove('col-md-8');
                    previewPanel.classList.add('col-12');
                }
                
                // 隐藏模态框的头部和底部，只显示3D预览
                if (modalHeader) modalHeader.style.display = 'none';
                if (modalFooter) modalFooter.style.display = 'none';
                
                // 通知 Three.js viewer 调整大小
                if (this.transparentViewer && this.transparentViewer.renderer) {
                    setTimeout(() => {
                        const container = document.getElementById('heatmap-preview');
                        this.transparentViewer.renderer.setSize(
                            container.clientWidth,
                            container.clientHeight
                        );
                        if (this.transparentViewer.camera) {
                            this.transparentViewer.camera.aspect = container.clientWidth / container.clientHeight;
                            this.transparentViewer.camera.updateProjectionMatrix();
                        }
                        this.transparentViewer.renderer.render(
                            this.transparentViewer.scene,
                            this.transparentViewer.camera
                        );
                    }, 100);
                }
            }).catch(err => {
                console.error('全屏模式失败:', err);
                Utils.showNotification('全屏模式失败: ' + err.message, 'error');
            });
        } else {
            // 退出全屏
            document.exitFullscreen().then(() => {
                button.innerHTML = '<i class="fas fa-expand"></i>';
                button.title = '全屏';
                console.log('已退出全屏模式');
                
                // 恢复左侧指标面板
                if (metricsPanel) metricsPanel.style.display = '';
                
                // 恢复预览面板的原始宽度
                if (previewPanel) {
                    previewPanel.classList.remove('col-12');
                    previewPanel.classList.add('col-md-8');
                }
                
                // 恢复模态框的头部和底部
                if (modalHeader) modalHeader.style.display = '';
                if (modalFooter) modalFooter.style.display = '';
                
                // 恢复正常大小
                setTimeout(() => {
                    if (this.transparentViewer && this.transparentViewer.renderer) {
                        const container = document.getElementById('heatmap-preview');
                        this.transparentViewer.renderer.setSize(
                            container.clientWidth,
                            container.clientHeight
                        );
                        if (this.transparentViewer.camera) {
                            this.transparentViewer.camera.aspect = container.clientWidth / container.clientHeight;
                            this.transparentViewer.camera.updateProjectionMatrix();
                        }
                        this.transparentViewer.renderer.render(
                            this.transparentViewer.scene,
                            this.transparentViewer.camera
                        );
                    }
                }, 100);
            });
        }
    }
    
    /**
     * 下载热力图截图
     */
    downloadHeatmapScreenshot() {
        if (!this.transparentViewer || !this.transparentViewer.renderer) {
            Utils.showNotification('请先加载3D预览', 'warning');
            return;
        }
        
        try {
            // 渲染当前场景
            this.transparentViewer.renderer.render(
                this.transparentViewer.scene,
                this.transparentViewer.camera
            );
            
            // 获取canvas并转换为图片
            const canvas = this.transparentViewer.renderer.domElement;
            canvas.toBlob((blob) => {
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                
                // 生成文件名
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                const taskId = this.currentTask ? this.currentTask.task_id : 'unknown';
                link.download = `3d_preview_${taskId}_${timestamp}.png`;
                
                // 触发下载
                link.click();
                
                // 清理URL对象
                URL.revokeObjectURL(url);
                
                Utils.showNotification('截图已保存', 'success');
                console.log('截图已保存:', link.download);
            }, 'image/png');
        } catch (error) {
            console.error('截图失败:', error);
            Utils.showNotification('截图失败: ' + error.message, 'error');
        }
    }
    
    // 当Plotly图表加载完成时调用
    onPlotlyReady(plotlyDiv) {
        window.currentPlotlyDiv = plotlyDiv;
        
        // 添加交互提示
        if ($('#interaction-tips').length === 0) {
            $('#preview-3d-content').append(`
                <div id="interaction-tips" class="position-absolute" style="top: 10px; right: 10px; background: rgba(0,0,0,0.7); color: white; padding: 8px; border-radius: 4px; font-size: 12px;">
                    <div><i class="fas fa-mouse"></i> 拖拽旋转</div>
                    <div><i class="fas fa-search-plus"></i> 滚轮缩放</div>
                    <div><i class="fas fa-hand-paper"></i> 右键平移</div>
                </div>
            `);
            
            // 5秒后自动隐藏提示
            setTimeout(() => {
                $('#interaction-tips').fadeOut();
            }, 5000);
        }
    }
    
    // ========== 导出功能 ==========
    
    /**
     * 导出匹配报告
     * 
     * 根据当前状态决定导出单个匹配结果还是批量匹配结果
     */
    exportReport() {
        // ==================== 检查导出数据 ====================
        // 检查是否有队列结果或单个结果
        if (this.completedMatches && this.completedMatches.length > 0) {
            // 导出队列匹配结果
            this.exportQueueReport();
        } else if (this.currentTask && this.currentResults) {
            // 导出单个匹配结果
            this.exportSingleReport();
        } else {
            Utils.showNotification('没有可导出的结果', 'warning');
        }
    }
    
    /**
     * 导出单个匹配结果报告
     * 
     * 将当前匹配任务的结果导出为JSON格式的报告文件
     */
    exportSingleReport() {
        try {
            // ==================== 准备导出数据 ====================
            // 创建导出数据
            const exportData = {
                task_info: {
                    task_id: this.currentTask.task_id,
                    shoe_model: this.currentShoeModel ? this.currentShoeModel.name : '',
                    created_at: new Date().toISOString(),
                    parameters: this.getMatchingParams()
                },
                summary: this.currentSummary,
                results: this.currentResults
            };
            
            // ==================== 创建下载文件 ====================
            // 创建下载链接
            const dataStr = JSON.stringify(exportData, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            
            const link = document.createElement('a');
            link.href = url;
            link.download = `matching_report_${this.currentTask.task_id}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            URL.revokeObjectURL(url);
            
            Utils.showNotification('报告导出成功', 'success');
            
        } catch (error) {
            Utils.showNotification('导出失败: ' + error.message, 'error');
        }
    }
    
    exportQueueReport() {
        try {
            // 创建队列匹配导出数据
            const exportData = {
                batch_info: {
                    total_shoes: this.completedMatches.length,
                    successful_matches: this.completedMatches.filter(m => m.status === 'completed').length,
                    created_at: new Date().toISOString(),
                    parameters: this.getMatchingParams()
                },
                matches: this.completedMatches.map(match => ({
                    shoe_model: match.shoe.name,
                    task_id: match.taskId,
                    status: match.status,
                    completed_at: match.completedAt,
                    summary: match.summary,
                    best_match: match.bestMatch,
                    results: match.results
                }))
            };
            
            // 创建下载链接
            const dataStr = JSON.stringify(exportData, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            
            const link = document.createElement('a');
            link.href = url;
            link.download = `queue_matching_report_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            URL.revokeObjectURL(url);
            
            Utils.showNotification('队列匹配报告导出成功', 'success');
            
        } catch (error) {
            Utils.showNotification('导出失败: ' + error.message, 'error');
        }
    }
    
    exportModels() {
        if (!this.currentTask) {
            Utils.showNotification('没有可导出的模型', 'warning');
            return;
        }
        
        // 显示导出选项Modal
        const exportModalHtml = `
            <div class="modal fade" id="exportModelsModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">导出3D模型</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>选择要导出的模型格式：</p>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="export-ply" checked>
                                <label class="form-check-label" for="export-ply">
                                    PLY格式 (推荐，支持颜色)
                                </label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="export-target">
                                <label class="form-check-label" for="export-target">
                                    包含目标鞋模
                                </label>
                            </div>
                            <div class="mt-3">
                                <label class="form-label">导出数量限制：</label>
                                <select class="form-select" id="export-limit">
                                    <option value="3">前3个结果</option>
                                    <option value="5">前5个结果</option>
                                    <option value="10">前10个结果</option>
                                    <option value="all">所有结果</option>
                                </select>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" onclick="matchingApp.confirmExportModels()">
                                <i class="fas fa-download me-2"></i>开始导出
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 移除现有modal并添加新的
        $('#exportModelsModal').remove();
        $('body').append(exportModalHtml);
        $('#exportModelsModal').modal('show');
    }
    
    confirmExportModels() {
        const includePly = $('#export-ply').is(':checked');
        const includeTarget = $('#export-target').is(':checked');
        const exportLimit = $('#export-limit').val();
        
        if (!includePly) {
            Utils.showNotification('请至少选择一种导出格式', 'warning');
            return;
        }
        
        // 关闭Modal
        $('#exportModelsModal').modal('hide');
        
        // 显示导出进度
        Utils.showNotification('正在准备模型文件，请稍候...', 'info');
        
        // 这里可以调用后端API来生成和下载模型文件
        // 由于当前hybrid系统已经生成PLY文件，我们可以直接提供下载链接
        Utils.showNotification('模型导出功能将在后续版本中完善', 'info');
    }
}

// 全局变量
let matchingApp;

// ==================== 应用初始化 ====================
// 页面加载完成后初始化匹配应用
$(document).ready(function() {
    console.log('初始化匹配应用...');
    
    // ==================== 防止重复初始化 ====================
    // 防止重复初始化，避免内存泄漏和事件重复绑定
    if (window.matchingApp) {
        console.log('匹配应用已存在，跳过初始化');
        return;
    }
    
    // ==================== 延迟初始化 ====================
    // 延迟初始化，确保所有DOM元素都已加载完成
    setTimeout(() => {
        try {
            // 创建全局匹配应用实例
            window.matchingApp = new MatchingApp();
            matchingApp = window.matchingApp; // 保持向后兼容性
            
            console.log('匹配应用初始化完成');
        } catch (error) {
            console.error('匹配应用初始化失败:', error);
        }
    }, 500);
});
