import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { DatabaseService } from './services/database.service';
import { PythonRunnerService } from './services/python-runner.service';
import { setupDatabaseHandlers } from './ipc-handlers/database.handler';
import { setupFileHandlers } from './ipc-handlers/file.handler';
import { setupMatchingHandlers } from './ipc-handlers/matching.handler';

let mainWindow: BrowserWindow | null = null;
let databaseService: DatabaseService;
let pythonRunnerService: PythonRunnerService;

// 开发模式检测
const isDev = process.argv.includes('--dev') || process.env.NODE_ENV === 'development';

// 创建主窗口
function createWindow(): void {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1200,
        minHeight: 700,
        title: '鞋模智能匹配系统',
        icon: path.join(__dirname, '../resources/icons/icon.png'),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
            webSecurity: !isDev
        },
        frame: process.platform !== 'darwin',
        titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default'
    });

    // 加载应用
    if (isDev) {
        // 开发模式：加载 Angular 开发服务器
        mainWindow.loadURL('http://localhost:4200');
        mainWindow.webContents.openDevTools();
    } else {
        // 生产模式：加载打包的 Angular 应用
        mainWindow.loadFile(path.join(__dirname, '../angular-app/dist/index.html'));
    }

    // 窗口关闭事件
    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // 防止窗口标题被修改
    mainWindow.on('page-title-updated', (evt) => {
        evt.preventDefault();
    });
}

// 初始化应用数据目录
function initializeAppData(): void {
    const userDataPath = app.getPath('userData');
    const directories = [
        'blanks',
        'models', 
        'results',
        'results/heatmaps',
        'results/exports',
        'temp'
    ];

    directories.forEach(dir => {
        const fullPath = path.join(userDataPath, dir);
        if (!fs.existsSync(fullPath)) {
            fs.mkdirSync(fullPath, { recursive: true });
        }
    });

    console.log('用户数据目录:', userDataPath);
}

// 初始化服务
async function initializeServices(): Promise<void> {
    const userDataPath = app.getPath('userData');
    
    // 初始化数据库服务
    databaseService = new DatabaseService(path.join(userDataPath, 'database.db'));
    await databaseService.initialize();
    
    // 初始化 Python 运行器服务
    pythonRunnerService = new PythonRunnerService(
        isDev 
            ? path.join(__dirname, '../python-engine/dist/shoe-matcher-engine')
            : path.join(process.resourcesPath, 'python-engine/shoe-matcher-engine')
    );
    
    // 设置 IPC 处理器
    setupDatabaseHandlers(ipcMain, databaseService);
    setupFileHandlers(ipcMain, app.getPath('userData'));
    setupMatchingHandlers(ipcMain, pythonRunnerService, databaseService);
}

// 应用就绪事件
app.whenReady().then(async () => {
    // 初始化应用数据目录
    initializeAppData();
    
    // 初始化服务
    await initializeServices();
    
    // 创建窗口
    createWindow();
    
    // macOS 特殊处理
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

// 所有窗口关闭事件
app.on('window-all-closed', () => {
    // macOS 上应用通常在关闭所有窗口后保持活动状态
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// 应用退出前清理
app.on('before-quit', async () => {
    // 关闭数据库连接
    if (databaseService) {
        await databaseService.close();
    }
    
    // 终止 Python 进程
    if (pythonRunnerService) {
        pythonRunnerService.cleanup();
    }
});

// 通用 IPC 处理器
ipcMain.handle('app:getVersion', () => {
    return app.getVersion();
});

ipcMain.handle('app:getPath', (event, name: string) => {
    return app.getPath(name as any);
});

ipcMain.handle('app:openExternal', async (event, url: string) => {
    return shell.openExternal(url);
});

ipcMain.handle('app:showItemInFolder', (event, fullPath: string) => {
    shell.showItemInFolder(fullPath);
});

// 对话框 API
ipcMain.handle('dialog:showOpenDialog', async (event, options) => {
    const result = await dialog.showOpenDialog(mainWindow!, options);
    return result;
});

ipcMain.handle('dialog:showSaveDialog', async (event, options) => {
    const result = await dialog.showSaveDialog(mainWindow!, options);
    return result;
});

ipcMain.handle('dialog:showMessageBox', async (event, options) => {
    const result = await dialog.showMessageBox(mainWindow!, options);
    return result;
});

// 错误处理
process.on('uncaughtException', (error) => {
    console.error('未捕获的异常:', error);
    dialog.showErrorBox('未捕获的异常', error.message);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('未处理的 Promise 拒绝:', reason);
});
