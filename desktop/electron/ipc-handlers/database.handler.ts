import { IpcMain } from 'electron';
import { DatabaseService } from '../services/database.service';

export function setupDatabaseHandlers(ipcMain: IpcMain, dbService: DatabaseService): void {
    // 分类管理
    ipcMain.handle('db:getCategories', async () => {
        try {
            return await dbService.getCategories();
        } catch (error: any) {
            console.error('获取分类失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:createCategory', async (event, data) => {
        try {
            return await dbService.createCategory(data);
        } catch (error: any) {
            console.error('创建分类失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:updateCategory', async (event, id, data) => {
        try {
            return await dbService.updateCategory(id, data);
        } catch (error: any) {
            console.error('更新分类失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:deleteCategory', async (event, id) => {
        try {
            return await dbService.deleteCategory(id);
        } catch (error: any) {
            console.error('删除分类失败:', error);
            throw error;
        }
    });

    // 粗胚管理
    ipcMain.handle('db:getBlanks', async (event, filters) => {
        try {
            return await dbService.getBlanks(filters);
        } catch (error: any) {
            console.error('获取粗胚列表失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:getBlankById', async (event, id) => {
        try {
            return await dbService.getBlankById(id);
        } catch (error: any) {
            console.error('获取粗胚详情失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:createBlank', async (event, data) => {
        try {
            return await dbService.createBlank(data);
        } catch (error: any) {
            console.error('创建粗胚失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:updateBlank', async (event, id, data) => {
        try {
            return await dbService.updateBlank(id, data);
        } catch (error: any) {
            console.error('更新粗胚失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:deleteBlank', async (event, id) => {
        try {
            return await dbService.deleteBlank(id);
        } catch (error: any) {
            console.error('删除粗胚失败:', error);
            throw error;
        }
    });

    // 粗胚分类关联
    ipcMain.handle('db:addBlankToCategory', async (event, blankId, categoryId) => {
        try {
            return await dbService.addBlankToCategory(blankId, categoryId);
        } catch (error: any) {
            console.error('添加粗胚到分类失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:removeBlankFromCategory', async (event, blankId, categoryId) => {
        try {
            return await dbService.removeBlankFromCategory(blankId, categoryId);
        } catch (error: any) {
            console.error('从分类移除粗胚失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:getBlankCategories', async (event, blankId) => {
        try {
            return await dbService.getBlankCategories(blankId);
        } catch (error: any) {
            console.error('获取粗胚分类失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:getBlanksByCategory', async (event, categoryId) => {
        try {
            return await dbService.getBlanksByCategory(categoryId);
        } catch (error: any) {
            console.error('按分类获取粗胚失败:', error);
            throw error;
        }
    });

    // 鞋模管理
    ipcMain.handle('db:getModels', async (event, filters) => {
        try {
            return await dbService.getModels(filters);
        } catch (error: any) {
            console.error('获取鞋模列表失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:getModelById', async (event, id) => {
        try {
            return await dbService.getModelById(id);
        } catch (error: any) {
            console.error('获取鞋模详情失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:createModel', async (event, data) => {
        try {
            return await dbService.createModel(data);
        } catch (error: any) {
            console.error('创建鞋模失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:deleteModel', async (event, id) => {
        try {
            return await dbService.deleteModel(id);
        } catch (error: any) {
            console.error('删除鞋模失败:', error);
            throw error;
        }
    });

    // 匹配历史
    ipcMain.handle('db:getMatches', async (event, filters) => {
        try {
            return await dbService.getMatches(filters);
        } catch (error: any) {
            console.error('获取匹配历史失败:', error);
            throw error;
        }
    });

    ipcMain.handle('db:getMatchResults', async (event, matchId) => {
        try {
            return await dbService.getMatchResults(matchId);
        } catch (error: any) {
            console.error('获取匹配结果失败:', error);
            throw error;
        }
    });

    // 统计
    ipcMain.handle('db:getStatistics', async () => {
        try {
            return await dbService.getStatistics();
        } catch (error: any) {
            console.error('获取统计信息失败:', error);
            throw error;
        }
    });
}
