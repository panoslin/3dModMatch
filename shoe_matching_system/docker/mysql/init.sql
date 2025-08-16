-- MySQL初始化脚本
-- 3D鞋模智能匹配系统

-- 创建数据库 (如果不存在)
CREATE DATABASE IF NOT EXISTS shoe_matching CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE shoe_matching;

-- 设置时区
SET time_zone = '+08:00';

-- 创建用户权限 (如果不存在)
-- 注意：在生产环境中应使用更安全的密码
CREATE USER IF NOT EXISTS 'django_user'@'%' IDENTIFIED BY 'django_password_2024';
GRANT ALL PRIVILEGES ON shoe_matching.* TO 'django_user'@'%';

-- 刷新权限
FLUSH PRIVILEGES;

-- 显示创建结果
SELECT 'MySQL初始化完成' as status;
