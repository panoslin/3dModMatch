import { Injectable } from '@angular/core';

// TypeScript interface matching the preload API
export interface ElectronAPI {
  getVersion: () => Promise<string>;
  getPath: (name: string) => Promise<string>;
  openExternal: (url: string) => Promise<void>;
  showItemInFolder: (path: string) => Promise<void>;
  
  showOpenDialog: (options: any) => Promise<any>;
  showSaveDialog: (options: any) => Promise<any>;
  showMessageBox: (options: any) => Promise<any>;
  
  database: {
    getCategories: () => Promise<any[]>;
    createCategory: (data: any) => Promise<number>;
    updateCategory: (id: number, data: any) => Promise<void>;
    deleteCategory: (id: number) => Promise<void>;
    
    getBlanks: (filters?: any) => Promise<any[]>;
    getBlankById: (id: number) => Promise<any>;
    createBlank: (data: any) => Promise<number>;
    updateBlank: (id: number, data: any) => Promise<void>;
    deleteBlank: (id: number) => Promise<void>;
    
    addBlankToCategory: (blankId: number, categoryId: number) => Promise<void>;
    removeBlankFromCategory: (blankId: number, categoryId: number) => Promise<void>;
    getBlankCategories: (blankId: number) => Promise<any[]>;
    getBlanksByCategory: (categoryId: number) => Promise<any[]>;
    
    getModels: (filters?: any) => Promise<any[]>;
    getModelById: (id: number) => Promise<any>;
    createModel: (data: any) => Promise<number>;
    deleteModel: (id: number) => Promise<void>;
    
    getMatches: (filters?: any) => Promise<any[]>;
    getMatchResults: (matchId: number) => Promise<any[]>;
    getStatistics: () => Promise<any>;
  };
  
  file: {
    uploadFile: (sourcePath: string, type: 'blank' | 'model') => Promise<any>;
    deleteFile: (filePath: string) => Promise<any>;
    getFilePath: (type: string, fileName: string) => Promise<string>;
    extractMetadata: (filePath: string) => Promise<any>;
    generatePreview: (filePath: string, outputPath: string) => Promise<any>;
  };
  
  matching: {
    startMatch: (params: any) => Promise<any>;
    cancelMatch: (matchId: number) => Promise<any>;
    getProgress: (matchId: number) => Promise<any>;
    onProgress: (callback: (data: any) => void) => () => void;
    onLog: (callback: (data: any) => void) => () => void;
    onComplete: (callback: (data: any) => void) => () => void;
    onError: (callback: (data: any) => void) => () => void;
  };
  
  viewer: {
    generateBlankPreview: (blankId: number) => Promise<any>;
    generateModelPreview: (modelId: number) => Promise<any>;
    generateHeatmap: (resultId: number) => Promise<any>;
    getPreviewUrl: (type: string, id: number) => Promise<string>;
  };
  
  system: {
    getMemoryUsage: () => Promise<any>;
    getCPUUsage: () => Promise<any>;
    getStorageInfo: () => Promise<any>;
    clearCache: () => Promise<any>;
  };
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

@Injectable({
  providedIn: 'root'
})
export class ElectronService {
  private electronAPI: ElectronAPI | null = null;

  constructor() {
    if (this.isElectron()) {
      this.electronAPI = window.electronAPI;
    }
  }

  isElectron(): boolean {
    return typeof window !== 'undefined' && !!(window && window.electronAPI);
  }

  getAPI(): ElectronAPI | null {
    return this.electronAPI;
  }

  // Convenience methods
  async getVersion(): Promise<string> {
    if (!this.electronAPI) return 'Web Mode';
    return this.electronAPI.getVersion();
  }

  async showOpenFileDialog(options?: any): Promise<string | null> {
    if (!this.electronAPI) return null;
    
    const defaultOptions = {
      properties: ['openFile'],
      filters: [
        { name: '3D模型', extensions: ['3dm'] },
        { name: '所有文件', extensions: ['*'] }
      ]
    };
    
    const result = await this.electronAPI.showOpenDialog({ ...defaultOptions, ...options });
    if (result.canceled || !result.filePaths.length) {
      return null;
    }
    return result.filePaths[0];
  }

  async showMessage(title: string, message: string, type: 'info' | 'error' | 'warning' = 'info'): Promise<void> {
    if (!this.electronAPI) {
      console.log(`[${type}] ${title}: ${message}`);
      return;
    }
    
    await this.electronAPI.showMessageBox({
      type,
      title,
      message,
      buttons: ['确定']
    });
  }
}
