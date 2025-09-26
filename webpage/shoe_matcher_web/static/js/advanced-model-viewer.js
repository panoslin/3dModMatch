/*!
 * 高级模型查看器 - 支持LOD和材质系统
 * 基于Three.js的专业级3D模型查看解决方案
 * 
 * 特性：
 * - 智能LOD级别管理和切换
 * - 高级PBR材质和后处理
 * - 性能优化和资源管理
 * - 实时质量调节
 * - 移动端优化
 * 
 * 作者：AI Assistant
 * 版本：v1.0
 * 日期：2024-09-25
 */

(function(window) {
    'use strict';

    // 检查基础查看器是否存在
    if (!window.ThreeModelViewer) {
        console.error('AdvancedModelViewer需要ThreeModelViewer作为基础');
        return;
    }

    // ========================== 高级配置 ========================== //
    
    const ADVANCED_CONFIG = {
        // LOD管理配置
        LOD_MANAGER: {
            // 自动切换阈值（基于相机距离）
            autoSwitchThresholds: {
                'full': 50,      // 距离小于50时使用full
                'detail': 150,   // 距离小于150时使用detail
                'preview': 500   // 其他情况使用preview
            },
            
            // 预加载策略
            preloadStrategy: {
                enabled: true,
                preloadNext: true,  // 预加载下一个级别
                cacheLimit: 3       // 最多缓存3个级别
            },
            
            // 切换动画
            transitionDuration: 500,  // 毫秒
            fadeInOut: true
        },
        
        // 材质增强
        MATERIALS: {
            // PBR材质配置
            pbr: {
                metalness: 0.1,
                roughness: 0.8,
                envMapIntensity: 1.0
            },
            
            // 鞋模专用材质预设
            shoePresets: {
                leather: {
                    color: 0x8B4513,
                    metalness: 0.0,
                    roughness: 0.7,
                    bumpScale: 0.02
                },
                rubber: {
                    color: 0x2F2F2F,
                    metalness: 0.0,
                    roughness: 0.9,
                    bumpScale: 0.01
                },
                fabric: {
                    color: 0x4A4A4A,
                    metalness: 0.0,
                    roughness: 0.85,
                    bumpScale: 0.015
                }
            }
        },
        
        // 性能优化
        PERFORMANCE: {
            // 渲染质量级别
            qualityLevels: {
                'low': {
                    pixelRatio: 1,
                    shadowMapSize: 512,
                    antialias: false,
                    postProcessing: false
                },
                'medium': {
                    pixelRatio: Math.min(window.devicePixelRatio, 1.5),
                    shadowMapSize: 1024,
                    antialias: true,
                    postProcessing: false
                },
                'high': {
                    pixelRatio: Math.min(window.devicePixelRatio, 2),
                    shadowMapSize: 2048,
                    antialias: true,
                    postProcessing: true
                }
            },
            
            // 自动质量调节
            autoQualityAdjust: {
                enabled: true,
                targetFPS: 30,
                adjustmentInterval: 2000  // 每2秒检查一次
            }
        }
    };

    // ========================== LOD管理器 ========================== //
    
    /**
     * LOD级别管理器
     */
    class LODManager {
        constructor(viewer, apiConfig) {
            this.viewer = viewer;
            this.apiConfig = apiConfig;
            this.currentLevel = 'preview';
            this.cache = new Map();
            this.isTransitioning = false;
            this.preloadQueue = [];
            
            // 绑定相机变化事件
            this.viewer.container.addEventListener('threeviewer:camera-change', 
                this._onCameraChange.bind(this));
        }

        /**
         * 初始化LOD系统
         */
        async initialize() {
            try {
                // 检查模型LOD状态
                const statusResponse = await fetch(
                    `/api/lod/${this.apiConfig.modelType}/${this.apiConfig.modelId}/status/`
                );
                
                if (!statusResponse.ok) {
                    throw new Error(`状态检查失败: ${statusResponse.status}`);
                }
                
                const statusData = await statusResponse.json();
                
                if (!statusData.success) {
                    throw new Error(statusData.message || 'LOD状态检查失败');
                }
                
                this.modelInfo = statusData.data;
                this.availableLevels = this.modelInfo.lod_levels || ['preview'];
                
                console.log('LOD管理器初始化成功:', this.availableLevels);
                
                // 加载初始级别
                await this.loadLevel('preview');
                
                // 开始预加载
                if (ADVANCED_CONFIG.LOD_MANAGER.preloadStrategy.enabled) {
                    this._startPreloading();
                }
                
            } catch (error) {
                console.error('LOD管理器初始化失败:', error);
                throw error;
            }
        }

        /**
         * 加载指定LOD级别
         */
        async loadLevel(level, options = {}) {
            if (this.isTransitioning && !options.force) {
                console.log('LOD切换进行中，跳过');
                return false;
            }
            
            if (!this.availableLevels.includes(level)) {
                console.warn(`LOD级别 ${level} 不可用`);
                return false;
            }
            
            // 检查缓存
            if (this.cache.has(level) && !options.force) {
                console.log(`使用缓存的LOD级别: ${level}`);
                await this._switchToLevel(level);
                return true;
            }
            
            try {
                this.isTransitioning = true;
                
                // 显示加载状态
                if (!options.silent) {
                    this.viewer._emit('lod-loading', { level });
                }
                
                // 请求GLB数据
                const response = await fetch(
                    `/api/lod/${this.apiConfig.modelType}/${this.apiConfig.modelId}/data/?lod=${level}&format=glb`,
                    {
                        headers: {
                            'If-None-Match': this._getETag(level)
                        }
                    }
                );
                
                if (response.status === 304) {
                    // 使用缓存的版本
                    console.log(`GLB文件未更改，使用缓存: ${level}`);
                    await this._switchToLevel(level);
                    return true;
                }
                
                if (!response.ok) {
                    throw new Error(`GLB加载失败: ${response.status} ${response.statusText}`);
                }
                
                // 保存ETag
                const etag = response.headers.get('ETag');
                if (etag) {
                    this._setETag(level, etag);
                }
                
                // 获取GLB数据
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                
                // 使用Three.js加载器加载
                await this.viewer.loadModel(url, { silent: options.silent });
                
                // 缓存结果
                this.cache.set(level, { url, timestamp: Date.now() });
                this._cleanupCache();
                
                // 切换到新级别
                await this._switchToLevel(level);
                
                console.log(`LOD级别 ${level} 加载成功`);
                
                if (!options.silent) {
                    this.viewer._emit('lod-loaded', { level });
                }
                
                return true;
                
            } catch (error) {
                console.error(`LOD级别 ${level} 加载失败:`, error);
                this.viewer._emit('lod-error', { level, error });
                return false;
                
            } finally {
                this.isTransitioning = false;
            }
        }

        /**
         * 切换到指定级别
         * @private
         */
        async _switchToLevel(level) {
            const oldLevel = this.currentLevel;
            this.currentLevel = level;
            
            // 触发切换事件
            this.viewer._emit('lod-switch', {
                from: oldLevel,
                to: level,
                levels: this.availableLevels
            });
            
            // 更新UI（如果有的话）
            this._updateUI();
        }

        /**
         * 相机变化处理
         * @private
         */
        _onCameraChange() {
            if (!ADVANCED_CONFIG.LOD_MANAGER.autoSwitchThresholds || this.isTransitioning) {
                return;
            }
            
            // 计算相机到模型的距离
            const distance = this._calculateCameraDistance();
            
            // 确定最佳LOD级别
            const optimalLevel = this._getOptimalLevel(distance);
            
            // 如果需要切换
            if (optimalLevel !== this.currentLevel) {
                console.log(`自动切换LOD: ${this.currentLevel} -> ${optimalLevel} (距离: ${distance.toFixed(1)})`);
                this.loadLevel(optimalLevel, { silent: true });
            }
        }

        /**
         * 计算相机距离
         * @private
         */
        _calculateCameraDistance() {
            if (!this.viewer.model || !this.viewer.camera) {
                return 100;
            }
            
            const box = new THREE.Box3().setFromObject(this.viewer.model);
            const center = box.getCenter(new THREE.Vector3());
            return this.viewer.camera.position.distanceTo(center);
        }

        /**
         * 获取最佳LOD级别
         * @private
         */
        _getOptimalLevel(distance) {
            const thresholds = ADVANCED_CONFIG.LOD_MANAGER.autoSwitchThresholds;
            
            for (const [level, threshold] of Object.entries(thresholds)) {
                if (this.availableLevels.includes(level) && distance < threshold) {
                    return level;
                }
            }
            
            return 'preview';  // 默认级别
        }

        /**
         * 开始预加载
         * @private
         */
        _startPreloading() {
            const strategy = ADVANCED_CONFIG.LOD_MANAGER.preloadStrategy;
            
            // 预加载下一个级别
            if (strategy.preloadNext) {
                const levelOrder = ['preview', 'detail', 'full'];
                const currentIndex = levelOrder.indexOf(this.currentLevel);
                
                if (currentIndex >= 0 && currentIndex < levelOrder.length - 1) {
                    const nextLevel = levelOrder[currentIndex + 1];
                    if (this.availableLevels.includes(nextLevel)) {
                        setTimeout(() => {
                            this.loadLevel(nextLevel, { silent: true });
                        }, 1000);
                    }
                }
            }
        }

        /**
         * 缓存管理
         * @private
         */
        _cleanupCache() {
            const limit = ADVANCED_CONFIG.LOD_MANAGER.preloadStrategy.cacheLimit;
            
            if (this.cache.size > limit) {
                // 清理最旧的缓存项
                const entries = Array.from(this.cache.entries())
                    .sort((a, b) => a[1].timestamp - b[1].timestamp);
                
                for (let i = 0; i < entries.length - limit; i++) {
                    const [level, data] = entries[i];
                    URL.revokeObjectURL(data.url);
                    this.cache.delete(level);
                    console.log(`清理缓存的LOD级别: ${level}`);
                }
            }
        }

        /**
         * ETag管理
         * @private
         */
        _getETag(level) {
            return localStorage.getItem(`lod_etag_${this.apiConfig.modelType}_${this.apiConfig.modelId}_${level}`);
        }

        _setETag(level, etag) {
            localStorage.setItem(`lod_etag_${this.apiConfig.modelType}_${this.apiConfig.modelId}_${level}`, etag);
        }

        /**
         * 更新UI显示
         * @private
         */
        _updateUI() {
            // 触发UI更新事件
            this.viewer._emit('lod-ui-update', {
                currentLevel: this.currentLevel,
                availableLevels: this.availableLevels,
                cache: Array.from(this.cache.keys())
            });
        }

        /**
         * 销毁LOD管理器
         */
        dispose() {
            // 清理缓存
            this.cache.forEach((data, level) => {
                URL.revokeObjectURL(data.url);
            });
            this.cache.clear();
            
            console.log('LOD管理器已销毁');
        }
    }

    // ========================== 材质增强器 ========================== //
    
    /**
     * 材质增强器
     */
    class MaterialEnhancer {
        constructor(viewer) {
            this.viewer = viewer;
            this.originalMaterials = new Map();
            this.enhancedMaterials = new Map();
        }

        /**
         * 增强模型材质
         */
        enhanceMaterials() {
            if (!this.viewer.model) {
                console.warn('没有加载的模型，跳过材质增强');
                return;
            }

            this.viewer.model.traverse((child) => {
                if (child.isMesh && child.material) {
                    this._enhanceMaterial(child);
                }
            });

            console.log('材质增强完成');
            this.viewer._emit('materials-enhanced');
        }

        /**
         * 增强单个材质
         * @private
         */
        _enhanceMaterial(mesh) {
            const originalMaterial = mesh.material;
            
            // 保存原始材质
            if (!this.originalMaterials.has(mesh.uuid)) {
                this.originalMaterials.set(mesh.uuid, originalMaterial);
            }

            // 创建增强材质
            let enhancedMaterial;
            
            if (originalMaterial.isMeshStandardMaterial || originalMaterial.isMeshPhysicalMaterial) {
                // 已经是PBR材质，只需要优化参数
                enhancedMaterial = originalMaterial.clone();
            } else {
                // 转换为PBR材质
                enhancedMaterial = new THREE.MeshStandardMaterial();
                
                // 复制基础属性
                if (originalMaterial.map) {
                    enhancedMaterial.map = originalMaterial.map;
                }
                if (originalMaterial.color) {
                    enhancedMaterial.color.copy(originalMaterial.color);
                }
            }

            // 应用鞋模专用配置
            const config = ADVANCED_CONFIG.MATERIALS.pbr;
            enhancedMaterial.metalness = config.metalness;
            enhancedMaterial.roughness = config.roughness;
            enhancedMaterial.envMapIntensity = config.envMapIntensity;

            // 应用材质预设（基于颜色推断材质类型）
            this._applyMaterialPreset(enhancedMaterial);

            // 应用材质
            mesh.material = enhancedMaterial;
            this.enhancedMaterials.set(mesh.uuid, enhancedMaterial);
        }

        /**
         * 应用材质预设
         * @private
         */
        _applyMaterialPreset(material) {
            const presets = ADVANCED_CONFIG.MATERIALS.shoePresets;
            const color = material.color;
            
            // 简单的颜色匹配逻辑
            const r = color.r, g = color.g, b = color.b;
            
            if (r < 0.3 && g < 0.3 && b < 0.3) {
                // 深色 - 可能是橡胶
                Object.assign(material, presets.rubber);
            } else if (r > 0.5 && (r - g) > 0.1 && (r - b) > 0.1) {
                // 偏红/棕色 - 可能是皮革
                Object.assign(material, presets.leather);
            } else {
                // 其他 - 布料材质
                Object.assign(material, presets.fabric);
            }
        }

        /**
         * 恢复原始材质
         */
        restoreOriginalMaterials() {
            if (!this.viewer.model) return;

            this.viewer.model.traverse((child) => {
                if (child.isMesh && this.originalMaterials.has(child.uuid)) {
                    child.material = this.originalMaterials.get(child.uuid);
                }
            });

            // 清理增强材质
            this.enhancedMaterials.forEach(material => {
                material.dispose();
            });
            this.enhancedMaterials.clear();

            console.log('已恢复原始材质');
        }

        /**
         * 销毁材质增强器
         */
        dispose() {
            this.restoreOriginalMaterials();
            this.originalMaterials.clear();
        }
    }

    // ========================== 性能监控器 ========================== //
    
    /**
     * 性能监控器
     */
    class PerformanceMonitor {
        constructor(viewer) {
            this.viewer = viewer;
            this.fps = 60;
            this.frameTime = 0;
            this.lastTime = performance.now();
            this.frameCount = 0;
            this.qualityLevel = 'medium';
            
            this.isMonitoring = false;
            this.adjustmentTimer = null;
        }

        /**
         * 开始性能监控
         */
        start() {
            if (this.isMonitoring) return;
            
            this.isMonitoring = true;
            this._startFPSTracking();
            
            if (ADVANCED_CONFIG.PERFORMANCE.autoQualityAdjust.enabled) {
                this._startAutoAdjustment();
            }
            
            console.log('性能监控已启动');
        }

        /**
         * 停止性能监控
         */
        stop() {
            this.isMonitoring = false;
            
            if (this.adjustmentTimer) {
                clearInterval(this.adjustmentTimer);
                this.adjustmentTimer = null;
            }
            
            console.log('性能监控已停止');
        }

        /**
         * 开始FPS追踪
         * @private
         */
        _startFPSTracking() {
            const trackFrame = () => {
                if (!this.isMonitoring) return;
                
                const now = performance.now();
                this.frameTime = now - this.lastTime;
                this.lastTime = now;
                this.frameCount++;
                
                // 每秒计算一次FPS
                if (this.frameCount % 60 === 0) {
                    this.fps = Math.round(1000 / this.frameTime);
                    this.viewer._emit('performance-update', {
                        fps: this.fps,
                        frameTime: this.frameTime,
                        qualityLevel: this.qualityLevel
                    });
                }
                
                requestAnimationFrame(trackFrame);
            };
            
            trackFrame();
        }

        /**
         * 开始自动质量调节
         * @private
         */
        _startAutoAdjustment() {
            const config = ADVANCED_CONFIG.PERFORMANCE.autoQualityAdjust;
            
            this.adjustmentTimer = setInterval(() => {
                if (this.fps < config.targetFPS * 0.8) {
                    // FPS过低，降低质量
                    this._adjustQuality('down');
                } else if (this.fps > config.targetFPS * 1.2) {
                    // FPS充足，可以提高质量
                    this._adjustQuality('up');
                }
            }, config.adjustmentInterval);
        }

        /**
         * 调节渲染质量
         * @private
         */
        _adjustQuality(direction) {
            const levels = ['low', 'medium', 'high'];
            const currentIndex = levels.indexOf(this.qualityLevel);
            
            let newIndex;
            if (direction === 'down' && currentIndex > 0) {
                newIndex = currentIndex - 1;
            } else if (direction === 'up' && currentIndex < levels.length - 1) {
                newIndex = currentIndex + 1;
            } else {
                return; // 无需调节
            }
            
            const newLevel = levels[newIndex];
            this.setQualityLevel(newLevel);
        }

        /**
         * 设置渲染质量级别
         */
        setQualityLevel(level) {
            if (!ADVANCED_CONFIG.PERFORMANCE.qualityLevels[level]) {
                console.warn(`未知的质量级别: ${level}`);
                return;
            }
            
            const oldLevel = this.qualityLevel;
            this.qualityLevel = level;
            
            const config = ADVANCED_CONFIG.PERFORMANCE.qualityLevels[level];
            
            // 应用渲染器设置
            if (this.viewer.renderer) {
                this.viewer.renderer.setPixelRatio(config.pixelRatio);
                
                // 更新阴影贴图大小
                if (this.viewer.lights && this.viewer.lights.directional) {
                    const shadowMap = this.viewer.lights.directional.shadow.mapSize;
                    shadowMap.width = config.shadowMapSize;
                    shadowMap.height = config.shadowMapSize;
                    this.viewer.lights.directional.shadow.map?.dispose();
                    this.viewer.lights.directional.shadow.map = null;
                }
            }
            
            console.log(`质量级别调节: ${oldLevel} -> ${level}`);
            this.viewer._emit('quality-changed', { from: oldLevel, to: level, config });
        }
    }

    // ========================== 高级模型查看器类 ========================== //
    
    /**
     * 高级模型查看器
     */
    class AdvancedModelViewer extends window.ThreeModelViewer {
        constructor(container, options = {}) {
            // 调用父类构造函数
            super(container, options);
            
            // 初始化高级功能
            this.lodManager = null;
            this.materialEnhancer = null;
            this.performanceMonitor = null;
            this.enhancedControls = null;
            
            // API配置
            this.apiConfig = {
                modelType: options.modelType || 'shoe',
                modelId: options.modelId
            };
            
            if (!this.apiConfig.modelId) {
                throw new Error('模型ID是必需的');
            }
            
            // 初始化高级组件
            this._initializeAdvancedComponents();
        }

        /**
         * 初始化高级组件
         * @private
         */
        _initializeAdvancedComponents() {
            try {
                // LOD管理器
                this.lodManager = new LODManager(this, this.apiConfig);
                
                // 材质增强器
                this.materialEnhancer = new MaterialEnhancer(this);
                
                // 性能监控器
                this.performanceMonitor = new PerformanceMonitor(this);
                
                // 增强交互控制器
                if (window.EnhancedControls) {
                    this.enhancedControls = new window.EnhancedControls(this, {
                        enableGestures: true,
                        enableKeyboard: true,
                        enableAnimation: true,
                        enableViewPresets: true
                    });
                } else {
                    console.warn('增强交互控制器未找到，将使用基础控制');
                }
                
                console.log('高级组件初始化完成');
                
            } catch (error) {
                console.error('高级组件初始化失败:', error);
            }
        }

        /**
         * 启动高级查看器
         */
        async start() {
            try {
                // 初始化LOD系统
                if (this.lodManager) {
                    await this.lodManager.initialize();
                }
                
                // 启动性能监控
                if (this.performanceMonitor) {
                    this.performanceMonitor.start();
                }
                
                // 监听模型加载事件以增强材质
                this.container.addEventListener('threeviewer:model-loaded', () => {
                    if (this.materialEnhancer) {
                        this.materialEnhancer.enhanceMaterials();
                    }
                });
                
                console.log('高级查看器启动成功');
                this._emit('advanced-viewer-ready');
                
            } catch (error) {
                console.error('高级查看器启动失败:', error);
                this._emit('advanced-viewer-error', { error });
            }
        }

        /**
         * 切换LOD级别
         */
        async switchLOD(level) {
            if (this.lodManager) {
                return await this.lodManager.loadLevel(level);
            }
            return false;
        }

        /**
         * 设置渲染质量
         */
        setQuality(level) {
            if (this.performanceMonitor) {
                this.performanceMonitor.setQualityLevel(level);
            }
        }

        /**
         * 获取当前状态
         */
        getStatus() {
            return {
                isReady: !!this.scene,
                currentLOD: this.lodManager?.currentLevel,
                availableLODs: this.lodManager?.availableLevels,
                quality: this.performanceMonitor?.qualityLevel,
                fps: this.performanceMonitor?.fps,
                hasModel: !!this.model
            };
        }

        /**
         * 销毁高级查看器
         */
        dispose() {
            // 停止性能监控
            if (this.performanceMonitor) {
                this.performanceMonitor.stop();
            }
            
            // 销毁增强交互控制器
            if (this.enhancedControls) {
                this.enhancedControls.dispose();
            }
            
            // 销毁LOD管理器
            if (this.lodManager) {
                this.lodManager.dispose();
            }
            
            // 销毁材质增强器
            if (this.materialEnhancer) {
                this.materialEnhancer.dispose();
            }
            
            // 调用父类销毁方法
            super.dispose();
            
            console.log('高级查看器已销毁');
        }
    }

    // ========================== 全局导出 ========================== //
    
    // 导出到全局作用域
    window.AdvancedModelViewer = AdvancedModelViewer;
    
    // 也导出组件类供高级用户使用
    window.LODManager = LODManager;
    window.MaterialEnhancer = MaterialEnhancer;
    window.PerformanceMonitor = PerformanceMonitor;
    
    console.log('高级模型查看器已加载');

})(window);
