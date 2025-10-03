/*!
 * Three.js模型查看器 - 高性能3D渲染解决方案
 * 替代Plotly，提供WebGL原生性能和更好的用户体验
 * 
 * 特性：
 * - GLB模型加载和渲染
 * - LOD多精度级别支持
 * - 渐进式加载体验
 * - 高级材质和光照
 * - 响应式设计
 * - 触摸和鼠标交互
 * 
 * 依赖：Three.js r158+
 * 作者：AI Assistant
 * 版本：v1.0
 * 日期：2024-09-25
 */

(function(window) {
    'use strict';

    // ========================== 核心常量 ========================== //
    
    const VIEWER_CONFIG = {
        // LOD级别配置
        LOD_LEVELS: {
            'preview': { priority: 1, autoLoad: true, description: '预览级别 - 快速加载' },
            'detail': { priority: 2, autoLoad: false, description: '详细级别 - 平衡质量' },
            'full': { priority: 3, autoLoad: false, description: '完整级别 - 最高质量' }
        },
        
        // 渲染配置
        RENDERER: {
            antialias: true,
            alpha: true,
            powerPreference: 'high-performance',
            preserveDrawingBuffer: false
        },
        
        // 相机配置
        CAMERA: {
            fov: 45,
            near: 0.1,
            far: 2000,
            position: { x: 100, y: 50, z: 100 }
        },
        
        // 控制器配置
        CONTROLS: {
            enableDamping: true,
            dampingFactor: 0.05,
            enableZoom: true,
            enableRotate: true,
            enablePan: true,
            maxPolarAngle: Math.PI,
            minDistance: 5,
            maxDistance: 500
        },
        
        // 光照配置 - 四光源照明系统
        LIGHTING: {
            ambient: { color: 0x404040, intensity: 0.6 },  // 原始环境光
            directional: { 
                color: 0xffffff, 
                intensity: 1.0,  // 原始主光源
                position: { x: 10, y: 10, z: 5 }
            },
            // 对称光源 - 相反方向同样亮度
            opposite: {
                color: 0xffffff,
                intensity: 1.0,  // 与主光源相同强度
                position: { x: -10, y: -10, z: -5 }  // 完全相反方向
            },
            // 垂直上光源 - 从上方极远距离照射
            verticalTop: {
                color: 0xffffff,
                intensity: 0.125,  // 亮度再次降低一半
                position: { x: 0, y: 100, z: 0 }  // 距离再拉开一倍
            },
            // 垂直下光源 - 从下方极远距离照射
            verticalBottom: {
                color: 0xffffff,
                intensity: 0.125,  // 亮度再次降低一半
                position: { x: 0, y: -100, z: 0 }  // 距离再拉开一倍
            },
            hemisphere: {
                skyColor: 0xffffbb,
                groundColor: 0x080820,
                intensity: 0.3  // 原始半球光
            }
        }
    };

    // ========================== 工具函数 ========================== //
    
    /**
     * 检查Three.js依赖
     */
    function checkThreeDependencies() {
        const missing = [];
        
        if (typeof THREE === 'undefined') {
            missing.push('Three.js');
        } else {
            // 检查必需的Three.js组件
            const required = ['Scene', 'PerspectiveCamera', 'WebGLRenderer', 'OrbitControls', 'GLTFLoader'];
            required.forEach(component => {
                if (!THREE[component] && !window[component]) {
                    missing.push(`THREE.${component}`);
                }
            });
        }
        
        return {
            satisfied: missing.length === 0,
            missing: missing
        };
    }

    /**
     * 创建错误信息显示
     */
    function createErrorDisplay(container, message, suggestions = []) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'three-viewer-error';
        errorDiv.innerHTML = `
            <div class="error-content">
                <div class="error-icon">⚠️</div>
                <div class="error-title">3D渲染器加载失败</div>
                <div class="error-message">${message}</div>
                ${suggestions.length > 0 ? `
                    <div class="error-suggestions">
                        <strong>建议：</strong>
                        <ul>
                            ${suggestions.map(s => `<li>${s}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
        
        // 添加样式
        const style = document.createElement('style');
        style.textContent = `
            .three-viewer-error {
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100%;
                min-height: 300px;
                background: #f8f9fa;
                border: 2px dashed #dee2e6;
                border-radius: 8px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            .error-content {
                text-align: center;
                max-width: 400px;
                padding: 20px;
            }
            .error-icon {
                font-size: 48px;
                margin-bottom: 16px;
            }
            .error-title {
                font-size: 18px;
                font-weight: 600;
                color: #495057;
                margin-bottom: 8px;
            }
            .error-message {
                color: #6c757d;
                margin-bottom: 16px;
                line-height: 1.5;
            }
            .error-suggestions {
                text-align: left;
                background: white;
                padding: 12px;
                border-radius: 4px;
                border-left: 3px solid #ffc107;
            }
            .error-suggestions ul {
                margin: 8px 0 0 0;
                padding-left: 20px;
            }
            .error-suggestions li {
                margin: 4px 0;
                color: #495057;
            }
        `;
        
        container.appendChild(style);
        container.appendChild(errorDiv);
    }

    /**
     * 创建加载指示器
     */
    function createLoadingIndicator() {
        const loader = document.createElement('div');
        loader.className = 'three-viewer-loader';
        loader.innerHTML = `
            <div class="loader-content">
                <div class="loader-spinner"></div>
                <div class="loader-text">正在加载3D模型...</div>
                <div class="loader-progress">
                    <div class="progress-bar">
                        <div class="progress-fill"></div>
                    </div>
                    <div class="progress-text">0%</div>
                </div>
            </div>
        `;
        
        // 添加加载动画样式
        const style = document.createElement('style');
        style.textContent = `
            .three-viewer-loader {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(248, 249, 250, 0.95);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            .loader-content {
                text-align: center;
                max-width: 200px;
            }
            .loader-spinner {
                width: 48px;
                height: 48px;
                border: 4px solid #e9ecef;
                border-top: 4px solid #007bff;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 16px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .loader-text {
                font-size: 16px;
                font-weight: 500;
                color: #495057;
                margin-bottom: 16px;
            }
            .progress-bar {
                width: 100%;
                height: 8px;
                background: #e9ecef;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 8px;
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #007bff, #0056b3);
                width: 0%;
                transition: width 0.3s ease;
                border-radius: 4px;
            }
            .progress-text {
                font-size: 12px;
                color: #6c757d;
            }
        `;
        
        if (!document.querySelector('style[data-three-loader]')) {
            style.setAttribute('data-three-loader', 'true');
            document.head.appendChild(style);
        }
        
        return loader;
    }

    // ========================== 依赖检查工具函数 ========================== //
    
    /**
     * 检查Three.js相关依赖是否可用
     * @returns {Object} 检查结果 { satisfied: boolean, missing: string[] }
     */
    function checkThreeDependencies() {
        const missing = [];
        
        // 检查THREE全局对象
        if (typeof THREE === 'undefined') {
            missing.push('Three.js核心库');
        } else {
            // 检查必要的Three.js组件
            if (!THREE.WebGLRenderer) missing.push('WebGL渲染器');
            if (!THREE.PerspectiveCamera) missing.push('透视相机');
            if (!THREE.Scene) missing.push('场景对象');
            if (!THREE.OrbitControls) missing.push('轨道控制器');
            if (!THREE.GLTFLoader) missing.push('GLTF加载器');
        }
        
        // 检查WebGL支持
        const canvas = document.createElement('canvas');
        const webglContext = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (!webglContext) {
            missing.push('WebGL支持');
        }
        
        return {
            satisfied: missing.length === 0,
            missing: missing
        };
    }

    // ========================== Three.js模型查看器类 ========================== //
    
    /**
     * Three.js模型查看器主类
     */
    class ThreeModelViewer {
        /**
         * 构造函数
         * @param {HTMLElement|string} container - 容器元素或选择器
         * @param {Object} options - 配置选项
         */
        constructor(container, options = {}) {
            // 初始化容器（必须先初始化）
            this.container = typeof container === 'string' ? 
                document.querySelector(container) : container;
                
            if (!this.container) {
                throw new Error('容器元素未找到');
            }
            
            // 依赖检查
            const deps = checkThreeDependencies();
            if (!deps.satisfied) {
                const suggestions = [
                    '确保Three.js库已正确加载',
                    '检查网络连接是否正常',
                    '尝试刷新页面重新加载'
                ];
                this._showError(`缺少必要的依赖: ${deps.missing.join(', ')}`, suggestions);
                return;
            }
            
            // 配置选项
            this.options = {
                ...VIEWER_CONFIG,
                ...options
            };
            
            // 初始化状态
            this.scene = null;
            this.camera = null;
            this.renderer = null;
            this.controls = null;
            this.model = null;
            this.lights = {};
            this.currentLOD = 'preview';
            this.loadingManager = null;
            this.isLoading = false;
            this.loadingIndicator = null;
            
            // 事件监听器存储
            this.eventListeners = new Map();
            
            // 初始化查看器
            this._initialize();
        }

        /**
         * 初始化Three.js场景
         * @private
         */
        _initialize() {
            try {
                // 设置容器样式
                this._setupContainer();
                
                // 创建场景
                this._createScene();
                
                // 创建相机
                this._createCamera();
                
                // 创建渲染器
                this._createRenderer();
                
                // 创建控制器
                this._createControls();
                
                // 设置光照
                this._setupLighting();
                
                // 设置加载管理器
                this._setupLoadingManager();
                
                // 绑定事件
                this._bindEvents();
                
                // 开始渲染循环
                this._startRenderLoop();
                
                console.log('Three.js模型查看器初始化成功');
                this._emit('initialized');
                
            } catch (error) {
                console.error('Three.js初始化失败:', error);
                this._showError(`初始化失败: ${error.message}`, [
                    '检查浏览器是否支持WebGL',
                    '尝试更新浏览器版本',
                    '检查GPU驱动是否最新'
                ]);
            }
        }

        /**
         * 设置容器样式
         * @private
         */
        _setupContainer() {
            const style = this.container.style;
            style.position = style.position || 'relative';
            style.overflow = 'hidden';
            
            // 确保容器有尺寸
            if (!this.container.offsetWidth || !this.container.offsetHeight) {
                style.width = style.width || '100%';
                style.height = style.height || '400px';
            }
        }

        /**
         * 创建Three.js场景
         * @private
         */
        _createScene() {
            this.scene = new THREE.Scene();
            this.scene.background = new THREE.Color(0xf8f9fa);
        }

        /**
         * 创建相机
         * @private
         */
        _createCamera() {
            const aspect = this.container.offsetWidth / this.container.offsetHeight;
            this.camera = new THREE.PerspectiveCamera(
                this.options.CAMERA.fov,
                aspect,
                this.options.CAMERA.near,
                this.options.CAMERA.far
            );
            
            const pos = this.options.CAMERA.position;
            this.camera.position.set(pos.x, pos.y, pos.z);
        }

        /**
         * 创建WebGL渲染器
         * @private
         */
        _createRenderer() {
            this.renderer = new THREE.WebGLRenderer(this.options.RENDERER);
            this.renderer.setSize(this.container.offsetWidth, this.container.offsetHeight);
            this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            
            // 启用阴影
            this.renderer.shadowMap.enabled = true;
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            
            // 色彩管理
            this.renderer.outputColorSpace = THREE.SRGBColorSpace;
            
            this.container.appendChild(this.renderer.domElement);
        }

        /**
         * 创建轨道控制器
         * @private
         */
        _createControls() {
            // 检查OrbitControls是否可用
            const OrbitControls = THREE.OrbitControls || window.OrbitControls;
            if (!OrbitControls) {
                throw new Error('OrbitControls未找到');
            }
            
            this.controls = new OrbitControls(this.camera, this.renderer.domElement);
            
            // 应用配置
            Object.assign(this.controls, this.options.CONTROLS);
            
            // 控制器事件
            this.controls.addEventListener('change', () => {
                this._emit('camera-change');
            });
        }

        /**
         * 设置场景光照
         * @private
         */
        _setupLighting() {
            const config = this.options.LIGHTING;
            
            // 环境光 - 原始配置
            this.lights.ambient = new THREE.AmbientLight(
                config.ambient.color, 
                config.ambient.intensity
            );
            this.scene.add(this.lights.ambient);
            
            // 主方向光 - 原始配置
            this.lights.directional = new THREE.DirectionalLight(
                config.directional.color,
                config.directional.intensity
            );
            const pos = config.directional.position;
            this.lights.directional.position.set(pos.x, pos.y, pos.z);
            this.lights.directional.castShadow = true;
            
            // 优化阴影设置
            const shadowMap = this.lights.directional.shadow.mapSize;
            shadowMap.width = 2048;
            shadowMap.height = 2048;
            this.scene.add(this.lights.directional);
            
            // 对称光源 - 相反方向同样强度
            this.lights.opposite = new THREE.DirectionalLight(
                config.opposite.color,
                config.opposite.intensity
            );
            const oppPos = config.opposite.position;
            this.lights.opposite.position.set(oppPos.x, oppPos.y, oppPos.z);
            this.lights.opposite.castShadow = false;  // 对称光不投射阴影，避免冲突
            this.scene.add(this.lights.opposite);
            
            // 垂直上光源 - 从上方远距离照射
            this.lights.verticalTop = new THREE.DirectionalLight(
                config.verticalTop.color,
                config.verticalTop.intensity
            );
            const vertTopPos = config.verticalTop.position;
            this.lights.verticalTop.position.set(vertTopPos.x, vertTopPos.y, vertTopPos.z);
            this.lights.verticalTop.castShadow = false;  // 垂直光不投射阴影，避免冲突
            this.scene.add(this.lights.verticalTop);
            
            // 垂直下光源 - 从下方照射
            this.lights.verticalBottom = new THREE.DirectionalLight(
                config.verticalBottom.color,
                config.verticalBottom.intensity
            );
            const vertBottomPos = config.verticalBottom.position;
            this.lights.verticalBottom.position.set(vertBottomPos.x, vertBottomPos.y, vertBottomPos.z);
            this.lights.verticalBottom.castShadow = false;  // 垂直光不投射阴影，避免冲突
            this.scene.add(this.lights.verticalBottom);
            
            // 半球光 - 原始配置
            this.lights.hemisphere = new THREE.HemisphereLight(
                config.hemisphere.skyColor,
                config.hemisphere.groundColor,
                config.hemisphere.intensity
            );
            this.scene.add(this.lights.hemisphere);
            
            console.log('🔄 四光源照明系统设置完成:', {
                ambient: config.ambient.intensity,
                directional: `${config.directional.intensity} at (${pos.x},${pos.y},${pos.z})`,
                opposite: `${config.opposite.intensity} at (${oppPos.x},${oppPos.y},${oppPos.z})`,
                verticalTop: `${config.verticalTop.intensity} at (${vertTopPos.x},${vertTopPos.y},${vertTopPos.z})`,
                verticalBottom: `${config.verticalBottom.intensity} at (${vertBottomPos.x},${vertBottomPos.y},${vertBottomPos.z})`,
                hemisphere: config.hemisphere.intensity
            });
        }

        /**
         * 设置加载管理器
         * @private
         */
        _setupLoadingManager() {
            this.loadingManager = new THREE.LoadingManager();
            
            this.loadingManager.onStart = (url, itemsLoaded, itemsTotal) => {
                this._showLoading(true);
                this._emit('load-start', { url, itemsLoaded, itemsTotal });
            };
            
            this.loadingManager.onProgress = (url, itemsLoaded, itemsTotal) => {
                const progress = (itemsLoaded / itemsTotal) * 100;
                this._updateLoadingProgress(progress);
                this._emit('load-progress', { url, itemsLoaded, itemsTotal, progress });
            };
            
            this.loadingManager.onLoad = () => {
                this._showLoading(false);
                this._emit('load-complete');
            };
            
            this.loadingManager.onError = (url) => {
                this._showLoading(false);
                this._emit('load-error', { url });
            };
        }

        /**
         * 绑定窗口事件
         * @private
         */
        _bindEvents() {
            // 窗口大小变化
            const resizeHandler = () => this._handleResize();
            window.addEventListener('resize', resizeHandler);
            this._storeEventListener('resize', window, resizeHandler);
            
            // 容器观察器（如果支持）
            if (window.ResizeObserver) {
                const resizeObserver = new ResizeObserver(entries => {
                    this._handleResize();
                });
                resizeObserver.observe(this.container);
                this.resizeObserver = resizeObserver;
            }
        }

        /**
         * 存储事件监听器以便清理
         * @private
         */
        _storeEventListener(name, element, handler) {
            if (!this.eventListeners.has(name)) {
                this.eventListeners.set(name, []);
            }
            this.eventListeners.get(name).push({ element, handler });
        }

        /**
         * 处理窗口大小变化
         * @private
         */
        _handleResize() {
            if (!this.camera || !this.renderer) return;
            
            const width = this.container.offsetWidth;
            const height = this.container.offsetHeight;
            
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
            
            this.renderer.setSize(width, height);
        }

        /**
         * 开始渲染循环
         * @private
         */
        _startRenderLoop() {
            const animate = () => {
                requestAnimationFrame(animate);
                
                // 更新控制器
                if (this.controls) {
                    this.controls.update();
                }
                
                // 渲染场景
                this.renderer.render(this.scene, this.camera);
            };
            
            animate();
        }

        /**
         * 显示错误信息
         * @private
         */
        _showError(message, suggestions = []) {
            this.container.innerHTML = '';
            createErrorDisplay(this.container, message, suggestions);
        }

        /**
         * 显示/隐藏加载指示器
         * @private
         */
        _showLoading(show) {
            if (show && !this.loadingIndicator) {
                this.loadingIndicator = createLoadingIndicator();
                this.container.appendChild(this.loadingIndicator);
            } else if (!show && this.loadingIndicator) {
                this.loadingIndicator.remove();
                this.loadingIndicator = null;
            }
        }

        /**
         * 更新加载进度
         * @private
         */
        _updateLoadingProgress(progress) {
            if (!this.loadingIndicator) return;
            
            const progressFill = this.loadingIndicator.querySelector('.progress-fill');
            const progressText = this.loadingIndicator.querySelector('.progress-text');
            
            if (progressFill) {
                progressFill.style.width = `${progress}%`;
            }
            if (progressText) {
                progressText.textContent = `${Math.round(progress)}%`;
            }
        }

        /**
         * 触发自定义事件
         * @private
         */
        _emit(eventName, data = {}) {
            const event = new CustomEvent(`threeviewer:${eventName}`, {
                detail: { viewer: this, ...data }
            });
            this.container.dispatchEvent(event);
        }

        // ========================== 公共API方法 ========================== //
        
        /**
         * 加载GLB模型
         * @param {string|Object} source - 模型URL或配置对象
         * @param {Object} options - 加载选项
         * @returns {Promise} 加载Promise
         */
        async loadModel(source, options = {}) {
            if (this.isLoading) {
                console.warn('模型正在加载中，请稍候');
                return;
            }
            
            this.isLoading = true;
            
            try {
                // 解析源参数
                const modelConfig = typeof source === 'string' ? 
                    { url: source } : source;
                
                // 检查GLTFLoader
                const GLTFLoader = THREE.GLTFLoader || window.GLTFLoader;
                if (!GLTFLoader) {
                    throw new Error('GLTFLoader未找到');
                }
                
                const loader = new GLTFLoader(this.loadingManager);
                
                // 使用缓存加载模型
                let gltf;
                if (window.glbCacheManager && !options.skipCache) {
                    console.log('🔄 使用缓存加载器...');
                    gltf = await window.glbCacheManager.loadModelWithCache(
                        modelConfig.url, 
                        loader, 
                        options
                    );
                } else {
                    // 回退到直接加载
                    gltf = await new Promise((resolve, reject) => {
                        loader.load(
                            modelConfig.url,
                            resolve,
                            undefined,
                            reject
                        );
                    });
                }
                
                // 修复材质问题 - 确保所有材质都有正确的属性
                if (gltf.scene) {
                    gltf.scene.traverse((child) => {
                        if (child.isMesh && child.material) {
                            // 确保材质可见性
                            child.material.transparent = false;
                            child.material.opacity = 1.0;
                            child.material.visible = true;
                            
                            // 如果材质是黑色，设置一个默认颜色
                            if (child.material.color && 
                                child.material.color.r === 0 && 
                                child.material.color.g === 0 && 
                                child.material.color.b === 0) {
                                child.material.color.setHex(0xcccccc); // 设置为灰色
                                console.warn('检测到黑色材质，已修复为灰色');
                            }
                            
                            // 强制材质更新
                            child.material.needsUpdate = true;
                        }
                    });
                }
                
                // 移除旧模型
                if (this.model) {
                    this.scene.remove(this.model);
                }
                
                // 添加新模型
                this.model = gltf.scene;
                this.scene.add(this.model);
                
                // 设置模型属性
                this.model.castShadow = true;
                this.model.receiveShadow = true;
                
                // 遍历所有网格设置阴影
                this.model.traverse((child) => {
                    if (child.isMesh) {
                        child.castShadow = true;
                        child.receiveShadow = true;
                    }
                });
                
                // 自动适配相机
                this._fitCameraToModel();
                
                this.isLoading = false;
                this._emit('model-loaded', { model: this.model, gltf });
                
                console.log('GLB模型加载成功', {
                    lodLevel: options?.lodLevel || 'unknown',
                    materials: this._countMaterials(this.model),
                    meshes: this._countMeshes(this.model),
                    hasColor: this._checkMaterialColors(this.model)
                });
                
            } catch (error) {
                this.isLoading = false;
                console.error('GLB模型加载失败:', error);
                this._emit('model-error', { error });
                throw error;
            }
        }

        /**
         * 自动适配相机到模型
         * @private
         */
        _fitCameraToModel() {
            if (!this.model) return;
            
            const box = new THREE.Box3().setFromObject(this.model);
            const size = box.getSize(new THREE.Vector3());
            const center = box.getCenter(new THREE.Vector3());
            
            // 计算合适的相机距离
            const maxDim = Math.max(size.x, size.y, size.z);
            const fov = this.camera.fov * (Math.PI / 180);
            const cameraDistance = maxDim / (2 * Math.tan(fov / 2)) * 1.5;
            
            // 设置相机位置
            this.camera.position.copy(center);
            this.camera.position.x += cameraDistance;
            this.camera.position.y += cameraDistance * 0.5;
            this.camera.position.z += cameraDistance;
            
            // 更新控制器目标
            this.controls.target.copy(center);
            this.controls.update();
            
            // 更新控制器距离限制
            this.controls.minDistance = maxDim * 0.1;
            this.controls.maxDistance = maxDim * 3;
        }

        /**
         * 销毁查看器，清理资源
         */
        dispose() {
            // 停止渲染
            if (this.renderer) {
                this.renderer.dispose();
            }
            
            // 清理控制器
            if (this.controls) {
                this.controls.dispose();
            }
            
            // 清理模型
            if (this.model) {
                this.scene.remove(this.model);
            }
            
            // 清理场景
            if (this.scene) {
                this.scene.clear();
            }
            
            // 清理事件监听器
            this.eventListeners.forEach((listeners, eventName) => {
                listeners.forEach(({ element, handler }) => {
                    element.removeEventListener(eventName, handler);
                });
            });
            this.eventListeners.clear();
            
            // 清理ResizeObserver
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
            }
            
            // 清理DOM
            if (this.loadingIndicator) {
                this.loadingIndicator.remove();
            }
            
            if (this.renderer && this.renderer.domElement) {
                this.renderer.domElement.remove();
            }
            
            console.log('Three.js查看器已销毁');
        }

        /**
         * 计算模型材质数量
         * @private
         */
        _countMaterials(model) {
            if (!model) return 0;
            let count = 0;
            model.traverse((child) => {
                if (child.isMesh && child.material) {
                    count++;
                }
            });
            return count;
        }

        /**
         * 计算模型网格数量
         * @private
         */
        _countMeshes(model) {
            if (!model) return 0;
            let count = 0;
            model.traverse((child) => {
                if (child.isMesh) {
                    count++;
                }
            });
            return count;
        }

        /**
         * 检查材质颜色
         * @private
         */
        _checkMaterialColors(model) {
            if (!model) return false;
            let hasNonBlackColor = false;
            model.traverse((child) => {
                if (child.isMesh && child.material && child.material.color) {
                    const color = child.material.color;
                    if (color.r > 0 || color.g > 0 || color.b > 0) {
                        hasNonBlackColor = true;
                    }
                }
            });
            return hasNonBlackColor;
        }
    }

    // ========================== 全局导出 ========================== //
    
    // 导出到全局作用域
    window.ThreeModelViewer = ThreeModelViewer;
    
    // 兼容AMD/CommonJS
    if (typeof define === 'function' && define.amd) {
        define([], () => ThreeModelViewer);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = ThreeModelViewer;
    }

})(window);
