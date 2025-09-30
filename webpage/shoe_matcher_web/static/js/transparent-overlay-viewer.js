/**
 * 透明叠加查看器 - 快速可视化鞋模与粗胚匹配关系
 * 
 * 功能：
 * - 加载鞋模和粗胚模型
 * - 应用对齐变换
 * - 鞋模：灰色不透明
 * - 粗胚：蓝色半透明
 * - 直观显示匹配关系
 * 
 * 优势：
 * - 加载速度快（<3秒）
 * - 无需复杂的间隙计算
 * - 性能优秀
 * 
 * @author AI Assistant
 * @date 2025-09-30
 */

class TransparentOverlayViewer {
    constructor(viewer, options = {}) {
        this.viewer = viewer;
        
        // 配置
        this.config = {
            // 鞋模材质
            targetColor: options.targetColor || 0x808080,        // 灰色
            targetOpacity: options.targetOpacity || 1.0,         // 不透明
            
            // 粗胚材质
            candidateColor: options.candidateColor || 0x4080FF,  // 蓝色
            candidateOpacity: options.candidateOpacity || 0.5,   // 50% 透明
            
            // 是否启用双面渲染
            doubleSided: options.doubleSided !== false
        };
        
        // 模型引用
        this.targetModel = null;
        this.candidateModel = null;
        this.alignmentRestorer = null;
        this.alignmentData = null;
        
        // 状态
        this.isActive = false;
        
        // 手动调整功能
        this.interactionMode = 'view';  // 'view' | 'translate' | 'rotate'
        this.originalShoeTransform = null;  // 保存鞋模原始变换
        this.isDragging = false;
        this.previousMouse = { x: 0, y: 0 };
        
        // 绑定事件处理器
        this.boundMouseDown = this.onMouseDown.bind(this);
        this.boundMouseMove = this.onMouseMove.bind(this);
        this.boundMouseUp = this.onMouseUp.bind(this);
    }

    /**
     * 加载透明叠加视图
     */
    async loadTransparentOverlay(taskId, resultIndex) {
        try {
            // 显示加载提示
            this.showLoadingIndicator('正在加载透明叠加视图');
            
            // 步骤 1: 加载并对齐模型
            console.log('步骤 1/3: 加载并对齐模型...');
            await this.loadAndAlignModels(taskId, resultIndex);
            
            // 步骤 2: 设置透明材质
            console.log('步骤 2/3: 设置透明材质...');
            this.updateLoadingProgress('正在设置材质和透明度...', 95);
            this.setupTransparentMaterials();
            
            // 步骤 3: 调整相机
            console.log('步骤 3/3: 调整相机...');
            this.updateLoadingProgress('正在调整视图...', 98);
            this.fitCameraToScene();
            
            this.isActive = true;
            
            // 保存鞋模的原始变换（用于重置）
            this.saveOriginalShoeTransform();
            
            // 启用手动调整交互
            this.enableInteraction();
            
            this.updateLoadingProgress('加载完成！', 100);
            
            // 延迟隐藏加载提示，让用户看到100%完成
            setTimeout(() => {
                this.hideLoadingIndicator();
                console.log('透明叠加视图加载完成！');
            }, 500);
            
        } catch (error) {
            console.error('透明叠加视图加载失败:', error);
            this.hideLoadingIndicator();
            this.showErrorMessage(error.message);
            throw error;
        }
    }

    /**
     * 加载并对齐模型
     */
    async loadAndAlignModels(taskId, resultIndex) {
        // 复用现有的 AlignmentRestorer
        if (typeof AlignmentRestorer === 'undefined') {
            throw new Error('AlignmentRestorer 未加载，请确保已引入 dual-model-heatmap.js');
        }
        
        // 创建进度回调函数
        const progressCallback = (message, progress) => {
            this.updateLoadingProgress(message, progress);
        };
        
        // 初始化对齐还原器并传递进度回调
        this.updateLoadingProgress('正在获取对齐数据...', 10);
        this.alignmentRestorer = new AlignmentRestorer(this.viewer, progressCallback);
        await this.alignmentRestorer.restoreAlignment(taskId, resultIndex);
        
        // 获取模型引用
        this.targetModel = this.alignmentRestorer.targetModel;
        this.candidateModel = this.alignmentRestorer.candidateModel;
        this.alignmentData = this.alignmentRestorer.alignmentData;
        
        if (!this.targetModel || !this.candidateModel) {
            throw new Error('模型加载失败');
        }
        
        console.log('模型加载和对齐完成');
    }

    /**
     * 设置透明材质
     */
    setupTransparentMaterials() {
        if (!this.targetModel || !this.candidateModel) {
            throw new Error('模型未加载');
        }
        
        // 设置鞋模材质（灰色，不透明）
        this.targetModel.traverse((child) => {
            if (child.isMesh) {
                child.material = new THREE.MeshLambertMaterial({
                    color: this.config.targetColor,
                    transparent: false,
                    opacity: this.config.targetOpacity,
                    side: this.config.doubleSided ? THREE.DoubleSide : THREE.FrontSide,
                    depthWrite: true,
                    depthTest: true
                });
                child.renderOrder = 1;  // 先渲染
                child.material.needsUpdate = true;
            }
        });
        
        // 设置粗胚材质（蓝色，半透明）
        this.candidateModel.traverse((child) => {
            if (child.isMesh) {
                child.material = new THREE.MeshLambertMaterial({
                    color: this.config.candidateColor,
                    transparent: true,
                    opacity: this.config.candidateOpacity,
                    side: this.config.doubleSided ? THREE.DoubleSide : THREE.FrontSide,
                    depthWrite: false,  // 透明物体不写入深度
                    depthTest: true
                });
                child.renderOrder = 2;  // 后渲染（透明物体）
                child.material.needsUpdate = true;
            }
        });
        
        // 强制渲染多次，确保显示
        if (this.viewer && this.viewer.renderer && this.viewer.scene && this.viewer.camera) {
            // 立即渲染
            this.viewer.renderer.render(this.viewer.scene, this.viewer.camera);
            
            // 延迟再渲染一次（确保所有资源就绪）
            setTimeout(() => {
                if (this.viewer && this.viewer.renderer) {
                    this.viewer.renderer.render(this.viewer.scene, this.viewer.camera);
                }
            }, 100);
        }
    }

    /**
     * 调整相机以适应场景
     */
    fitCameraToScene() {
        if (!this.viewer || !this.viewer.scene || !this.viewer.camera || !this.viewer.controls) {
            return;
        }
        
        try {
            // 计算场景边界框
            const box = new THREE.Box3();
            
            this.viewer.scene.traverse((object) => {
                if (object.isMesh) {
                    box.expandByObject(object);
                }
            });
            
            if (box.isEmpty()) {
                console.warn('场景为空，无法调整相机');
                return;
            }
            
            // 计算边界框中心和大小
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            
            // 计算相机距离（确保能看到整个模型）
            const fov = this.viewer.camera.fov * (Math.PI / 180);
            let cameraDistance = Math.abs(maxDim / Math.sin(fov / 2));
            cameraDistance *= 1.5; // 添加一些边距
            
            // 设置相机位置（从斜上方观察）
            const direction = new THREE.Vector3(1, 1, 1).normalize();
            this.viewer.camera.position.copy(center).add(direction.multiplyScalar(cameraDistance));
            
            // 相机看向中心
            this.viewer.camera.lookAt(center);
            
            // 更新控制器目标
            if (this.viewer.controls.target) {
                this.viewer.controls.target.copy(center);
            }
            
            this.viewer.camera.updateProjectionMatrix();
            if (this.viewer.controls.update) {
                this.viewer.controls.update();
            }
            
            // 强制渲染，确保相机调整后可见
            if (this.viewer.renderer) {
                this.viewer.renderer.render(this.viewer.scene, this.viewer.camera);
            }
            
        } catch (error) {
            console.error('调整相机失败:', error);
        }
    }

    /**
     * 更新透明度（动态调整）
     */
    updateOpacity(candidateOpacity) {
        if (!this.candidateModel) return;
        
        this.config.candidateOpacity = Math.max(0, Math.min(1, candidateOpacity));
        
        this.candidateModel.traverse((child) => {
            if (child.isMesh && child.material) {
                child.material.opacity = this.config.candidateOpacity;
                child.material.needsUpdate = true;
            }
        });
    }

    /**
     * 切换粗胚可见性
     */
    toggleCandidateVisibility() {
        if (!this.candidateModel) return;
        
        this.candidateModel.visible = !this.candidateModel.visible;
    }

    /**
     * 切换鞋模可见性
     */
    toggleTargetVisibility() {
        if (!this.targetModel) return;
        
        this.targetModel.visible = !this.targetModel.visible;
    }

    /**
     * 清理资源
     */
    cleanup() {
        if (this.alignmentRestorer) {
            // AlignmentRestorer 会处理模型的清理
        }
        
        this.targetModel = null;
        this.candidateModel = null;
        this.alignmentData = null;
        this.isActive = false;
    }

    /**
     * 获取 CSRF Token
     */
    getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return '';
    }

    /**
     * 显示加载指示器
     */
    showLoadingIndicator(message = '正在加载3D模型...') {
        // 移除旧的加载指示器
        this.hideLoadingIndicator();
        
        // 创建加载指示器覆盖层
        const container = this.viewer.container;
        const overlay = document.createElement('div');
        overlay.id = 'three-loading-overlay';
        overlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(248, 249, 250, 0.95);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            backdrop-filter: blur(5px);
        `;
        
        overlay.innerHTML = `
            <div style="text-align: center;">
                <div class="spinner-border text-primary mb-3" role="status" style="width: 3rem; height: 3rem;">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <h5 class="text-primary mb-2" id="loading-message">${message}</h5>
                <p class="text-muted" id="loading-details">准备加载...</p>
                <div class="progress mt-3" style="width: 300px; height: 8px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary" 
                         role="progressbar" 
                         style="width: 0%"
                         id="loading-progress-bar"></div>
                </div>
            </div>
        `;
        
        container.appendChild(overlay);
        this.loadingOverlay = overlay;
    }

    /**
     * 更新加载进度
     */
    updateLoadingProgress(message, progress = null) {
        if (this.loadingOverlay) {
            const messageEl = this.loadingOverlay.querySelector('#loading-details');
            if (messageEl) {
                messageEl.textContent = message;
            }
            
            if (progress !== null) {
                const progressBar = this.loadingOverlay.querySelector('#loading-progress-bar');
                if (progressBar) {
                    progressBar.style.width = `${progress}%`;
                }
            }
        }
    }

    /**
     * 隐藏加载指示器
     */
    hideLoadingIndicator() {
        if (this.loadingOverlay && this.loadingOverlay.parentNode) {
            this.loadingOverlay.parentNode.removeChild(this.loadingOverlay);
            this.loadingOverlay = null;
        }
        
        // 兼容旧的 ID
        const oldIndicator = document.getElementById('heatmap-loading');
        if (oldIndicator) {
            oldIndicator.style.display = 'none';
        }
    }

    /**
     * 显示成功消息
     */
    showSuccessMessage() {
        // 加载成功，无需额外提示
    }

    /**
     * 显示错误消息
     */
    showErrorMessage(message) {
        console.error('错误:', message);
        
        const indicator = document.getElementById('heatmap-loading');
        if (indicator) {
            indicator.style.display = 'block';
            indicator.innerHTML = `
                <div class="alert alert-danger m-3" role="alert">
                    <strong>加载失败:</strong> ${message}
                </div>
            `;
        }
    }

    // ========================================================================
    // 手动调整功能
    // ========================================================================

    /**
     * 保存鞋模的原始变换
     */
    saveOriginalShoeTransform() {
        if (!this.targetModel) {
            console.warn('无法保存原始变换: 鞋模未加载');
            return;
        }
        
        this.originalShoeTransform = {
            position: this.targetModel.position.clone(),
            rotation: this.targetModel.rotation.clone(),
            quaternion: this.targetModel.quaternion.clone()
        };
        
        console.log('已保存鞋模原始变换');
    }

    /**
     * 启用交互
     */
    enableInteraction() {
        const container = this.viewer.renderer.domElement;
        container.addEventListener('mousedown', this.boundMouseDown);
        container.addEventListener('mousemove', this.boundMouseMove);
        container.addEventListener('mouseup', this.boundMouseUp);
        container.addEventListener('mouseleave', this.boundMouseUp);
        
        console.log('已启用手动调整交互');
    }

    /**
     * 禁用交互
     */
    disableInteraction() {
        const container = this.viewer.renderer.domElement;
        container.removeEventListener('mousedown', this.boundMouseDown);
        container.removeEventListener('mousemove', this.boundMouseMove);
        container.removeEventListener('mouseup', this.boundMouseUp);
        container.removeEventListener('mouseleave', this.boundMouseUp);
        
        console.log('已禁用手动调整交互');
    }

    /**
     * 设置交互模式
     */
    setInteractionMode(mode) {
        this.interactionMode = mode;
        
        // 根据模式控制 OrbitControls
        if (this.viewer.controls) {
            if (mode === 'view') {
                this.viewer.controls.enabled = true;
            } else {
                // 平移/旋转模式下禁用 OrbitControls 的左键拖拽
                this.viewer.controls.enabled = false;
            }
        }
        
        console.log(`切换交互模式: ${mode}`);
    }

    /**
     * 鼠标按下事件
     */
    onMouseDown(event) {
        if (this.interactionMode === 'view') return;
        if (event.button !== 0) return; // 只处理左键
        
        this.isDragging = true;
        this.previousMouse.x = event.clientX;
        this.previousMouse.y = event.clientY;
        
        event.preventDefault();
    }

    /**
     * 鼠标移动事件
     */
    onMouseMove(event) {
        if (!this.isDragging) return;
        
        const deltaX = event.clientX - this.previousMouse.x;
        const deltaY = event.clientY - this.previousMouse.y;
        
        if (this.interactionMode === 'translate') {
            this.translateShoe(deltaX, deltaY);
        } else if (this.interactionMode === 'rotate') {
            this.rotateShoe(deltaX, deltaY);
        }
        
        this.previousMouse.x = event.clientX;
        this.previousMouse.y = event.clientY;
        
        event.preventDefault();
    }

    /**
     * 鼠标释放事件
     */
    onMouseUp(event) {
        this.isDragging = false;
    }

    /**
     * 平移鞋模
     */
    translateShoe(deltaX, deltaY) {
        if (!this.targetModel || !this.viewer.camera) return;
        
        const camera = this.viewer.camera;
        const container = this.viewer.renderer.domElement;
        
        // 计算移动敏感度（根据相机距离和容器大小）
        const distance = camera.position.length();
        const sensitivity = distance / container.clientHeight * 2;
        
        // 获取相机的右向量和上向量
        const right = new THREE.Vector3();
        const up = new THREE.Vector3();
        
        camera.getWorldDirection(right);
        right.cross(camera.up).normalize();
        up.copy(camera.up).normalize();
        
        // 计算移动向量
        const moveX = right.multiplyScalar(deltaX * sensitivity);
        const moveY = up.multiplyScalar(-deltaY * sensitivity);
        
        // 应用移动
        this.targetModel.position.add(moveX);
        this.targetModel.position.add(moveY);
    }

    /**
     * 旋转鞋模
     */
    rotateShoe(deltaX, deltaY) {
        if (!this.targetModel || !this.viewer.camera) return;
        
        const sensitivity = 0.005; // 旋转敏感度
        
        // 绕 Y 轴旋转（水平拖拽）
        this.targetModel.rotation.y += deltaX * sensitivity;
        
        // 绕 X 轴旋转（垂直拖拽）
        this.targetModel.rotation.x += deltaY * sensitivity;
    }

    /**
     * 重置鞋模变换
     */
    resetShoeTransform() {
        if (!this.targetModel || !this.originalShoeTransform) {
            console.warn('无法重置: 原始变换未保存');
            return;
        }
        
        this.targetModel.position.copy(this.originalShoeTransform.position);
        this.targetModel.rotation.copy(this.originalShoeTransform.rotation);
        this.targetModel.quaternion.copy(this.originalShoeTransform.quaternion);
        
        console.log('已重置鞋模到原始位置');
    }
}

// 导出到全局作用域
if (typeof window !== 'undefined') {
    window.TransparentOverlayViewer = TransparentOverlayViewer;
}
