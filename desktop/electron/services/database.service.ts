import Database from 'better-sqlite3';
import * as path from 'path';
import * as fs from 'fs';

export class DatabaseService {
    private db: Database.Database | null = null;
    private readonly dbPath: string;

    constructor(dbPath: string) {
        this.dbPath = dbPath;
    }

    async initialize(): Promise<void> {
        try {
            // 创建数据库连接
            this.db = new Database(this.dbPath, { verbose: console.log });
            
            // 启用外键约束
            this.db.pragma('foreign_keys = ON');
            
            // 创建表结构
            await this.createTables();
            
            // 初始化默认数据
            await this.initializeDefaultData();
            
            console.log('数据库初始化成功:', this.dbPath);
        } catch (error) {
            console.error('数据库初始化失败:', error);
            throw error;
        }
    }

    private async createTables(): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');

        const schema = `
            -- 分类表（层级结构）
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                name TEXT NOT NULL,
                level INTEGER NOT NULL,
                path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
            );

            -- 粗胚表
            CREATE TABLE IF NOT EXISTS blanks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                metadata JSON,
                tags JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 粗胚分类关联表（多对多）
            CREATE TABLE IF NOT EXISTS blank_categories (
                blank_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                PRIMARY KEY (blank_id, category_id),
                FOREIGN KEY (blank_id) REFERENCES blanks(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );

            -- 鞋模表
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 匹配任务表
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                selected_blank_ids JSON,
                status TEXT NOT NULL DEFAULT 'pending',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
            );

            -- 匹配结果表
            CREATE TABLE IF NOT EXISTS match_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                blank_id INTEGER NOT NULL,
                result_data JSON,
                coverage_rate REAL,
                volume_ratio REAL,
                p15_clearance REAL,
                min_clearance REAL,
                passed BOOLEAN DEFAULT 0,
                heatmap_path TEXT,
                ply_path TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
                FOREIGN KEY (blank_id) REFERENCES blanks(id) ON DELETE CASCADE
            );

            -- 索引
            CREATE INDEX IF NOT EXISTS idx_blank_categories_blank ON blank_categories(blank_id);
            CREATE INDEX IF NOT EXISTS idx_blank_categories_category ON blank_categories(category_id);
            CREATE INDEX IF NOT EXISTS idx_matches_model ON matches(model_id);
            CREATE INDEX IF NOT EXISTS idx_match_results_match ON match_results(match_id);
            CREATE INDEX IF NOT EXISTS idx_match_results_passed ON match_results(passed);
        `;

        this.db.exec(schema);
    }

    private async initializeDefaultData(): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');

        // 检查是否已有数据
        const count = this.db.prepare('SELECT COUNT(*) as count FROM categories').get() as any;
        if (count.count > 0) return;

        // 插入默认分类
        const insertCategory = this.db.prepare(`
            INSERT INTO categories (parent_id, name, level, path) 
            VALUES (?, ?, ?, ?)
        `);

        const categories = [
            { parent_id: null, name: '鞋型', level: 0, path: '/鞋型' },
            { parent_id: 1, name: '尖头', level: 1, path: '/鞋型/尖头' },
            { parent_id: 1, name: '圆头', level: 1, path: '/鞋型/圆头' },
            { parent_id: 1, name: '方头', level: 1, path: '/鞋型/方头' },
            { parent_id: null, name: '高度', level: 0, path: '/高度' },
            { parent_id: 5, name: '高帮', level: 1, path: '/高度/高帮' },
            { parent_id: 5, name: '中帮', level: 1, path: '/高度/中帮' },
            { parent_id: 5, name: '低帮', level: 1, path: '/高度/低帮' },
            { parent_id: null, name: '跟型', level: 0, path: '/跟型' },
            { parent_id: 9, name: '高跟', level: 1, path: '/跟型/高跟' },
            { parent_id: 9, name: '中跟', level: 1, path: '/跟型/中跟' },
            { parent_id: 9, name: '低跟', level: 1, path: '/跟型/低跟' },
            { parent_id: 9, name: '平跟', level: 1, path: '/跟型/平跟' }
        ];

        const transaction = this.db.transaction(() => {
            for (const cat of categories) {
                insertCategory.run(cat.parent_id, cat.name, cat.level, cat.path);
            }
        });

        transaction();
    }

    // === 分类管理 ===
    async getCategories(): Promise<any[]> {
        if (!this.db) throw new Error('数据库未连接');
        return this.db.prepare('SELECT * FROM categories ORDER BY path').all();
    }

    async createCategory(data: any): Promise<number> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            INSERT INTO categories (parent_id, name, level, path) 
            VALUES (?, ?, ?, ?)
        `);
        const result = stmt.run(data.parent_id, data.name, data.level, data.path);
        return result.lastInsertRowid as number;
    }

    async updateCategory(id: number, data: any): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            UPDATE categories SET name = ?, path = ? WHERE id = ?
        `);
        stmt.run(data.name, data.path, id);
    }

    async deleteCategory(id: number): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        this.db.prepare('DELETE FROM categories WHERE id = ?').run(id);
    }

    // === 粗胚管理 ===
    async getBlanks(filters?: any): Promise<any[]> {
        if (!this.db) throw new Error('数据库未连接');
        let query = 'SELECT * FROM blanks';
        const params: any[] = [];

        if (filters?.categoryId) {
            query = `
                SELECT DISTINCT b.* FROM blanks b
                JOIN blank_categories bc ON b.id = bc.blank_id
                WHERE bc.category_id = ?
            `;
            params.push(filters.categoryId);
        }

        query += ' ORDER BY created_at DESC';
        return this.db.prepare(query).all(...params);
    }

    async getBlankById(id: number): Promise<any> {
        if (!this.db) throw new Error('数据库未连接');
        return this.db.prepare('SELECT * FROM blanks WHERE id = ?').get(id);
    }

    async createBlank(data: any): Promise<number> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            INSERT INTO blanks (name, file_path, metadata, tags) 
            VALUES (?, ?, ?, ?)
        `);
        const result = stmt.run(
            data.name, 
            data.file_path, 
            JSON.stringify(data.metadata || {}),
            JSON.stringify(data.tags || [])
        );
        return result.lastInsertRowid as number;
    }

    async updateBlank(id: number, data: any): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            UPDATE blanks 
            SET name = ?, metadata = ?, tags = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        `);
        stmt.run(
            data.name,
            JSON.stringify(data.metadata || {}),
            JSON.stringify(data.tags || []),
            id
        );
    }

    async deleteBlank(id: number): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        
        // 获取文件路径以便删除文件
        const blank = this.getBlankById(id) as any;
        if (blank && blank.file_path && fs.existsSync(blank.file_path)) {
            fs.unlinkSync(blank.file_path);
        }
        
        this.db.prepare('DELETE FROM blanks WHERE id = ?').run(id);
    }

    // === 粗胚分类关联 ===
    async addBlankToCategory(blankId: number, categoryId: number): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            INSERT OR IGNORE INTO blank_categories (blank_id, category_id) 
            VALUES (?, ?)
        `);
        stmt.run(blankId, categoryId);
    }

    async removeBlankFromCategory(blankId: number, categoryId: number): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            DELETE FROM blank_categories 
            WHERE blank_id = ? AND category_id = ?
        `);
        stmt.run(blankId, categoryId);
    }

    async getBlankCategories(blankId: number): Promise<any[]> {
        if (!this.db) throw new Error('数据库未连接');
        return this.db.prepare(`
            SELECT c.* FROM categories c
            JOIN blank_categories bc ON c.id = bc.category_id
            WHERE bc.blank_id = ?
        `).all(blankId);
    }

    async getBlanksByCategory(categoryId: number): Promise<any[]> {
        if (!this.db) throw new Error('数据库未连接');
        return this.db.prepare(`
            SELECT b.* FROM blanks b
            JOIN blank_categories bc ON b.id = bc.blank_id
            WHERE bc.category_id = ?
        `).all(categoryId);
    }

    // === 鞋模管理 ===
    async getModels(filters?: any): Promise<any[]> {
        if (!this.db) throw new Error('数据库未连接');
        return this.db.prepare('SELECT * FROM models ORDER BY created_at DESC').all();
    }

    async getModelById(id: number): Promise<any> {
        if (!this.db) throw new Error('数据库未连接');
        return this.db.prepare('SELECT * FROM models WHERE id = ?').get(id);
    }

    async createModel(data: any): Promise<number> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            INSERT INTO models (name, file_path, metadata) 
            VALUES (?, ?, ?)
        `);
        const result = stmt.run(
            data.name,
            data.file_path,
            JSON.stringify(data.metadata || {})
        );
        return result.lastInsertRowid as number;
    }

    async deleteModel(id: number): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        
        // 获取文件路径以便删除文件
        const model = this.getModelById(id) as any;
        if (model && model.file_path && fs.existsSync(model.file_path)) {
            fs.unlinkSync(model.file_path);
        }
        
        this.db.prepare('DELETE FROM models WHERE id = ?').run(id);
    }

    // === 匹配管理 ===
    async createMatch(data: any): Promise<number> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            INSERT INTO matches (model_id, selected_blank_ids, status) 
            VALUES (?, ?, ?)
        `);
        const result = stmt.run(
            data.model_id,
            JSON.stringify(data.selected_blank_ids || []),
            'processing'
        );
        return result.lastInsertRowid as number;
    }

    async updateMatchStatus(id: number, status: string, error?: string): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            UPDATE matches 
            SET status = ?, completed_at = CURRENT_TIMESTAMP, error_message = ?
            WHERE id = ?
        `);
        stmt.run(status, error || null, id);
    }

    async saveMatchResult(data: any): Promise<void> {
        if (!this.db) throw new Error('数据库未连接');
        const stmt = this.db.prepare(`
            INSERT INTO match_results (
                match_id, blank_id, result_data, 
                coverage_rate, volume_ratio, p15_clearance, 
                min_clearance, passed, heatmap_path, ply_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        stmt.run(
            data.match_id,
            data.blank_id,
            JSON.stringify(data.result_data || {}),
            data.coverage_rate,
            data.volume_ratio,
            data.p15_clearance,
            data.min_clearance,
            data.passed ? 1 : 0,
            data.heatmap_path || null,
            data.ply_path || null
        );
    }

    async getMatches(filters?: any): Promise<any[]> {
        if (!this.db) throw new Error('数据库未连接');
        return this.db.prepare(`
            SELECT m.*, mo.name as model_name 
            FROM matches m
            JOIN models mo ON m.model_id = mo.id
            ORDER BY m.started_at DESC
        `).all();
    }

    async getMatchResults(matchId: number): Promise<any[]> {
        if (!this.db) throw new Error('数据库未连接');
        return this.db.prepare(`
            SELECT mr.*, b.name as blank_name 
            FROM match_results mr
            JOIN blanks b ON mr.blank_id = b.id
            WHERE mr.match_id = ?
            ORDER BY mr.p15_clearance DESC
        `).all(matchId);
    }

    // === 统计 ===
    async getStatistics(): Promise<any> {
        if (!this.db) throw new Error('数据库未连接');
        
        const stats = {
            totalBlanks: (this.db.prepare('SELECT COUNT(*) as count FROM blanks').get() as any).count,
            totalModels: (this.db.prepare('SELECT COUNT(*) as count FROM models').get() as any).count,
            totalMatches: (this.db.prepare('SELECT COUNT(*) as count FROM matches').get() as any).count,
            successfulMatches: (this.db.prepare('SELECT COUNT(*) as count FROM matches WHERE status = "completed"').get() as any).count,
            totalPassedResults: (this.db.prepare('SELECT COUNT(*) as count FROM match_results WHERE passed = 1').get() as any).count
        };
        
        return stats;
    }

    async close(): Promise<void> {
        if (this.db) {
            this.db.close();
            this.db = null;
            console.log('数据库连接已关闭');
        }
    }
}
