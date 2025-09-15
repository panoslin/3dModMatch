import { contextBridge, ipcRenderer } from 'electron';

// 定义安全的 API 接口
const electronAPI = {
    // 应用信息
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
    getPath: (name: string) => ipcRenderer.invoke('app:getPath', name),
    openExternal: (url: string) => ipcRenderer.invoke('app:openExternal', url),
    showItemInFolder: (path: string) => ipcRenderer.invoke('app:showItemInFolder', path),

    // 对话框
    showOpenDialog: (options: any) => ipcRenderer.invoke('dialog:showOpenDialog', options),
    showSaveDialog: (options: any) => ipcRenderer.invoke('dialog:showSaveDialog', options),
    showMessageBox: (options: any) => ipcRenderer.invoke('dialog:showMessageBox', options),

    // 数据库操作
    database: {
        // 分类管理
        getCategories: () => ipcRenderer.invoke('db:getCategories'),
        createCategory: (data: any) => ipcRenderer.invoke('db:createCategory', data),
        updateCategory: (id: number, data: any) => ipcRenderer.invoke('db:updateCategory', id, data),
        deleteCategory: (id: number) => ipcRenderer.invoke('db:deleteCategory', id),
        
        // 粗胚管理
        getBlanks: (filters?: any) => ipcRenderer.invoke('db:getBlanks', filters),
        getBlankById: (id: number) => ipcRenderer.invoke('db:getBlankById', id),
        createBlank: (data: any) => ipcRenderer.invoke('db:createBlank', data),
        updateBlank: (id: number, data: any) => ipcRenderer.invoke('db:updateBlank', id, data),
        deleteBlank: (id: number) => ipcRenderer.invoke('db:deleteBlank', id),
        
        // 粗胚分类关联
        addBlankToCategory: (blankId: number, categoryId: number) => 
            ipcRenderer.invoke('db:addBlankToCategory', blankId, categoryId),
        removeBlankFromCategory: (blankId: number, categoryId: number) => 
            ipcRenderer.invoke('db:removeBlankFromCategory', blankId, categoryId),
        getBlankCategories: (blankId: number) => 
            ipcRenderer.invoke('db:getBlankCategories', blankId),
        getBlanksByCategory: (categoryId: number) => 
            ipcRenderer.invoke('db:getBlanksByCategory', categoryId),
        
        // 鞋模管理
        getModels: (filters?: any) => ipcRenderer.invoke('db:getModels', filters),
        getModelById: (id: number) => ipcRenderer.invoke('db:getModelById', id),
        createModel: (data: any) => ipcRenderer.invoke('db:createModel', data),
        updateModel: (id: number, data: any) => ipcRenderer.invoke('db:updateModel', id, data),
        deleteModel: (id: number) => ipcRenderer.invoke('db:deleteModel', id),
        
        // 匹配历史
        getMatches: (filters?: any) => ipcRenderer.invoke('db:getMatches', filters),
        getMatchById: (id: number) => ipcRenderer.invoke('db:getMatchById', id),
        getMatchResults: (matchId: number) => ipcRenderer.invoke('db:getMatchResults', matchId),
        
        // 统计查询
        getStatistics: () => ipcRenderer.invoke('db:getStatistics')
    },

    // 文件操作
    file: {
        uploadFile: (sourcePath: string, type: 'blank' | 'model') => 
            ipcRenderer.invoke('file:upload', sourcePath, type),
        deleteFile: (filePath: string) => 
            ipcRenderer.invoke('file:delete', filePath),
        getFilePath: (type: string, fileName: string) => 
            ipcRenderer.invoke('file:getPath', type, fileName),
        extractMetadata: (filePath: string) => 
            ipcRenderer.invoke('file:extractMetadata', filePath),
        generatePreview: (filePath: string, outputPath: string) => 
            ipcRenderer.invoke('file:generatePreview', filePath, outputPath)
    },

    // 匹配操作
    matching: {
        startMatch: (params: any) => ipcRenderer.invoke('match:start', params),
        cancelMatch: (matchId: number) => ipcRenderer.invoke('match:cancel', matchId),
        getProgress: (matchId: number) => ipcRenderer.invoke('match:getProgress', matchId),
        
        // 进度监听
        onProgress: (callback: (data: any) => void) => {
            const subscription = (event: any, data: any) => callback(data);
            ipcRenderer.on('match:progress', subscription);
            return () => ipcRenderer.removeListener('match:progress', subscription);
        },
        
        // 日志监听
        onLog: (callback: (data: any) => void) => {
            const subscription = (event: any, data: any) => callback(data);
            ipcRenderer.on('match:log', subscription);
            return () => ipcRenderer.removeListener('match:log', subscription);
        },
        
        // 完成监听
        onComplete: (callback: (data: any) => void) => {
            const subscription = (event: any, data: any) => callback(data);
            ipcRenderer.on('match:complete', subscription);
            return () => ipcRenderer.removeListener('match:complete', subscription);
        },
        
        // 错误监听
        onError: (callback: (data: any) => void) => {
            const subscription = (event: any, data: any) => callback(data);
            ipcRenderer.on('match:error', subscription);
            return () => ipcRenderer.removeListener('match:error', subscription);
        }
    },

    // 3D 预览
    viewer: {
        generateBlankPreview: (blankId: number) => 
            ipcRenderer.invoke('viewer:generateBlankPreview', blankId),
        generateModelPreview: (modelId: number) => 
            ipcRenderer.invoke('viewer:generateModelPreview', modelId),
        generateHeatmap: (resultId: number) => 
            ipcRenderer.invoke('viewer:generateHeatmap', resultId),
        getPreviewUrl: (type: string, id: number) => 
            ipcRenderer.invoke('viewer:getPreviewUrl', type, id)
    },

    // 系统工具
    system: {
        getMemoryUsage: () => ipcRenderer.invoke('system:getMemoryUsage'),
        getCPUUsage: () => ipcRenderer.invoke('system:getCPUUsage'),
        getStorageInfo: () => ipcRenderer.invoke('system:getStorageInfo'),
        clearCache: () => ipcRenderer.invoke('system:clearCache'),
        exportData: (options: any) => ipcRenderer.invoke('system:exportData', options),
        importData: (filePath: string) => ipcRenderer.invoke('system:importData', filePath)
    }
};

// 暴露 API 到渲染进程
contextBridge.exposeInMainWorld('electronAPI', electronAPI);

// 类型定义导出（供 Angular 使用）
export type ElectronAPI = typeof electronAPI;
