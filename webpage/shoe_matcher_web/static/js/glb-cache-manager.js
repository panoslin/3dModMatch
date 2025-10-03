/**
 * GLB模型缓存管理器
 * 
 * 功能：
 * - 缓存已加载的GLB模型，避免重复加载
 * - 支持内存缓存（Map）和持久化缓存（IndexedDB）
 * - 自动管理缓存大小，避免内存溢出
 * - 提供统计信息和缓存清理功能
 * 
 * @author 3D ModMatch Team
 * @version 1.0
 */

class GLBCacheManager {
    constructor(options = {}) {
        // 缓存配置
        this.maxCacheSize = options.maxCacheSize || 200;  // 最多缓存200个模型
        this.maxMemoryMB = options.maxMemoryMB || 2000;   // 最大内存使用2GB
        this.maxMemoryCacheSize = options.maxMemoryCacheSize || 20;  // 内存只缓存20个最热门的
        this.cacheName = 'glb-models-cache-v1';  // Cache API名称
        
        // L1缓存：内存（热数据，快速访问）
        this.memoryCache = new Map();
        
        // L2缓存：Cache API（持久化，大容量）
        this.cacheAPI = null;
        
        // 缓存元数据（URL -> {size, timestamp, hits, memoryHits}）
        // 使用 LocalStorage 持久化元数据
        this.metadataKey = 'glb-cache-metadata';
        this.cacheMetadata = this.loadMetadataFromStorage();
        
        // 统计信息
        this.stats = {
            memoryHits: 0,    // L1缓存命中
            diskHits: 0,      // L2缓存命中
            misses: 0,        // 完全未命中
            loads: 0,         // 总加载次数
            evictions: 0      // 缓存驱逐次数
        };
        
        // 初始化Cache API
        this.initCacheAPI();
        
        console.log('✅ GLB缓存管理器已初始化（双层缓存）', {
            maxCacheSize: this.maxCacheSize,
            maxMemoryMB: this.maxMemoryMB,
            memoryCacheSize: this.maxMemoryCacheSize,
            persistentCache: 'Cache API'
        });
    }
    
    /**
     * 初始化Cache API
     */
    async initCacheAPI() {
        try {
            if ('caches' in window) {
                this.cacheAPI = await caches.open(this.cacheName);
                console.log('✅ Cache API已初始化（持久化缓存）');
                
                // 清理过期缓存
                await this.cleanupExpiredCache();
            } else {
                console.warn('⚠️ 浏览器不支持Cache API，缓存刷新后会丢失');
            }
        } catch (error) {
            console.error('Cache API初始化失败:', error);
        }
    }
    
    /**
     * 从LocalStorage加载元数据
     */
    loadMetadataFromStorage() {
        try {
            const stored = localStorage.getItem(this.metadataKey);
            if (stored) {
                const metadata = JSON.parse(stored);
                console.log(`📥 从存储恢复元数据: ${Object.keys(metadata).length}个项目`);
                return new Map(Object.entries(metadata));
            }
        } catch (error) {
            console.warn('加载缓存元数据失败:', error);
        }
        return new Map();
    }
    
    /**
     * 保存元数据到LocalStorage
     */
    saveMetadataToStorage() {
        try {
            const metadata = Object.fromEntries(this.cacheMetadata);
            localStorage.setItem(this.metadataKey, JSON.stringify(metadata));
        } catch (error) {
            console.warn('保存缓存元数据失败:', error);
        }
    }
    
    /**
     * 初始化IndexedDB（已废弃，使用Cache API代替）
     */
    async initIndexedDB() {
        // 不再使用IndexedDB，改用Cache API
        console.log('ℹ️ 使用Cache API代替IndexedDB进行持久化缓存');
        return true;
    }
    
    /**
     * 加载GLB模型（带缓存）
     * 
     * @param {string} url - GLB模型URL
     * @param {THREE.GLTFLoader} loader - GLTFLoader实例
     * @param {Object} options - 加载选项
     * @returns {Promise<Object>} GLTF对象
     */
    async loadModelWithCache(url, loader, options = {}) {
        this.stats.loads++;
        
        console.log(`🔍 [L1] 检查内存缓存: ${url.substring(url.lastIndexOf('/'))}`);
        
        // ========== L1: 内存缓存（最快，但页面刷新会丢失）==========
        const memoryCached = this.memoryCache.get(url);
        if (memoryCached) {
            this.stats.memoryHits++;
            this.updateCacheMetadata(url, 'memory-hit');
            console.log(`✅ [L1] 内存缓存命中 (瞬间)`);
            
            return {
                scene: memoryCached.scene.clone(),
                scenes: memoryCached.scenes,
                animations: memoryCached.animations,
                cameras: memoryCached.cameras,
                asset: memoryCached.asset,
                userData: memoryCached.userData
            };
        }
        
        console.log(`⏭️ [L1] 内存未命中，检查 [L2] Cache API...`);
        
        // ========== L2: Cache API（持久化，跨页面有效）==========
        if (this.cacheAPI) {
            try {
                const cachedResponse = await this.cacheAPI.match(url);
                if (cachedResponse) {
                    this.stats.diskHits++;
                    console.log(`✅ [L2] Cache API命中，解析GLB...`);
                    
                    // 从Response读取ArrayBuffer
                    const arrayBuffer = await cachedResponse.arrayBuffer();
                    
                    // 使用GLTFLoader解析
                    const gltf = await new Promise((resolve, reject) => {
                        loader.parse(
                            arrayBuffer,
                            '',  // resourcePath
                            resolve,
                            reject
                        );
                    });
                    
                    // 提升到L1缓存（热数据）
                    this.addToMemoryCache(url, gltf);
                    this.updateCacheMetadata(url, 'disk-hit');
                    
                    console.log(`✅ GLB解析完成，已提升到内存缓存`);
                    return gltf;
                }
            } catch (error) {
                console.warn('Cache API读取失败:', error);
            }
        }
        
        // ========== 完全未命中：从网络加载 ==========
        this.stats.misses++;
        console.log(`⏬ [网络] 缓存未命中，从服务器加载...`);
        
        // 使用fetch获取，这样可以同时缓存到Cache API
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        // 克隆响应（一份存Cache API，一份解析）
        const responseClone = response.clone();
        
        // 存入Cache API（持久化）
        if (this.cacheAPI) {
            try {
                await this.cacheAPI.put(url, responseClone);
                console.log(`💾 [L2] 已存入Cache API`);
            } catch (error) {
                console.warn('存入Cache API失败:', error);
            }
        }
        
        // 解析GLB
        const arrayBuffer = await response.arrayBuffer();
        const gltf = await new Promise((resolve, reject) => {
            loader.parse(arrayBuffer, '', resolve, reject);
        });
        
        // 存入内存缓存
        this.addToMemoryCache(url, gltf);
        this.updateCacheMetadata(url, 'new');
        
        console.log(`✅ 模型已加载并缓存（L1+L2）`);
        return gltf;
    }
    
    /**
     * 添加模型到内存缓存（L1）
     */
    addToMemoryCache(url, gltf) {
        // 检查L1缓存大小限制（只保留热数据）
        if (this.memoryCache.size >= this.maxMemoryCacheSize) {
            this.evictFromMemory();
        }
        
        // 存储到内存缓存
        this.memoryCache.set(url, gltf);
        console.log(`💾 [L1] 已存入内存 (${this.memoryCache.size}/${this.maxMemoryCacheSize})`);
    }
    
    /**
     * 添加模型到缓存（已废弃，使用addToMemoryCache）
     */
    addToCache(url, gltf) {
        this.addToMemoryCache(url, gltf);
    }
    
    /**
     * 清理过期的Cache API缓存
     */
    async cleanupExpiredCache() {
        if (!this.cacheAPI) return;
        
        try {
            const requests = await this.cacheAPI.keys();
            const now = Date.now();
            const maxAge = 7 * 24 * 60 * 60 * 1000;  // 7天
            
            let cleaned = 0;
            for (const request of requests) {
                const url = request.url;
                const metadata = this.cacheMetadata.get(url);
                
                if (metadata && (now - metadata.timestamp > maxAge)) {
                    await this.cacheAPI.delete(request);
                    this.cacheMetadata.delete(url);
                    cleaned++;
                }
            }
            
            if (cleaned > 0) {
                console.log(`🗑️ 清理了${cleaned}个过期缓存项`);
                this.saveMetadataToStorage();
            }
        } catch (error) {
            console.warn('清理过期缓存失败:', error);
        }
    }
    
    /**
     * 更新缓存元数据
     */
    updateCacheMetadata(url, action) {
        let metadata = this.cacheMetadata.get(url);
        
        if (!metadata) {
            metadata = {
                timestamp: Date.now(),
                hits: 0,
                memoryHits: 0,
                diskHits: 0,
                lastAccess: Date.now()
            };
            this.cacheMetadata.set(url, metadata);
        }
        
        metadata.lastAccess = Date.now();
        
        if (action === 'memory-hit') {
            metadata.hits++;
            metadata.memoryHits++;
        } else if (action === 'disk-hit') {
            metadata.hits++;
            metadata.diskHits++;
        } else if (action === 'new') {
            // 新添加，不增加hits
        }
        
        // 定期保存元数据到LocalStorage
        if (this.stats.loads % 5 === 0) {
            this.saveMetadataToStorage();
        }
    }
    
    /**
     * 从内存驱逐（LRU策略）
     */
    evictFromMemory() {
        let oldestUrl = null;
        let oldestTime = Infinity;
        
        // 只从内存缓存中的项里找最旧的
        for (const url of this.memoryCache.keys()) {
            const metadata = this.cacheMetadata.get(url);
            if (metadata) {
                const accessTime = metadata.lastAccess || metadata.timestamp;
                if (accessTime < oldestTime) {
                    oldestTime = accessTime;
                    oldestUrl = url;
                }
            }
        }
        
        if (oldestUrl) {
            this.memoryCache.delete(oldestUrl);
            this.stats.evictions++;
            console.log(`🗑️ [L1] 内存驱逐: ${oldestUrl.substring(oldestUrl.lastIndexOf('/'))}`);
            // 注意：不删除元数据和Cache API中的数据，仅从内存移除
        }
    }
    
    /**
     * 驱逐最旧的缓存项（已废弃）
     */
    evictOldest() {
        this.evictFromMemory();
    }
    
    /**
     * 估算模型大小（粗略估计）
     */
    estimateModelSize(gltf) {
        let size = 0;
        if (gltf.scene) {
            gltf.scene.traverse((child) => {
                if (child.geometry) {
                    const geometry = child.geometry;
                    // 估算几何体大小
                    if (geometry.attributes.position) {
                        size += geometry.attributes.position.array.length * 4; // Float32
                    }
                    if (geometry.index) {
                        size += geometry.index.array.length * 4;
                    }
                }
            });
        }
        return size;
    }
    
    /**
     * 预加载模型列表
     * 
     * @param {Array<string>} urls - 要预加载的URL列表
     * @param {THREE.GLTFLoader} loader - GLTFLoader实例
     */
    async preloadModels(urls, loader) {
        console.log(`🚀 开始预加载 ${urls.length} 个模型...`);
        
        const results = {
            success: 0,
            failed: 0,
            errors: []
        };
        
        for (const url of urls) {
            try {
                if (!this.memoryCache.has(url)) {
                    await this.loadModelWithCache(url, loader);
                    results.success++;
                } else {
                    console.log(`⏭️ 跳过已缓存: ${url}`);
                }
            } catch (error) {
                console.error(`❌ 预加载失败: ${url}`, error);
                results.failed++;
                results.errors.push({ url, error: error.message });
            }
        }
        
        console.log(`✅ 预加载完成: 成功${results.success}, 失败${results.failed}`);
        return results;
    }
    
    /**
     * 清除指定URL的缓存
     */
    async clearCache(url) {
        if (url) {
            // 清除内存缓存
            this.memoryCache.delete(url);
            
            // 清除Cache API
            if (this.cacheAPI) {
                await this.cacheAPI.delete(url);
            }
            
            // 清除元数据
            this.cacheMetadata.delete(url);
            this.saveMetadataToStorage();
            
            console.log(`🗑️ 已清除缓存: ${url}`);
        } else {
            // 清除所有缓存
            this.memoryCache.clear();
            
            if (this.cacheAPI) {
                const requests = await this.cacheAPI.keys();
                for (const request of requests) {
                    await this.cacheAPI.delete(request);
                }
            }
            
            this.cacheMetadata.clear();
            localStorage.removeItem(this.metadataKey);
            
            console.log('🗑️ 已清除所有缓存（L1+L2）');
        }
    }
    
    /**
     * 获取缓存统计信息
     */
    async getStats() {
        // 统计Cache API中的项数
        let cacheAPISize = 0;
        if (this.cacheAPI) {
            try {
                const requests = await this.cacheAPI.keys();
                cacheAPISize = requests.length;
            } catch (error) {
                console.warn('获取Cache API大小失败:', error);
            }
        }
        
        const totalHits = this.stats.memoryHits + this.stats.diskHits;
        const totalHitRate = this.stats.loads > 0 
            ? ((totalHits / this.stats.loads) * 100).toFixed(1)
            : 0;
        
        const memoryHitRate = this.stats.loads > 0
            ? ((this.stats.memoryHits / this.stats.loads) * 100).toFixed(1)
            : 0;
        
        return {
            ...this.stats,
            memoryCacheSize: this.memoryCache.size,
            diskCacheSize: cacheAPISize,
            totalCacheSize: this.cacheMetadata.size,
            totalHitRate: totalHitRate + '%',
            memoryHitRate: memoryHitRate + '%',
            items: Array.from(this.cacheMetadata.entries()).map(([url, meta]) => ({
                url,
                hits: meta.hits,
                memoryHits: meta.memoryHits || 0,
                diskHits: meta.diskHits || 0,
                cached: new Date(meta.timestamp).toLocaleString(),
                lastAccess: new Date(meta.lastAccess).toLocaleString()
            }))
        };
    }
    
    /**
     * 打印缓存统计
     */
    async printStats() {
        const stats = await this.getStats();
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log('📊 GLB双层缓存统计');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log(`🔥 L1缓存(内存): ${stats.memoryCacheSize} / ${this.maxMemoryCacheSize} 个`);
        console.log(`💾 L2缓存(持久): ${stats.diskCacheSize} / ${this.maxCacheSize} 个`);
        console.log(`📦 总缓存项: ${stats.totalCacheSize} 个`);
        console.log(`📈 总命中率: ${stats.totalHitRate}`);
        console.log(`   └─ L1命中率: ${stats.memoryHitRate}`);
        console.log(`   └─ L2命中率: ${((stats.diskHits / (stats.loads || 1)) * 100).toFixed(1)}%`);
        console.log(`🔢 总加载: ${stats.loads} 次`);
        console.log(`   ├─ L1命中: ${stats.memoryHits} 次 (瞬间)`);
        console.log(`   ├─ L2命中: ${stats.diskHits} 次 (快速)`);
        console.log(`   └─ 网络: ${stats.misses} 次 (慢)`);
        console.log(`🗑️ 驱逐: ${stats.evictions} 次`);
        
        if (stats.items.length > 0) {
            console.log('\n📦 热门缓存项 (前10):');
            stats.items
                .sort((a, b) => b.hits - a.hits)
                .slice(0, 10)
                .forEach((item, i) => {
                    const filename = item.url.split('/').pop().substring(0, 40);
                    console.log(`  ${i+1}. ${filename}`);
                    console.log(`     总命中: ${item.hits} (L1:${item.memoryHits}, L2:${item.diskHits})`);
                });
        }
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    }
}

// 创建全局缓存管理器实例
window.glbCacheManager = window.glbCacheManager || new GLBCacheManager({
    maxCacheSize: 200,          // L2持久化缓存：最多200个模型 (20MB×200=4GB)
    maxMemoryCacheSize: 20,     // L1内存缓存：最多20个热门模型 (20MB×20=400MB)
    maxMemoryMB: 2000           // 最大内存限制
});

// 导出以便模块化使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GLBCacheManager;
}

