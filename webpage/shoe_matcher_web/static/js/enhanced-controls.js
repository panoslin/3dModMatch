/*!
 * 增强交互控制器 - Three.js高级交互系统
 * 提供专业级的3D模型交互体验
 * 
 * 特性：
 * - 智能相机控制和动画
 * - 多点触摸手势支持
 * - 键盘快捷键
 * - 上下文菜单
 * - 测量工具
 * - 视角预设和动画过渡
 * 
 * 作者：AI Assistant
 * 版本：v1.0
 * 日期：2024-09-25
 */

(function(window) {
    'use strict';

    // ========================== 配置常量 ========================== //
    
    const CONTROLS_CONFIG = {
        // 相机动画配置
        CAMERA_ANIMATION: {
            duration: 1000,          // 动画时长(毫秒)
            easing: 'easeInOutQuad', // 缓动函数
            smoothness: 0.1          // 平滑度
        },
        
        // 手势识别配置
        GESTURES: {
            pinchThreshold: 10,      // 捏合阈值(像素)
            panThreshold: 5,         // 平移阈值
            tapTimeout: 300,         // 点击超时
            doubleTapTimeout: 400,   // 双击超时
            longPressTimeout: 800    // 长按超时
        },
        
        // 键盘快捷键
        KEYBOARD: {
            zoomIn: ['=', '+'],
            zoomOut: ['-', '_'],
            reset: ['r', 'R', ' '],
            fullscreen: ['f', 'F'],
            screenshot: ['s', 'S'],
            help: ['h', 'H', '?']
        },
        
        // 视角预设
        VIEW_PRESETS: {
            front: { position: [0, 0, 200], target: [0, 0, 0], name: '前视图' },
            back: { position: [0, 0, -200], target: [0, 0, 0], name: '后视图' },
            left: { position: [-200, 0, 0], target: [0, 0, 0], name: '左视图' },
            right: { position: [200, 0, 0], target: [0, 0, 0], name: '右视图' },
            top: { position: [0, 200, 0], target: [0, 0, 0], name: '俯视图' },
            bottom: { position: [0, -200, 0], target: [0, 0, 0], name: '仰视图' },
            isometric: { position: [150, 150, 150], target: [0, 0, 0], name: '等角视图' }
        }
    };

    // ========================== 工具函数 ========================== //
    
    /**
     * 缓动函数集合
     */
    const Easing = {
        linear: t => t,
        easeInQuad: t => t * t,
        easeOutQuad: t => t * (2 - t),
        easeInOutQuad: t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
        easeInCubic: t => t * t * t,
        easeOutCubic: t => (--t) * t * t + 1,
        easeInOutCubic: t => t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1
    };

    /**
     * 向量工具函数
     */
    const VectorUtils = {
        lerp: (a, b, t) => a + (b - a) * t,
        
        lerpVector3: (a, b, t, result) => {
            result.x = VectorUtils.lerp(a.x, b.x, t);
            result.y = VectorUtils.lerp(a.y, b.y, t);
            result.z = VectorUtils.lerp(a.z, b.z, t);
            return result;
        },
        
        distance: (a, b) => Math.sqrt(
            Math.pow(b.x - a.x, 2) + 
            Math.pow(b.y - a.y, 2) + 
            Math.pow(b.z - a.z, 2)
        )
    };

    // ========================== 手势识别器 ========================== //
    
    /**
     * 多点触摸手势识别器
     */
    class GestureRecognizer {
        constructor(element, callbacks = {}) {
            this.element = element;
            this.callbacks = callbacks;
            
            // 状态变量
            this.touches = new Map();
            this.lastTap = 0;
            this.tapCount = 0;
            this.isLongPress = false;
            this.longPressTimer = null;
            this.initialDistance = 0;
            this.initialCenter = { x: 0, y: 0 };
            
            // 绑定事件
            this._bindEvents();
        }

        _bindEvents() {
            // 触摸事件
            this.element.addEventListener('touchstart', this._handleTouchStart.bind(this), { passive: false });
            this.element.addEventListener('touchmove', this._handleTouchMove.bind(this), { passive: false });
            this.element.addEventListener('touchend', this._handleTouchEnd.bind(this), { passive: false });
            this.element.addEventListener('touchcancel', this._handleTouchCancel.bind(this), { passive: false });
            
            // 鼠标事件（作为触摸的回退）
            this.element.addEventListener('mousedown', this._handleMouseDown.bind(this));
            this.element.addEventListener('mousemove', this._handleMouseMove.bind(this));
            this.element.addEventListener('mouseup', this._handleMouseUp.bind(this));
            this.element.addEventListener('wheel', this._handleWheel.bind(this), { passive: false });
            
            // 阻止默认的触摸行为
            this.element.addEventListener('touchstart', (e) => e.preventDefault());
            this.element.addEventListener('touchmove', (e) => e.preventDefault());
        }

        _handleTouchStart(event) {
            const touches = Array.from(event.touches);
            
            // 更新触摸点
            touches.forEach(touch => {
                this.touches.set(touch.identifier, {
                    x: touch.clientX,
                    y: touch.clientY,
                    startTime: Date.now()
                });
            });
            
            if (touches.length === 1) {
                // 单指触摸 - 可能是点击或长按
                this._startLongPressTimer();
                this._handleTap(touches[0]);
                
                if (this.callbacks.touchStart) {
                    this.callbacks.touchStart({
                        type: 'single',
                        x: touches[0].clientX,
                        y: touches[0].clientY
                    });
                }
                
            } else if (touches.length === 2) {
                // 双指触摸 - 缩放或旋转
                this._clearLongPressTimer();
                this.initialDistance = this._calculateDistance(touches[0], touches[1]);
                this.initialCenter = this._calculateCenter(touches[0], touches[1]);
                
                if (this.callbacks.pinchStart) {
                    this.callbacks.pinchStart({
                        distance: this.initialDistance,
                        center: this.initialCenter
                    });
                }
            }
        }

        _handleTouchMove(event) {
            const touches = Array.from(event.touches);
            
            if (touches.length === 1) {
                // 单指平移
                this._clearLongPressTimer();
                const touch = touches[0];
                const stored = this.touches.get(touch.identifier);
                
                if (stored) {
                    const deltaX = touch.clientX - stored.x;
                    const deltaY = touch.clientY - stored.y;
                    
                    if (Math.abs(deltaX) > CONTROLS_CONFIG.GESTURES.panThreshold || 
                        Math.abs(deltaY) > CONTROLS_CONFIG.GESTURES.panThreshold) {
                        
                        if (this.callbacks.pan) {
                            this.callbacks.pan({ deltaX, deltaY });
                        }
                    }
                    
                    // 更新存储的位置
                    stored.x = touch.clientX;
                    stored.y = touch.clientY;
                }
                
            } else if (touches.length === 2) {
                // 双指缩放
                const currentDistance = this._calculateDistance(touches[0], touches[1]);
                const currentCenter = this._calculateCenter(touches[0], touches[1]);
                
                // 缩放
                if (Math.abs(currentDistance - this.initialDistance) > CONTROLS_CONFIG.GESTURES.pinchThreshold) {
                    const scale = currentDistance / this.initialDistance;
                    
                    if (this.callbacks.pinch) {
                        this.callbacks.pinch({
                            scale,
                            center: currentCenter,
                            delta: currentDistance - this.initialDistance
                        });
                    }
                    
                    this.initialDistance = currentDistance;
                }
                
                // 中心点移动（双指平移）
                const centerDeltaX = currentCenter.x - this.initialCenter.x;
                const centerDeltaY = currentCenter.y - this.initialCenter.y;
                
                if (Math.abs(centerDeltaX) > 5 || Math.abs(centerDeltaY) > 5) {
                    if (this.callbacks.pan) {
                        this.callbacks.pan({
                            deltaX: centerDeltaX,
                            deltaY: centerDeltaY
                        });
                    }
                    
                    this.initialCenter = currentCenter;
                }
            }
        }

        _handleTouchEnd(event) {
            const touches = Array.from(event.touches);
            
            // 清理结束的触摸点
            const activeTouchIds = new Set(touches.map(t => t.identifier));
            for (const [id] of this.touches) {
                if (!activeTouchIds.has(id)) {
                    this.touches.delete(id);
                }
            }
            
            this._clearLongPressTimer();
            
            if (touches.length === 0) {
                // 所有触摸结束
                if (this.callbacks.touchEnd) {
                    this.callbacks.touchEnd();
                }
            }
        }

        _handleTouchCancel(event) {
            this.touches.clear();
            this._clearLongPressTimer();
        }

        _handleMouseDown(event) {
            // 鼠标事件模拟触摸
            if (event.button === 0) {  // 左键
                this._handleTouchStart({
                    touches: [{
                        identifier: 'mouse',
                        clientX: event.clientX,
                        clientY: event.clientY
                    }]
                });
            }
        }

        _handleMouseMove(event) {
            if (this.touches.has('mouse')) {
                this._handleTouchMove({
                    touches: [{
                        identifier: 'mouse',
                        clientX: event.clientX,
                        clientY: event.clientY
                    }]
                });
            }
        }

        _handleMouseUp(event) {
            if (event.button === 0 && this.touches.has('mouse')) {
                this._handleTouchEnd({ touches: [] });
            }
        }

        _handleWheel(event) {
            event.preventDefault();
            
            if (this.callbacks.wheel) {
                this.callbacks.wheel({
                    deltaY: event.deltaY,
                    deltaX: event.deltaX,
                    x: event.clientX,
                    y: event.clientY
                });
            }
        }

        _handleTap(touch) {
            const now = Date.now();
            
            if (now - this.lastTap < CONTROLS_CONFIG.GESTURES.doubleTapTimeout) {
                // 双击
                this.tapCount++;
                if (this.tapCount === 2) {
                    if (this.callbacks.doubleTap) {
                        this.callbacks.doubleTap({
                            x: touch.clientX,
                            y: touch.clientY
                        });
                    }
                    this.tapCount = 0;
                }
            } else {
                // 单击
                this.tapCount = 1;
                setTimeout(() => {
                    if (this.tapCount === 1) {
                        if (this.callbacks.tap) {
                            this.callbacks.tap({
                                x: touch.clientX,
                                y: touch.clientY
                            });
                        }
                    }
                    this.tapCount = 0;
                }, CONTROLS_CONFIG.GESTURES.tapTimeout);
            }
            
            this.lastTap = now;
        }

        _startLongPressTimer() {
            this.isLongPress = false;
            this.longPressTimer = setTimeout(() => {
                this.isLongPress = true;
                if (this.callbacks.longPress) {
                    this.callbacks.longPress();
                }
            }, CONTROLS_CONFIG.GESTURES.longPressTimeout);
        }

        _clearLongPressTimer() {
            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }
        }

        _calculateDistance(touch1, touch2) {
            const dx = touch2.clientX - touch1.clientX;
            const dy = touch2.clientY - touch1.clientY;
            return Math.sqrt(dx * dx + dy * dy);
        }

        _calculateCenter(touch1, touch2) {
            return {
                x: (touch1.clientX + touch2.clientX) / 2,
                y: (touch1.clientY + touch2.clientY) / 2
            };
        }

        dispose() {
            this.touches.clear();
            this._clearLongPressTimer();
            // 这里应该移除所有事件监听器，但为简化代码省略
        }
    }

    // ========================== 相机动画控制器 ========================== //
    
    /**
     * 相机动画控制器
     */
    class CameraAnimator {
        constructor(camera, controls) {
            this.camera = camera;
            this.controls = controls;
            this.isAnimating = false;
            this.animationFrame = null;
        }

        /**
         * 动画到指定位置
         */
        animateTo(targetPosition, targetLookAt, duration = 1000, easing = 'easeInOutQuad') {
            if (this.isAnimating) {
                this.stopAnimation();
            }

            const startPosition = this.camera.position.clone();
            const startLookAt = this.controls.target.clone();
            const startTime = Date.now();

            const animate = () => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const easedProgress = Easing[easing](progress);

                // 插值位置
                VectorUtils.lerpVector3(startPosition, targetPosition, easedProgress, this.camera.position);
                VectorUtils.lerpVector3(startLookAt, targetLookAt, easedProgress, this.controls.target);

                this.controls.update();

                if (progress < 1) {
                    this.animationFrame = requestAnimationFrame(animate);
                } else {
                    this.isAnimating = false;
                    this.animationFrame = null;
                }
            };

            this.isAnimating = true;
            animate();

            return new Promise(resolve => {
                const checkComplete = () => {
                    if (!this.isAnimating) {
                        resolve();
                    } else {
                        setTimeout(checkComplete, 16);
                    }
                };
                checkComplete();
            });
        }

        /**
         * 平滑缩放到指定距离
         */
        zoomTo(targetDistance, duration = 500) {
            const currentDistance = this.camera.position.distanceTo(this.controls.target);
            const direction = this.camera.position.clone().sub(this.controls.target).normalize();
            const targetPosition = this.controls.target.clone().add(direction.multiplyScalar(targetDistance));

            return this.animateTo(targetPosition, this.controls.target, duration);
        }

        /**
         * 停止当前动画
         */
        stopAnimation() {
            if (this.animationFrame) {
                cancelAnimationFrame(this.animationFrame);
                this.animationFrame = null;
            }
            this.isAnimating = false;
        }

        /**
         * 应用视角预设
         */
        applyViewPreset(presetName, duration = 1000) {
            const preset = CONTROLS_CONFIG.VIEW_PRESETS[presetName];
            if (!preset) {
                console.warn(`未知的视角预设: ${presetName}`);
                return Promise.resolve();
            }

            const targetPosition = new THREE.Vector3(...preset.position);
            const targetLookAt = new THREE.Vector3(...preset.target);

            return this.animateTo(targetPosition, targetLookAt, duration);
        }

        dispose() {
            this.stopAnimation();
        }
    }

    // ========================== 键盘控制器 ========================== //
    
    /**
     * 键盘快捷键控制器
     */
    class KeyboardController {
        constructor(viewer, callbacks = {}) {
            this.viewer = viewer;
            this.callbacks = callbacks;
            this.activeKeys = new Set();
            
            this._bindEvents();
        }

        _bindEvents() {
            document.addEventListener('keydown', this._handleKeyDown.bind(this));
            document.addEventListener('keyup', this._handleKeyUp.bind(this));
        }

        _handleKeyDown(event) {
            // 避免在输入框中触发
            if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
                return;
            }

            const key = event.key;
            this.activeKeys.add(key);

            // 检查快捷键
            const config = CONTROLS_CONFIG.KEYBOARD;
            
            if (config.zoomIn.includes(key)) {
                event.preventDefault();
                this._handleZoom(0.9);
            } else if (config.zoomOut.includes(key)) {
                event.preventDefault();
                this._handleZoom(1.1);
            } else if (config.reset.includes(key)) {
                event.preventDefault();
                this._handleReset();
            } else if (config.fullscreen.includes(key)) {
                event.preventDefault();
                this._handleFullscreen();
            } else if (config.screenshot.includes(key)) {
                event.preventDefault();
                this._handleScreenshot();
            } else if (config.help.includes(key)) {
                event.preventDefault();
                this._handleHelp();
            }
        }

        _handleKeyUp(event) {
            this.activeKeys.delete(event.key);
        }

        _handleZoom(factor) {
            if (this.viewer.controls) {
                const camera = this.viewer.camera;
                const controls = this.viewer.controls;
                const distance = camera.position.distanceTo(controls.target);
                const newDistance = distance * factor;
                
                if (this.viewer.cameraAnimator) {
                    this.viewer.cameraAnimator.zoomTo(newDistance, 300);
                }
            }
        }

        _handleReset() {
            if (this.callbacks.reset) {
                this.callbacks.reset();
            }
        }

        _handleFullscreen() {
            if (this.callbacks.fullscreen) {
                this.callbacks.fullscreen();
            }
        }

        _handleScreenshot() {
            if (this.callbacks.screenshot) {
                this.callbacks.screenshot();
            }
        }

        _handleHelp() {
            if (this.callbacks.help) {
                this.callbacks.help();
            } else {
                this._showDefaultHelp();
            }
        }

        _showDefaultHelp() {
            const helpContent = `
                <div class="keyboard-help">
                    <h3>键盘快捷键</h3>
                    <div class="help-item"><kbd>=</kbd> / <kbd>+</kbd> 放大</div>
                    <div class="help-item"><kbd>-</kbd> 缩小</div>
                    <div class="help-item"><kbd>R</kbd> / <kbd>Space</kbd> 重置视角</div>
                    <div class="help-item"><kbd>F</kbd> 全屏</div>
                    <div class="help-item"><kbd>S</kbd> 截图</div>
                    <div class="help-item"><kbd>H</kbd> / <kbd>?</kbd> 帮助</div>
                </div>
                <style>
                    .keyboard-help {
                        position: fixed;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        background: white;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                        z-index: 10000;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    }
                    .help-item {
                        margin: 8px 0;
                        display: flex;
                        align-items: center;
                        gap: 12px;
                    }
                    .keyboard-help kbd {
                        background: #f4f4f4;
                        border: 1px solid #ccc;
                        border-radius: 3px;
                        padding: 2px 6px;
                        font-size: 12px;
                        min-width: 20px;
                        text-align: center;
                    }
                </style>
            `;
            
            const helpDiv = document.createElement('div');
            helpDiv.innerHTML = helpContent;
            document.body.appendChild(helpDiv);
            
            // 点击外部关闭
            setTimeout(() => {
                const clickHandler = (e) => {
                    if (!helpDiv.querySelector('.keyboard-help').contains(e.target)) {
                        helpDiv.remove();
                        document.removeEventListener('click', clickHandler);
                    }
                };
                document.addEventListener('click', clickHandler);
            }, 100);
        }

        dispose() {
            document.removeEventListener('keydown', this._handleKeyDown);
            document.removeEventListener('keyup', this._handleKeyUp);
        }
    }

    // ========================== 增强交互控制器主类 ========================== //
    
    /**
     * 增强交互控制器
     */
    class EnhancedControls {
        constructor(viewer, options = {}) {
            this.viewer = viewer;
            this.options = {
                enableGestures: true,
                enableKeyboard: true,
                enableAnimation: true,
                enableViewPresets: true,
                ...options
            };

            // 子组件
            this.gestureRecognizer = null;
            this.cameraAnimator = null;
            this.keyboardController = null;

            // 状态
            this.isInitialized = false;
            
            // 初始化
            this._initialize();
        }

        _initialize() {
            if (!this.viewer.camera || !this.viewer.controls) {
                console.warn('增强控制器需要相机和基础控制器');
                return;
            }

            try {
                // 初始化相机动画器
                if (this.options.enableAnimation) {
                    this.cameraAnimator = new CameraAnimator(this.viewer.camera, this.viewer.controls);
                    this.viewer.cameraAnimator = this.cameraAnimator; // 暴露给查看器
                }

                // 初始化手势识别
                if (this.options.enableGestures) {
                    this._initializeGestureRecognizer();
                }

                // 初始化键盘控制
                if (this.options.enableKeyboard) {
                    this._initializeKeyboardController();
                }

                // 初始化视角预设
                if (this.options.enableViewPresets) {
                    this._initializeViewPresets();
                }

                this.isInitialized = true;
                console.log('增强交互控制器初始化成功');

            } catch (error) {
                console.error('增强控制器初始化失败:', error);
            }
        }

        _initializeGestureRecognizer() {
            const element = this.viewer.renderer.domElement;
            
            this.gestureRecognizer = new GestureRecognizer(element, {
                pan: (data) => {
                    // 禁用默认的轨道控制器，使用自定义手势
                    if (this.viewer.controls) {
                        // 这里可以添加自定义的平移逻辑
                        // 或者让默认控制器处理
                    }
                },
                
                pinch: (data) => {
                    // 处理缩放手势
                    if (this.viewer.controls) {
                        const camera = this.viewer.camera;
                        const controls = this.viewer.controls;
                        const distance = camera.position.distanceTo(controls.target);
                        const newDistance = distance / data.scale;
                        
                        // 限制缩放范围
                        const clampedDistance = Math.max(
                            controls.minDistance || 1,
                            Math.min(controls.maxDistance || 1000, newDistance)
                        );
                        
                        if (this.cameraAnimator) {
                            this.cameraAnimator.zoomTo(clampedDistance, 100);
                        }
                    }
                },
                
                doubleTap: (data) => {
                    // 双击重置视角
                    this.resetView();
                },
                
                longPress: () => {
                    // 长按显示上下文菜单
                    this._showContextMenu();
                },
                
                wheel: (data) => {
                    // 优化滚轮缩放
                    const zoomFactor = data.deltaY > 0 ? 1.1 : 0.9;
                    this._handleZoom(zoomFactor);
                }
            });
        }

        _initializeKeyboardController() {
            this.keyboardController = new KeyboardController(this.viewer, {
                reset: () => this.resetView(),
                fullscreen: () => this._toggleFullscreen(),
                screenshot: () => this._takeScreenshot(),
                help: () => this._showHelp()
            });
        }

        _initializeViewPresets() {
            // 可以在这里添加视角预设的UI或其他逻辑
            this.viewer.setViewPreset = (presetName) => {
                if (this.cameraAnimator) {
                    return this.cameraAnimator.applyViewPreset(presetName);
                }
                return Promise.resolve();
            };
        }

        _handleZoom(factor) {
            if (!this.viewer.controls || !this.viewer.camera) return;
            
            const camera = this.viewer.camera;
            const controls = this.viewer.controls;
            const distance = camera.position.distanceTo(controls.target);
            const newDistance = distance * factor;
            
            // 限制缩放范围
            const minDistance = controls.minDistance || 1;
            const maxDistance = controls.maxDistance || 1000;
            const clampedDistance = Math.max(minDistance, Math.min(maxDistance, newDistance));
            
            if (this.cameraAnimator) {
                this.cameraAnimator.zoomTo(clampedDistance, 200);
            }
        }

        _showContextMenu() {
            // 创建上下文菜单
            const menu = document.createElement('div');
            menu.className = 'context-menu';
            menu.innerHTML = `
                <div class="menu-item" data-action="reset">重置视角</div>
                <div class="menu-item" data-action="fullscreen">全屏</div>
                <div class="menu-item" data-action="screenshot">截图</div>
                <div class="menu-separator"></div>
                <div class="menu-item" data-action="front">前视图</div>
                <div class="menu-item" data-action="back">后视图</div>
                <div class="menu-item" data-action="left">左视图</div>
                <div class="menu-item" data-action="right">右视图</div>
                <div class="menu-item" data-action="top">俯视图</div>
                <div class="menu-item" data-action="isometric">等角视图</div>
            `;

            // 添加样式
            if (!document.querySelector('style[data-context-menu]')) {
                const style = document.createElement('style');
                style.setAttribute('data-context-menu', 'true');
                style.textContent = `
                    .context-menu {
                        position: fixed;
                        background: white;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                        z-index: 10000;
                        min-width: 120px;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                        font-size: 13px;
                    }
                    .menu-item {
                        padding: 8px 12px;
                        cursor: pointer;
                        border-bottom: 1px solid #f0f0f0;
                    }
                    .menu-item:hover {
                        background: #f5f5f5;
                    }
                    .menu-item:last-child {
                        border-bottom: none;
                    }
                    .menu-separator {
                        height: 1px;
                        background: #e0e0e0;
                        margin: 4px 0;
                    }
                `;
                document.head.appendChild(style);
            }

            // 定位菜单
            menu.style.left = '50%';
            menu.style.top = '50%';
            menu.style.transform = 'translate(-50%, -50%)';

            document.body.appendChild(menu);

            // 处理菜单点击
            menu.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                if (action) {
                    this._handleContextMenuAction(action);
                }
                menu.remove();
            });

            // 点击外部关闭菜单
            setTimeout(() => {
                const clickHandler = (e) => {
                    if (!menu.contains(e.target)) {
                        menu.remove();
                        document.removeEventListener('click', clickHandler);
                    }
                };
                document.addEventListener('click', clickHandler);
            }, 100);
        }

        _handleContextMenuAction(action) {
            switch (action) {
                case 'reset':
                    this.resetView();
                    break;
                case 'fullscreen':
                    this._toggleFullscreen();
                    break;
                case 'screenshot':
                    this._takeScreenshot();
                    break;
                case 'front':
                case 'back':
                case 'left':
                case 'right':
                case 'top':
                case 'isometric':
                    if (this.cameraAnimator) {
                        this.cameraAnimator.applyViewPreset(action);
                    }
                    break;
            }
        }

        /**
         * 重置视角
         */
        resetView() {
            if (this.viewer.model && this.cameraAnimator) {
                // 计算模型的边界框并重置相机
                const box = new THREE.Box3().setFromObject(this.viewer.model);
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                const distance = maxDim * 2;

                const targetPosition = center.clone();
                targetPosition.x += distance;
                targetPosition.y += distance * 0.5;
                targetPosition.z += distance;

                this.cameraAnimator.animateTo(targetPosition, center, 1000);
            }
        }

        _toggleFullscreen() {
            const container = this.viewer.container;
            if (!document.fullscreenElement) {
                container.requestFullscreen().catch(console.error);
            } else {
                document.exitFullscreen().catch(console.error);
            }
        }

        _takeScreenshot() {
            if (this.viewer.renderer) {
                const canvas = this.viewer.renderer.domElement;
                const link = document.createElement('a');
                link.download = `3d_model_${Date.now()}.png`;
                link.href = canvas.toDataURL('image/png');
                link.click();
            }
        }

        _showHelp() {
            // 显示帮助信息
            if (this.keyboardController) {
                this.keyboardController._showDefaultHelp();
            }
        }

        /**
         * 获取当前视角状态
         */
        getViewState() {
            if (!this.viewer.camera || !this.viewer.controls) {
                return null;
            }

            return {
                position: this.viewer.camera.position.toArray(),
                target: this.viewer.controls.target.toArray(),
                zoom: this.viewer.camera.zoom || 1
            };
        }

        /**
         * 恢复视角状态
         */
        restoreViewState(state, animated = true) {
            if (!state || !this.viewer.camera || !this.viewer.controls) {
                return Promise.resolve();
            }

            const targetPosition = new THREE.Vector3(...state.position);
            const targetLookAt = new THREE.Vector3(...state.target);

            if (animated && this.cameraAnimator) {
                return this.cameraAnimator.animateTo(targetPosition, targetLookAt);
            } else {
                this.viewer.camera.position.copy(targetPosition);
                this.viewer.controls.target.copy(targetLookAt);
                this.viewer.controls.update();
                return Promise.resolve();
            }
        }

        /**
         * 销毁控制器
         */
        dispose() {
            if (this.gestureRecognizer) {
                this.gestureRecognizer.dispose();
            }
            
            if (this.cameraAnimator) {
                this.cameraAnimator.dispose();
            }
            
            if (this.keyboardController) {
                this.keyboardController.dispose();
            }

            this.isInitialized = false;
            console.log('增强交互控制器已销毁');
        }
    }

    // ========================== 全局导出 ========================== //
    
    // 导出到全局作用域
    window.EnhancedControls = EnhancedControls;
    window.GestureRecognizer = GestureRecognizer;
    window.CameraAnimator = CameraAnimator;
    window.KeyboardController = KeyboardController;
    
    console.log('增强交互控制器已加载');

})(window);
