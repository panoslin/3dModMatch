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
        
        // 中线显示
        this.showCenterlines = false;
        this.targetCenterline = null;   // 鞋模中线
        this.candidateCenterline = null; // 粗胚中线
        this.centerlineLocked = false;  // 中线是否锁定
        this.lockedCenterlineDirection = null;  // 锁定的中线方向
        
        // 绑定事件处理器
        this.boundMouseDown = this.onMouseDown.bind(this);
        this.boundMouseMove = this.onMouseMove.bind(this);
        this.boundMouseUp = this.onMouseUp.bind(this);
        this.boundKeyDown = this.onKeyDown.bind(this);
        
        // 键盘控制配置
        this.keyboardStepSize = 1.0;  // 每次按键的基础移动距离（mm）
        this.keyboardRotationStep = 0.02;  // 每次按键的旋转角度（弧度）≈1.15度
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
        
        // 启用键盘控制
        document.addEventListener('keydown', this.boundKeyDown);
        
        console.log('已启用手动调整交互（鼠标 + 键盘）');
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
        
        // 禁用键盘控制
        document.removeEventListener('keydown', this.boundKeyDown);
        
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
     * 键盘按下事件
     */
    onKeyDown(event) {
        // 只在平移或旋转模式下响应
        if (this.interactionMode === 'view') return;
        
        // 检查是否是方向键
        const arrowKeys = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];
        if (!arrowKeys.includes(event.key)) return;
        
        // 防止页面滚动
        event.preventDefault();
        
        // 检测修饰键
        const multiplier = event.shiftKey ? 5 : 1;  // Shift键加速5倍
        
        // 根据模式处理
        if (this.interactionMode === 'translate') {
            this.handleKeyboardTranslate(event.key, multiplier);
        } else if (this.interactionMode === 'rotate') {
            this.handleKeyboardRotate(event.key, multiplier);
        }
    }

    /**
     * 键盘平移控制
     */
    handleKeyboardTranslate(key, multiplier = 1) {
        if (!this.targetModel || !this.viewer.camera) return;
        
        const stepSize = this.keyboardStepSize * multiplier;
        
        if (this.centerlineLocked && this.lockedCenterlineDirection) {
            // 锁定模式：只允许沿中线方向移动
            let moveDir = 0;
            
            switch(key) {
                case 'ArrowLeft':
                case 'ArrowDown':
                    moveDir = -1;  // 向后（沿中线负方向）
                    break;
                case 'ArrowRight':
                case 'ArrowUp':
                    moveDir = 1;   // 向前（沿中线正方向）
                    break;
            }
            
            const moveVector = this.lockedCenterlineDirection.clone().multiplyScalar(
                moveDir * stepSize
            );
            
            this.targetModel.position.add(moveVector);
            
            const directionText = moveDir > 0 ? '前' : '后';
            console.log(`⌨️ 🔒锁定平移: 沿中线向${directionText} ${stepSize.toFixed(1)}mm`);
        } else {
            // 正常模式：相对于相机平面移动
            const camera = this.viewer.camera;
            const right = new THREE.Vector3();
            const up = new THREE.Vector3();
            
            camera.getWorldDirection(right);
            right.cross(camera.up).normalize();
            up.copy(camera.up).normalize();
            
            let moveVector = new THREE.Vector3();
            
            switch(key) {
                case 'ArrowLeft':
                    moveVector = right.multiplyScalar(-stepSize);
                    break;
                case 'ArrowRight':
                    moveVector = right.multiplyScalar(stepSize);
                    break;
                case 'ArrowUp':
                    moveVector = up.multiplyScalar(stepSize);
                    break;
                case 'ArrowDown':
                    moveVector = up.multiplyScalar(-stepSize);
                    break;
            }
            
            this.targetModel.position.add(moveVector);
            
            const direction = {
                'ArrowLeft': '左',
                'ArrowRight': '右',
                'ArrowUp': '上',
                'ArrowDown': '下'
            }[key];
            console.log(`⌨️ 平移: ${direction} ${stepSize.toFixed(1)}mm`);
        }
        
        // 更新中线显示（实时更新，避免重新计算PCA）
        this.updateCenterlinePositions();
    }

    /**
     * 键盘旋转控制（相对于当前视图，锁定时绕中线）
     */
    handleKeyboardRotate(key, multiplier = 1) {
        if (!this.targetModel || !this.viewer.camera) return;
        
        const rotationStep = this.keyboardRotationStep * multiplier;
        const degrees = (rotationStep * 180 / Math.PI).toFixed(1);
        
        if (this.centerlineLocked && this.lockedCenterlineDirection) {
            // 锁定模式：只允许绕中线旋转
            let rotationAngle = 0;
            
            switch(key) {
                case 'ArrowLeft':
                case 'ArrowDown':
                    rotationAngle = -rotationStep;  // 逆时针
                    break;
                case 'ArrowRight':
                case 'ArrowUp':
                    rotationAngle = rotationStep;   // 顺时针
                    break;
            }
            
            // 绕中线旋转
            const rotationQuaternion = new THREE.Quaternion();
            rotationQuaternion.setFromAxisAngle(
                this.lockedCenterlineDirection,
                rotationAngle
            );
            
            this.targetModel.quaternion.multiplyQuaternions(
                rotationQuaternion,
                this.targetModel.quaternion
            );
            
            const directionText = rotationAngle > 0 ? '顺时针' : '逆时针';
            console.log(`⌨️ 🔒锁定旋转: 绕中线${directionText} ${degrees}°`);
        } else {
            // 正常模式：相对于视图旋转
            const camera = this.viewer.camera;
            const cameraDirection = new THREE.Vector3();
            camera.getWorldDirection(cameraDirection);
            
            const right = new THREE.Vector3();
            right.crossVectors(cameraDirection, camera.up).normalize();
            const up = camera.up.clone().normalize();
            
            let rotationAxis;
            let rotationAngle;
            let description;
            
            switch(key) {
                case 'ArrowLeft':
                    rotationAxis = up;
                    rotationAngle = rotationStep;
                    description = `绕视图垂直轴: +${degrees}° (向左转)`;
                    break;
                case 'ArrowRight':
                    rotationAxis = up;
                    rotationAngle = -rotationStep;
                    description = `绕视图垂直轴: -${degrees}° (向右转)`;
                    break;
                case 'ArrowUp':
                    rotationAxis = right;
                    rotationAngle = rotationStep;
                    description = `绕视图水平轴: +${degrees}° (后仰)`;
                    break;
                case 'ArrowDown':
                    rotationAxis = right;
                    rotationAngle = -rotationStep;
                    description = `绕视图水平轴: -${degrees}° (前倾)`;
                    break;
            }
            
            if (rotationAxis && rotationAngle !== undefined) {
                const rotationQuaternion = new THREE.Quaternion();
                rotationQuaternion.setFromAxisAngle(rotationAxis, rotationAngle);
                
                this.targetModel.quaternion.multiplyQuaternions(
                    rotationQuaternion,
                    this.targetModel.quaternion
                );
                
                console.log(`⌨️ ${description}`);
            }
        }
        
        // 更新中线显示（实时更新）
        this.updateCenterlinePositions();
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

    /**
     * 计算模型的PCA主轴（中线）
     */
    computePCAAxis(model) {
        if (!model || !model.geometry) return null;
        
        const positions = model.geometry.attributes.position.array;
        const count = positions.length / 3;
        
        // 1. 计算中心点
        let centerX = 0, centerY = 0, centerZ = 0;
        for (let i = 0; i < count; i++) {
            centerX += positions[i * 3];
            centerY += positions[i * 3 + 1];
            centerZ += positions[i * 3 + 2];
        }
        centerX /= count;
        centerY /= count;
        centerZ /= count;
        
        const center = new THREE.Vector3(centerX, centerY, centerZ);
        
        // 2. 计算协方差矩阵
        let cov = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0]
        ];
        
        for (let i = 0; i < count; i++) {
            const dx = positions[i * 3] - centerX;
            const dy = positions[i * 3 + 1] - centerY;
            const dz = positions[i * 3 + 2] - centerZ;
            
            cov[0][0] += dx * dx;
            cov[0][1] += dx * dy;
            cov[0][2] += dx * dz;
            cov[1][1] += dy * dy;
            cov[1][2] += dy * dz;
            cov[2][2] += dz * dz;
        }
        
        cov[1][0] = cov[0][1];
        cov[2][0] = cov[0][2];
        cov[2][1] = cov[1][2];
        
        for (let i = 0; i < 3; i++) {
            for (let j = 0; j < 3; j++) {
                cov[i][j] /= count;
            }
        }
        
        // 3. 简化的特征向量计算（使用迭代方法找主方向）
        // 对于鞋模，主轴通常是X方向（长度方向）
        const mainAxis = this.findPrincipalAxis(positions, center, count);
        
        return {
            center: center,
            direction: mainAxis,
            length: this.estimateAxisLength(positions, center, mainAxis, count)
        };
    }

    /**
     * 找到主轴方向（简化的幂迭代法）
     */
    findPrincipalAxis(positions, center, count) {
        // 初始猜测：X轴方向
        let v = new THREE.Vector3(1, 0, 0);
        
        // 幂迭代10次
        for (let iter = 0; iter < 10; iter++) {
            let newV = new THREE.Vector3(0, 0, 0);
            
            for (let i = 0; i < count; i++) {
                const dx = positions[i * 3] - center.x;
                const dy = positions[i * 3 + 1] - center.y;
                const dz = positions[i * 3 + 2] - center.z;
                
                const dot = dx * v.x + dy * v.y + dz * v.z;
                newV.x += dx * dot;
                newV.y += dy * dot;
                newV.z += dz * dot;
            }
            
            newV.normalize();
            v = newV;
        }
        
        return v;
    }

    /**
     * 估算轴长度（沿主轴方向的跨度）
     */
    estimateAxisLength(positions, center, axis, count) {
        let minProj = Infinity;
        let maxProj = -Infinity;
        
        for (let i = 0; i < count; i++) {
            const dx = positions[i * 3] - center.x;
            const dy = positions[i * 3 + 1] - center.y;
            const dz = positions[i * 3 + 2] - center.z;
            
            const proj = dx * axis.x + dy * axis.y + dz * axis.z;
            minProj = Math.min(minProj, proj);
            maxProj = Math.max(maxProj, proj);
        }
        
        return maxProj - minProj;
    }

    /**
     * 显示/隐藏中线
     */
    toggleCenterlines() {
        this.showCenterlines = !this.showCenterlines;
        
        if (this.showCenterlines) {
            this.renderCenterlines();
        } else {
            this.removeCenterlines();
        }
    }

    /**
     * 渲染中线（作为模型的子对象，自动跟随）
     */
    renderCenterlines() {
        console.log('🔍 开始渲染中线...');
        
        if (!this.targetModel || !this.candidateModel) {
            console.error('❌ 模型未加载:', {
                targetModel: !!this.targetModel,
                candidateModel: !!this.candidateModel
            });
            return;
        }
        
        console.log('✅ 模型已加载，开始计算PCA...');
        
        // 移除旧的中线
        this.removeCenterlines();
        
        // 计算鞋模中线（在局部坐标系中）
        const targetPCA = this.computePCAAxisLocal(this.targetModel);
        console.log('鞋模PCA:', targetPCA);
        
        if (targetPCA) {
            const start = targetPCA.direction.clone().multiplyScalar(-targetPCA.length / 2);
            const end = targetPCA.direction.clone().multiplyScalar(targetPCA.length / 2);
            
            console.log('鞋模中线（局部坐标）:', { start, end });
            
            this.targetCenterline = this.createCenterline(start, end, 0xff0000); // 红色
            this.targetCenterline.name = 'target-centerline';
            
            // 作为鞋模的子对象添加，这样会自动跟随鞋模移动
            this.targetModel.add(this.targetCenterline);
            console.log('✅ 鞋模中线已作为子对象添加');
        } else {
            console.error('❌ 无法计算鞋模PCA');
        }
        
        // 计算粗胚中线（在局部坐标系中）
        const candidatePCA = this.computePCAAxisLocal(this.candidateModel);
        console.log('粗胚PCA:', candidatePCA);
        
        if (candidatePCA) {
            const start = candidatePCA.direction.clone().multiplyScalar(-candidatePCA.length / 2);
            const end = candidatePCA.direction.clone().multiplyScalar(candidatePCA.length / 2);
            
            console.log('粗胚中线（局部坐标）:', { start, end });
            
            this.candidateCenterline = this.createCenterline(start, end, 0x00ff00); // 绿色
            this.candidateCenterline.name = 'candidate-centerline';
            
            // 作为粗胚的子对象添加
            this.candidateModel.add(this.candidateCenterline);
            console.log('✅ 粗胚中线已作为子对象添加');
        } else {
            console.error('❌ 无法计算粗胚PCA');
        }
        
        console.log('✅ 中线已显示: 鞋模(红色), 粗胚(绿色)');
    }
    
    /**
     * 计算模型的PCA主轴（局部坐标系）
     */
    computePCAAxisLocal(model) {
        if (!model || !model.geometry) return null;
        
        const positions = model.geometry.attributes.position.array;
        const count = positions.length / 3;
        
        // 在局部坐标系中计算（顶点已经是局部坐标）
        // 计算中心点
        let centerX = 0, centerY = 0, centerZ = 0;
        for (let i = 0; i < count; i++) {
            centerX += positions[i * 3];
            centerY += positions[i * 3 + 1];
            centerZ += positions[i * 3 + 2];
        }
        centerX /= count;
        centerY /= count;
        centerZ /= count;
        
        const center = new THREE.Vector3(centerX, centerY, centerZ);
        
        // 找到主轴方向
        const mainAxis = this.findPrincipalAxisFromPositions(positions, center, count);
        const length = this.estimateAxisLength(positions, center, mainAxis, count);
        
        return {
            center: center,      // 局部坐标系中的中心
            direction: mainAxis, // 局部坐标系中的方向
            length: length * 1.5 // 延长50%
        };
    }
    
    /**
     * 从顶点数组找主轴方向
     */
    findPrincipalAxisFromPositions(positions, center, count) {
        let v = new THREE.Vector3(1, 0, 0);
        
        for (let iter = 0; iter < 10; iter++) {
            let newV = new THREE.Vector3(0, 0, 0);
            
            for (let i = 0; i < count; i++) {
                const dx = positions[i * 3] - center.x;
                const dy = positions[i * 3 + 1] - center.y;
                const dz = positions[i * 3 + 2] - center.z;
                
                const dot = dx * v.x + dy * v.y + dz * v.z;
                newV.x += dx * dot;
                newV.y += dy * dot;
                newV.z += dz * dot;
            }
            
            newV.normalize();
            v = newV;
        }
        
        return v;
    }

    /**
     * 创建中线对象（粗线条）
     */
    createCenterline(start, end, color) {
        // 延长中线，使其更容易看到
        const direction = end.clone().sub(start).normalize();
        const length = end.distanceTo(start);
        const extendedLength = length * 1.5;  // 延长50%
        
        const extendedStart = start.clone().sub(direction.clone().multiplyScalar(length * 0.25));
        const extendedEnd = end.clone().add(direction.clone().multiplyScalar(length * 0.25));
        
        // 使用圆柱体创建粗线条（而不是LineBasicMaterial）
        const cylinderLength = extendedStart.distanceTo(extendedEnd);
        const cylinderGeometry = new THREE.CylinderGeometry(
            1.5,  // 顶部半径（1.5mm，明显可见）
            1.5,  // 底部半径
            cylinderLength,  // 长度
            8,    // 圆周分段
            1     // 高度分段
        );
        
        const material = new THREE.MeshBasicMaterial({
            color: color,
            depthTest: true,
            transparent: false
        });
        
        const cylinder = new THREE.Mesh(cylinderGeometry, material);
        
        // 设置位置和方向
        const midpoint = extendedStart.clone().add(extendedEnd).multiplyScalar(0.5);
        cylinder.position.copy(midpoint);
        
        // 对齐圆柱体方向
        const up = new THREE.Vector3(0, 1, 0);
        const quaternion = new THREE.Quaternion();
        quaternion.setFromUnitVectors(up, direction);
        cylinder.quaternion.copy(quaternion);
        
        console.log(`创建中线: 长度=${cylinderLength.toFixed(1)}mm, 半径=1.5mm`);
        
        return cylinder;
    }

    /**
     * 移除中线
     */
    removeCenterlines() {
        if (this.targetCenterline) {
            // 从鞋模子对象中移除
            if (this.targetModel) {
                this.targetModel.remove(this.targetCenterline);
            }
            this.targetCenterline = null;
        }
        if (this.candidateCenterline) {
            // 从粗胚子对象中移除
            if (this.candidateModel) {
                this.candidateModel.remove(this.candidateCenterline);
            }
            this.candidateCenterline = null;
        }
    }

    /**
     * 对齐中线（在全局坐标系中进行）
     */
    alignCenterlines() {
        if (!this.targetModel || !this.candidateModel) {
            console.warn('无法对齐中线: 模型未加载');
            return;
        }
        
        console.log('🔧 开始对齐中线...');
        
        // 计算全局坐标系中的PCA主轴
        const targetPCA = this.computePCAAxisGlobal(this.targetModel);
        const candidatePCA = this.computePCAAxisGlobal(this.candidateModel);
        
        console.log('鞋模全局PCA:', targetPCA);
        console.log('粗胚全局PCA:', candidatePCA);
        
        if (!targetPCA || !candidatePCA) {
            console.warn('无法计算主轴');
            return;
        }
        
        // 1. 计算中心偏移（粗胚中心 -> 鞋模要移动到的位置）
        const centerOffset = candidatePCA.center.clone().sub(targetPCA.center);
        console.log('中心偏移:', centerOffset);
        
        // 2. 计算方向对齐的旋转
        const quaternion = new THREE.Quaternion();
        quaternion.setFromUnitVectors(targetPCA.direction, candidatePCA.direction);
        
        console.log('旋转四元数:', quaternion);
        
        // 3. 先应用旋转（绕鞋模当前中心旋转）
        const targetCenter = targetPCA.center.clone();
        
        // 将鞋模移到原点
        this.targetModel.position.sub(targetCenter);
        
        // 应用旋转
        this.targetModel.quaternion.premultiply(quaternion);
        
        // 移回原位置
        this.targetModel.position.add(targetCenter);
        
        // 4. 再应用平移（对齐中心点）
        this.targetModel.position.add(centerOffset);
        
        console.log('✅ 中线已对齐');
        console.log(`   中心偏移: ${centerOffset.length().toFixed(2)}mm`);
        console.log(`   新位置: ${this.targetModel.position.x.toFixed(1)}, ${this.targetModel.position.y.toFixed(1)}, ${this.targetModel.position.z.toFixed(1)}`);
    }
    
    /**
     * 计算模型的PCA主轴（全局坐标系）
     */
    computePCAAxisGlobal(model) {
        if (!model || !model.geometry) return null;
        
        const positions = model.geometry.attributes.position.array;
        const count = positions.length / 3;
        
        // 将局部坐标转换为全局坐标
        const worldMatrix = model.matrixWorld;
        
        // 计算全局坐标中的中心点
        let centerX = 0, centerY = 0, centerZ = 0;
        const tempVec = new THREE.Vector3();
        
        for (let i = 0; i < count; i++) {
            tempVec.set(
                positions[i * 3],
                positions[i * 3 + 1],
                positions[i * 3 + 2]
            );
            tempVec.applyMatrix4(worldMatrix);
            
            centerX += tempVec.x;
            centerY += tempVec.y;
            centerZ += tempVec.z;
        }
        centerX /= count;
        centerY /= count;
        centerZ /= count;
        
        const globalCenter = new THREE.Vector3(centerX, centerY, centerZ);
        
        // 在全局坐标系中找主轴方向
        let v = new THREE.Vector3(1, 0, 0);
        
        for (let iter = 0; iter < 10; iter++) {
            let newV = new THREE.Vector3(0, 0, 0);
            
            for (let i = 0; i < count; i++) {
                tempVec.set(
                    positions[i * 3],
                    positions[i * 3 + 1],
                    positions[i * 3 + 2]
                );
                tempVec.applyMatrix4(worldMatrix);
                
                const dx = tempVec.x - centerX;
                const dy = tempVec.y - centerY;
                const dz = tempVec.z - centerZ;
                
                const dot = dx * v.x + dy * v.y + dz * v.z;
                newV.x += dx * dot;
                newV.y += dy * dot;
                newV.z += dz * dot;
            }
            
            newV.normalize();
            v = newV;
        }
        
        // 计算长度
        let minProj = Infinity;
        let maxProj = -Infinity;
        
        for (let i = 0; i < count; i++) {
            tempVec.set(
                positions[i * 3],
                positions[i * 3 + 1],
                positions[i * 3 + 2]
            );
            tempVec.applyMatrix4(worldMatrix);
            
            const dx = tempVec.x - centerX;
            const dy = tempVec.y - centerY;
            const dz = tempVec.z - centerZ;
            
            const proj = dx * v.x + dy * v.y + dz * v.z;
            minProj = Math.min(minProj, proj);
            maxProj = Math.max(maxProj, proj);
        }
        
        return {
            center: globalCenter,
            direction: v,
            length: maxProj - minProj
        };
    }

    /**
     * 锁定/解锁中线
     */
    toggleCenterlineLock() {
        this.centerlineLocked = !this.centerlineLocked;
        
        if (this.centerlineLocked) {
            // 锁定时保存当前中线方向
            const candidatePCA = this.computePCAAxis(this.candidateModel);
            if (candidatePCA) {
                this.lockedCenterlineDirection = candidatePCA.direction.clone();
                console.log('🔒 中线已锁定');
            }
        } else {
            this.lockedCenterlineDirection = null;
            console.log('🔓 中线已解锁');
        }
        
        return this.centerlineLocked;
    }

    /**
     * 平移鞋模（锁定中线时只允许沿中线方向移动）
     */
    translateShoe(deltaX, deltaY) {
        if (!this.targetModel || !this.viewer.camera) return;
        
        const camera = this.viewer.camera;
        const container = this.viewer.renderer.domElement;
        
        // 计算移动敏感度（根据相机距离和容器大小）
        const distance = camera.position.length();
        const sensitivity = distance / container.clientHeight * 2;
        
        if (this.centerlineLocked && this.lockedCenterlineDirection) {
            // 锁定模式：只允许沿中线方向平移
            const screenMove = new THREE.Vector2(deltaX, deltaY);
            const moveLength = screenMove.length() * sensitivity;
            
            // 判断移动方向（横向还是纵向为主）
            const isHorizontal = Math.abs(deltaX) > Math.abs(deltaY);
            
            // 沿中线方向移动
            const moveDir = isHorizontal ? 
                (deltaX > 0 ? 1 : -1) : 
                (deltaY < 0 ? 1 : -1);  // Y轴翻转
            
            const moveVector = this.lockedCenterlineDirection.clone().multiplyScalar(
                moveDir * moveLength
            );
            
            this.targetModel.position.add(moveVector);
            console.log('🔒 锁定平移: 沿中线方向');
        } else {
            // 正常模式：相对于相机平面移动
            const right = new THREE.Vector3();
            const up = new THREE.Vector3();
            
            camera.getWorldDirection(right);
            right.cross(camera.up).normalize();
            up.copy(camera.up).normalize();
            
            const moveX = right.multiplyScalar(deltaX * sensitivity);
            const moveY = up.multiplyScalar(-deltaY * sensitivity);
            
            this.targetModel.position.add(moveX);
            this.targetModel.position.add(moveY);
        }
        
        // 更新中线显示（实时更新）
        this.updateCenterlinePositions();
    }

    /**
     * 旋转鞋模（锁定中线时只允许绕中线旋转）
     */
    rotateShoe(deltaX, deltaY) {
        if (!this.targetModel || !this.viewer.camera) return;
        
        if (this.centerlineLocked && this.lockedCenterlineDirection) {
            // 锁定模式：只允许绕中线（主轴）旋转
            const rotationStep = 0.005;
            const totalDelta = Math.abs(deltaX) + Math.abs(deltaY);
            const rotationAngle = totalDelta * rotationStep;
            
            // 判断旋转方向
            const rotationDir = (deltaX + deltaY > 0) ? 1 : -1;
            
            // 绕中线旋转
            const rotationQuaternion = new THREE.Quaternion();
            rotationQuaternion.setFromAxisAngle(
                this.lockedCenterlineDirection,
                rotationAngle * rotationDir
            );
            
            this.targetModel.quaternion.multiplyQuaternions(
                rotationQuaternion,
                this.targetModel.quaternion
            );
            
            console.log('🔒 锁定旋转: 绕中线旋转');
        } else {
            // 正常模式：相对于视图旋转（原有逻辑保持不变）
            const sensitivity = 0.005;
            
            this.targetModel.rotation.y += deltaX * sensitivity;
            this.targetModel.rotation.x += deltaY * sensitivity;
        }
        
        // 更新中线显示（实时更新）
        this.updateCenterlinePositions();
    }

    /**
     * 更新中线位置
     * 注意：中线作为模型子对象会自动跟随，通常不需要手动更新
     * 仅在需要重新计算PCA时调用
     */
    updateCenterlinePositions() {
        // 中线已经是模型的子对象，会自动跟随移动和旋转
        // 无需每次都重新渲染
        // 除非需要重新计算PCA（例如模型变形时）
    }
}

// 导出到全局作用域
if (typeof window !== 'undefined') {
    window.TransparentOverlayViewer = TransparentOverlayViewer;
}
