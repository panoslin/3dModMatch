/**
 * 分类管理模块
 */

class CategoryManager {
    constructor() {
        this.categories = [];
        this.selectedCategory = null;
        this.isEditing = false;
        this.bindEvents();
    }
    
    bindEvents() {
        // 添加分类按钮
        $(document).on('click', '#add-category-btn', () => {
            this.showAddCategoryForm();
        });
        
        // 保存分类按钮
        $(document).on('click', '#save-category-btn', () => {
            console.log('保存分类按钮被点击');
            this.saveCategoryData();
        });
        
        // 确认删除按钮
        $(document).on('click', '#confirm-delete-category-btn', () => {
            this.confirmDeleteCategory();
        });
        
        // 分类项点击事件
        $(document).on('click', '.category-item-manage', (e) => {
            console.log('分类项被点击，事件对象:', e);
            const categoryId = $(e.currentTarget).data('category-id');
            console.log('从DOM获取的分类ID:', categoryId);
            this.selectCategory(categoryId);
        });
        
        // 编辑按钮
        $(document).on('click', '.edit-category-btn', (e) => {
            e.stopPropagation();
            const categoryId = $(e.currentTarget).data('category-id');
            this.showEditCategoryForm(categoryId);
        });
        
        // 删除按钮
        $(document).on('click', '.delete-category-btn', (e) => {
            e.stopPropagation();
            const categoryId = $(e.currentTarget).data('category-id');
            this.deleteCategoryWithConfirm(categoryId);
        });
        
        // 添加子分类按钮
        $(document).on('click', '.add-child-category-btn', (e) => {
            console.log('添加子分类按钮被点击，事件对象:', e);
            e.stopPropagation();
            const parentId = $(e.currentTarget).data('parent-id');
            console.log('获取到的父分类ID:', parentId);
            console.log('即将调用 showAddCategoryForm...');
            this.showAddCategoryForm(parentId);
        });
    }
    
    async loadCategories() {
        console.log('开始加载分类数据...');
        try {
            const response = await Utils.apiRequest('/api/blanks/categories/');
            console.log('分类API响应:', response);
            
            if (response.success) {
                this.categories = response.data;
                console.log('已加载的分类数据:', this.categories);
                this.renderCategoryTree(this.categories);
            } else {
                throw new Error('API响应失败');
            }
        } catch (error) {
            console.error('加载分类失败:', error);
            $('#category-tree-manage').html(`
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    加载分类失败: ${error.message}
                </div>
            `);
        }
    }
    
    renderCategoryTree(categories) {
        console.log('渲染分类树，数据:', categories);
        
        if (!categories || categories.length === 0) {
            console.log('没有分类数据，显示空状态');
            $('#category-tree-manage').html(`
                <div class="text-muted text-center py-4">
                    <i class="fas fa-folder-open fa-2x mb-2"></i>
                    <br>暂无分类
                    <br><small>点击"添加分类"创建第一个分类</small>
                </div>
            `);
            return;
        }
        
        const html = categories.map(category => this.renderCategoryItem(category, 0)).join('');
        console.log('生成的HTML:', html);
        $('#category-tree-manage').html(html);
        console.log('分类树渲染完成');
    }
    
    renderCategoryItem(category, level) {
        const indent = level * 20;
        const hasChildren = category.children && category.children.length > 0;
        
        let html = `
            <div class="category-item-manage d-flex align-items-center py-2 px-2 border-bottom" 
                 data-category-id="${category.id}" 
                 style="margin-left: ${indent}px;">
                <div class="flex-grow-1">
                    <i class="fas fa-${level === 0 ? 'folder' : 'tag'} text-primary me-2"></i>
                    <span class="category-name">${category.name}</span>
                    ${category.description ? `<small class="text-muted d-block">${category.description}</small>` : ''}
                </div>
                <div class="category-actions">
                    <button class="btn btn-sm btn-outline-primary edit-category-btn me-1" 
                            data-category-id="${category.id}" title="编辑">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger delete-category-btn" 
                            data-category-id="${category.id}" title="删除">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
        
        if (hasChildren) {
            html += category.children.map(child => this.renderCategoryItem(child, level + 1)).join('');
        }
        
        return html;
    }
    
    selectCategory(categoryId) {
        console.log('选择分类，ID:', categoryId);
        
        // 移除之前的选中状态
        $('.category-item-manage').removeClass('selected');
        
        // 添加选中状态
        $(`.category-item-manage[data-category-id="${categoryId}"]`).addClass('selected');
        
        // 查找选中的分类
        this.selectedCategory = this.findCategoryById(categoryId);
        console.log('选中的分类对象:', this.selectedCategory);
        
        // 更新操作面板
        console.log('即将调用 updateOperationPanel...');
        this.updateOperationPanel();
        console.log('updateOperationPanel 调用完成');
    }
    
    findCategoryById(id) {
        function searchInCategories(categories) {
            for (const category of categories) {
                if (category.id === id) {
                    return category;
                }
                if (category.children) {
                    const found = searchInCategories(category.children);
                    if (found) return found;
                }
            }
            return null;
        }
        
        return searchInCategories(this.categories);
    }
    
    updateOperationPanel() {
        console.log('更新操作面板，选中的分类:', this.selectedCategory);
        
        if (!this.selectedCategory) {
            console.log('没有选中分类，显示默认状态');
            $('#category-operation-panel').html(`
                <div class="text-muted text-center py-4">
                    <i class="fas fa-mouse-pointer fa-2x mb-2"></i>
                    <br>选择分类进行操作
                </div>
            `);
            return;
        }
        
        const category = this.selectedCategory;
        const childrenCount = category.children ? category.children.length : 0;
        
        console.log('生成操作面板HTML，分类:', category.name);
        
        const panelHTML = `
            <div class="selected-category-info">
                <h6><i class="fas fa-tag me-2"></i>${category.name}</h6>
                ${category.description ? `<p class="text-muted small">${category.description}</p>` : ''}
                
                <div class="category-stats mb-3">
                    <small class="text-muted">
                        <i class="fas fa-sitemap me-1"></i>子分类: ${childrenCount}个
                        <br>
                        <i class="fas fa-clock me-1"></i>创建时间: ${new Date(category.created_at).toLocaleString()}
                    </small>
                </div>
                
                <div class="category-actions-panel">
                    <button class="btn btn-outline-primary btn-sm w-100 mb-2 edit-category-btn" 
                            data-category-id="${category.id}">
                        <i class="fas fa-edit me-2"></i>编辑分类
                    </button>
                    <button class="btn btn-outline-success btn-sm w-100 mb-2 add-child-category-btn" 
                            data-parent-id="${category.id}">
                        <i class="fas fa-plus me-2"></i>添加子分类
                    </button>
                    <button class="btn btn-outline-danger btn-sm w-100 delete-category-btn" 
                            data-category-id="${category.id}">
                        <i class="fas fa-trash me-2"></i>删除分类
                    </button>
                </div>
            </div>
        `;
        
        console.log('操作面板HTML:', panelHTML);
        $('#category-operation-panel').html(panelHTML);
        console.log('操作面板更新完成');
    }
    
    showAddCategoryForm(parentId = null) {
        console.log('showAddCategoryForm 被调用，parentId:', parentId);
        this.isEditing = false;
        
        // 重置表单
        console.log('重置表单...');
        $('#category-form')[0].reset();
        $('#categoryFormModalLabel').html('<i class="fas fa-tag me-2"></i>添加分类');
        
        // 填充父分类选项
        console.log('填充父分类选项...');
        this.populateParentSelect();
        
        // 如果指定了父分类，则选中
        if (parentId) {
            console.log('设置父分类为:', parentId);
            $('#category-parent').val(parentId);
        }
        
        // 显示Modal
        console.log('显示分类表单Modal...');
        const formModal = $('#categoryFormModal');
        console.log('分类表单Modal元素:', formModal.length);
        formModal.modal('show');
        console.log('Modal.show() 已调用');
    }
    
    showEditCategoryForm(categoryId) {
        this.isEditing = true;
        const category = this.findCategoryById(categoryId);
        
        if (!category) {
            Utils.showNotification('分类不存在', 'error');
            return;
        }
        
        // 填充表单
        $('#category-name').val(category.name);
        $('#category-description').val(category.description || '');
        $('#categoryFormModalLabel').html('<i class="fas fa-edit me-2"></i>编辑分类');
        
        // 填充父分类选项（排除自己和子分类）
        this.populateParentSelect(categoryId);
        $('#category-parent').val(category.parent || '');
        
        // 存储当前编辑的分类ID
        $('#category-form').data('editing-id', categoryId);
        
        // 显示Modal
        $('#categoryFormModal').modal('show');
    }
    
    populateParentSelect(excludeId = null) {
        const select = $('#category-parent');
        select.empty().append('<option value="">-- 选择父分类 --</option>');
        
        const addOptions = (categories, prefix = '') => {
            categories.forEach(category => {
                if (excludeId && category.id === excludeId) {
                    return; // 排除自己
                }
                
                select.append(`<option value="${category.id}">${prefix}${category.name}</option>`);
                
                if (category.children && category.children.length > 0) {
                    addOptions(category.children, prefix + '　');
                }
            });
        };
        
        addOptions(this.categories);
    }
    
    async saveCategoryData() {
        console.log('saveCategoryData 方法被调用');
        const form = $('#category-form')[0];
        console.log('表单元素:', form);
        const formData = new FormData(form);
        
        const data = {
            name: formData.get('name').trim(),
            parent: formData.get('parent') || null,
            description: formData.get('description').trim()
        };
        console.log('提取的表单数据:', data);
        
        // 验证表单
        console.log('开始验证表单...');
        if (!this.validateCategoryForm(data)) {
            console.log('表单验证失败');
            return;
        }
        console.log('表单验证通过');
        
        try {
            let response;
            
            if (this.isEditing) {
                console.log('执行编辑模式...');
                const categoryId = $('#category-form').data('editing-id');
                console.log('编辑分类ID:', categoryId);
                response = await Utils.apiRequest(`/api/blanks/categories/${categoryId}/`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
            } else {
                console.log('执行新增模式...');
                console.log('发送POST请求到: /api/blanks/categories/');
                response = await Utils.apiRequest('/api/blanks/categories/', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
            }
            console.log('API响应:', response);
            
            if (response.success) {
                Utils.showNotification(response.message, 'success');
                $('#categoryFormModal').modal('hide');
                await this.loadCategories(); // 重新加载分类树
                
                // 触发分类变化事件，通知其他页面刷新
                $(document).trigger('categoryChanged');
                $(document).trigger('categoryChanged.mainPage');
                $(document).trigger('categoryChanged.blankManage');
            } else {
                throw new Error(response.message || 'API响应失败');
            }
        } catch (error) {
            console.error('保存分类失败:', error);
            Utils.showNotification(`保存分类失败: ${error.message}`, 'error');
        }
    }
    
    validateCategoryForm(data) {
        let isValid = true;
        
        // 清除之前的错误状态
        $('.form-control').removeClass('is-invalid');
        
        // 验证名称
        if (!data.name) {
            $('#category-name').addClass('is-invalid');
            $('#category-name').siblings('.invalid-feedback').text('请输入分类名称');
            isValid = false;
        }
        
        return isValid;
    }
    
    deleteCategoryWithConfirm(categoryId) {
        const category = this.findCategoryById(categoryId);
        
        if (!category) {
            Utils.showNotification('分类不存在', 'error');
            return;
        }
        
        // 填充删除确认信息
        $('#delete-category-name').text(category.name);
        $('#confirm-delete-category-btn').data('category-id', categoryId);
        
        // 显示确认Modal
        $('#deleteCategoryModal').modal('show');
    }
    
    async confirmDeleteCategory() {
        const categoryId = $('#confirm-delete-category-btn').data('category-id');
        console.log('确认删除分类，ID:', categoryId);
        
        try {
            console.log('发送DELETE请求到:', `/api/blanks/categories/${categoryId}/`);
            const response = await Utils.apiRequest(`/api/blanks/categories/${categoryId}/`, {
                method: 'DELETE'
            });
            
            console.log('删除API响应:', response);
            
            if (response.success) {
                Utils.showNotification(response.message || '分类删除成功', 'success');
                $('#deleteCategoryModal').modal('hide');
                await this.loadCategories(); // 重新加载分类树
                
                // 如果删除的是当前选中的分类，清除选择
                if (this.selectedCategory && this.selectedCategory.id === categoryId) {
                    this.selectedCategory = null;
                    this.updateOperationPanel();
                }
                
                // 触发分类变化事件，通知其他页面刷新
                $(document).trigger('categoryChanged');
                $(document).trigger('categoryChanged.mainPage');
                $(document).trigger('categoryChanged.blankManage');
            } else {
                // 显示后端返回的具体错误信息
                Utils.showNotification(response.message || '删除失败', 'error');
                $('#deleteCategoryModal').modal('hide');
            }
        } catch (error) {
            console.error('删除分类失败:', error);
            Utils.showNotification(`删除分类失败: ${error.message}`, 'error');
        }
    }
    
    // 显示分类管理主界面
    async show() {
        console.log('CategoryManager.show() 被调用');
        console.log('尝试显示 Modal: #categoryManageModal');
        
        const modal = $('#categoryManageModal');
        console.log('Modal 元素:', modal.length);
        
        if (modal.length > 0) {
            modal.modal('show');
            console.log('Modal.modal("show") 已调用');
            await this.loadCategories();
        } else {
            console.error('找不到 #categoryManageModal 元素');
        }
    }
}

// 全局分类管理器实例
let categoryManager;

// 页面加载完成后初始化
$(document).ready(function() {
    window.categoryManager = new CategoryManager();
    console.log('分类管理器初始化完成:', window.categoryManager);
});
