#!/bin/bash

# 3D鞋模智能匹配系统 - 系统管理脚本

COMPOSE_FILE="docker-compose.prod.yml"

show_usage() {
    echo "3D鞋模智能匹配系统 - 系统管理"
    echo "使用方法: $0 [命令]"
    echo ""
    echo "可用命令:"
    echo "  start     - 启动所有服务"
    echo "  stop      - 停止所有服务"
    echo "  restart   - 重启所有服务"
    echo "  status    - 查看服务状态"
    echo "  logs      - 查看所有日志"
    echo "  web-logs  - 查看Web服务日志"
    echo "  celery-logs - 查看Celery日志"
    echo "  test      - 运行功能测试"
    echo "  backup    - 备份数据库"
    echo "  clean     - 清理系统（删除所有数据）"
    echo "  shell     - 进入Web容器shell"
    echo "  reset     - 重置并重新部署"
    echo ""
    echo "示例:"
    echo "  $0 start     # 启动系统"
    echo "  $0 status    # 查看状态"
    echo "  $0 logs      # 查看日志"
}

start_system() {
    echo "🚀 启动3D鞋模智能匹配系统..."
    
    # 检查环境变量文件
    if [ ! -f ".env" ]; then
        cp env.prod.example .env
        echo "📝 已创建 .env 文件，请根据需要修改配置"
    fi
    
    # 启动服务
    docker-compose -f $COMPOSE_FILE up -d
    
    echo "⏳ 等待服务启动..."
    sleep 10
    
    # 检查健康状态
    check_health
}

stop_system() {
    echo "🛑 停止3D鞋模智能匹配系统..."
    docker-compose -f $COMPOSE_FILE down
    echo "✅ 系统已停止"
}

restart_system() {
    echo "🔄 重启3D鞋模智能匹配系统..."
    docker-compose -f $COMPOSE_FILE restart
    echo "✅ 系统已重启"
}

show_status() {
    echo "📊 系统状态:"
    docker-compose -f $COMPOSE_FILE ps
    echo ""
    echo "🌐 网络状态:"
    docker network ls | grep shoe_matcher
    echo ""
    echo "💾 存储卷状态:"
    docker volume ls | grep webpage
}

show_logs() {
    echo "📝 查看系统日志 (按Ctrl+C退出):"
    docker-compose -f $COMPOSE_FILE logs -f
}

show_web_logs() {
    echo "📝 查看Web服务日志 (按Ctrl+C退出):"
    docker-compose -f $COMPOSE_FILE logs -f web
}

show_celery_logs() {
    echo "📝 查看Celery日志 (按Ctrl+C退出):"
    docker-compose -f $COMPOSE_FILE logs -f celery
}

run_test() {
    echo "🧪 运行功能测试..."
    if [ -f "test_matching_simple.py" ]; then
        python3 test_matching_simple.py
    else
        echo "❌ 测试脚本不存在"
    fi
}

backup_database() {
    echo "💾 备份数据库..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_file="backup_${timestamp}.sql"
    
    docker-compose -f $COMPOSE_FILE exec -T db pg_dump -U postgres shoe_matcher > $backup_file
    
    if [ -f "$backup_file" ]; then
        echo "✅ 数据库备份完成: $backup_file"
        gzip $backup_file
        echo "📦 备份文件已压缩: ${backup_file}.gz"
    else
        echo "❌ 数据库备份失败"
    fi
}

clean_system() {
    echo "🧹 清理系统..."
    read -p "⚠️ 这将删除所有数据，确定继续吗? (y/N): " confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        docker-compose -f $COMPOSE_FILE down -v
        docker system prune -f
        echo "✅ 系统清理完成"
    else
        echo "❌ 取消清理操作"
    fi
}

enter_shell() {
    echo "🐚 进入Web容器shell..."
    docker-compose -f $COMPOSE_FILE exec web bash
}

reset_system() {
    echo "🔄 重置并重新部署系统..."
    
    # 停止并清理
    docker-compose -f $COMPOSE_FILE down -v
    
    # 重新构建
    docker-compose -f $COMPOSE_FILE build --no-cache
    
    # 启动系统
    start_system
}

check_health() {
    echo "🩺 检查系统健康状态..."
    
    # 检查API健康
    if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
        echo "✅ API健康检查通过"
    else
        echo "❌ API健康检查失败"
        return 1
    fi
    
    # 检查服务状态
    unhealthy=$(docker-compose -f $COMPOSE_FILE ps | grep -v "Up\|healthy" | wc -l)
    if [ $unhealthy -eq 1 ]; then  # 1 for header line
        echo "✅ 所有服务运行正常"
    else
        echo "⚠️ 部分服务可能有问题"
        docker-compose -f $COMPOSE_FILE ps
    fi
}

# 主逻辑
case "${1:-}" in
    start)
        start_system
        ;;
    stop)
        stop_system
        ;;
    restart)
        restart_system
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    web-logs)
        show_web_logs
        ;;
    celery-logs)
        show_celery_logs
        ;;
    test)
        run_test
        ;;
    backup)
        backup_database
        ;;
    clean)
        clean_system
        ;;
    shell)
        enter_shell
        ;;
    reset)
        reset_system
        ;;
    health)
        check_health
        ;;
    *)
        show_usage
        ;;
esac
