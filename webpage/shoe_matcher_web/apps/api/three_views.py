#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Three.js预览页面视图
为模型预览提供HTML页面和相关功能

作者：AI Assistant
创建时间：2024-09-25
版本：v1.0
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from apps.shoes.models import ShoeModel
from apps.blanks.models import BlankModel


@xframe_options_sameorigin
@cache_control(max_age=3600)  # 1小时缓存
def three_viewer_page(request, model_type, model_id):
    """
    Three.js模型预览页面
    
    Args:
        model_type: 模型类型 ('shoe' 或 'blank')
        model_id: 模型ID
        
    Returns:
        HTML页面响应
    """
    try:
        # 获取模型对象
        if model_type == 'shoe':
            model = get_object_or_404(ShoeModel, id=model_id)
            model_class_name = 'ShoeModel'
        elif model_type == 'blank':
            model = get_object_or_404(BlankModel, id=model_id)
            model_class_name = 'BlankModel'
        else:
            return HttpResponseNotFound('不支持的模型类型')
        
        # 检查模型是否支持Three.js渲染
        supports_threejs = model.is_ready_for_threejs() if hasattr(model, 'is_ready_for_threejs') else False
        
        # 准备上下文数据
        context = {
            'model': model,
            'model_type': model_type,
            'model_id': model_id,
            'model_class_name': model_class_name,
            'supports_threejs': supports_threejs,
            'optimization_status': getattr(model, 'optimization_status', {}) if hasattr(model, 'optimization_status') else {},
            'page_title': f'{model.name} - 3D预览',
            'api_base_url': f'/api/lod/{model_type}/{model_id}/',
        }
        
        return render(request, 'three_viewer.html', context)
        
    except Exception as e:
        # 错误处理
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>预览错误</title>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background: #f8f9fa;
                }}
                .error-container {{
                    text-align: center;
                    max-width: 400px;
                    padding: 40px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .error-icon {{
                    font-size: 64px;
                    margin-bottom: 20px;
                }}
                .error-title {{
                    font-size: 24px;
                    font-weight: 600;
                    color: #495057;
                    margin-bottom: 12px;
                }}
                .error-message {{
                    color: #6c757d;
                    margin-bottom: 20px;
                    line-height: 1.5;
                }}
                .error-action {{
                    margin-top: 20px;
                }}
                .btn {{
                    display: inline-block;
                    padding: 10px 20px;
                    background: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-icon">⚠️</div>
                <div class="error-title">预览加载失败</div>
                <div class="error-message">
                    无法加载3D模型预览：{str(e)}
                </div>
                <div class="error-action">
                    <a href="javascript:history.back()" class="btn">返回上页</a>
                </div>
            </div>
        </body>
        </html>
        """
        return HttpResponse(error_html, status=500, content_type='text/html')


@cache_control(max_age=86400)  # 24小时缓存
def three_viewer_embed(request, model_type, model_id):
    """
    Three.js查看器嵌入版本（用于iframe）
    
    Args:
        model_type: 模型类型
        model_id: 模型ID
        
    Returns:
        简化的HTML响应，适合嵌入
    """
    try:
        # 获取模型对象
        if model_type == 'shoe':
            model = get_object_or_404(ShoeModel, id=model_id)
        elif model_type == 'blank':
            model = get_object_or_404(BlankModel, id=model_id)
        else:
            return HttpResponseNotFound('不支持的模型类型')
        
        # 检查LOD支持
        has_lod = getattr(model, 'geometry_simplified', False)
        available_levels = getattr(model, 'available_lod_levels', []) if hasattr(model, 'available_lod_levels') else []
        
        # 生成嵌入式HTML
        embed_html = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{model.name} - 3D预览</title>
            
            <!-- Three.js依赖 -->
            <script src="https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/three@0.158.0/examples/js/controls/OrbitControls.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/three@0.158.0/examples/js/loaders/GLTFLoader.js"></script>
            
            <!-- 本地Three.js查看器 -->
            <script src="/static/js/three-model-viewer.js"></script>
            {('<script src="/static/js/advanced-model-viewer.js"></script>' if has_lod else '')}
            
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    width: 100vw;
                    height: 100vh;
                    overflow: hidden;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                }}
                
                #viewer-container {{
                    width: 100%;
                    height: 100%;
                    position: relative;
                }}
                
                .embed-overlay {{
                    position: absolute;
                    bottom: 16px;
                    left: 16px;
                    background: rgba(0, 0, 0, 0.7);
                    color: white;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    z-index: 100;
                    pointer-events: none;
                }}
                
                .lod-controls {{
                    position: absolute;
                    top: 16px;
                    right: 16px;
                    display: flex;
                    gap: 4px;
                    z-index: 100;
                }}
                
                .lod-btn {{
                    padding: 6px 10px;
                    background: rgba(255, 255, 255, 0.9);
                    border: 1px solid rgba(0, 0, 0, 0.1);
                    border-radius: 4px;
                    font-size: 11px;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                
                .lod-btn:hover {{
                    background: white;
                }}
                
                .lod-btn.active {{
                    background: #007bff;
                    color: white;
                    border-color: #007bff;
                }}
            </style>
        </head>
        <body>
            <div id="viewer-container">
                <!-- LOD控制（如果支持的话） -->
                {f'''
                <div class="lod-controls">
                    {chr(10).join([f'<button class="lod-btn" data-lod="{level}">{level.upper()}</button>' for level in available_levels])}
                </div>
                ''' if has_lod and available_levels else ''}
                
                <!-- 信息覆盖层 -->
                <div class="embed-overlay">
                    {model.name} | Three.js渲染器
                </div>
            </div>
            
            <script>
                let viewer = null;
                
                async function initEmbedViewer() {{
                    try {{
                        const ViewerClass = {'AdvancedModelViewer' if has_lod else 'ThreeModelViewer'};
                        
                        viewer = new ViewerClass('#viewer-container', {{
                            modelType: '{model_type}',
                            modelId: {model_id}
                        }});
                        
                        {f'''
                        // 启动高级功能
                        if (viewer.start) {{
                            await viewer.start();
                        }}
                        
                        // LOD按钮事件
                        document.querySelectorAll('.lod-btn').forEach(btn => {{
                            btn.addEventListener('click', async (e) => {{
                                const level = e.target.dataset.lod;
                                if (viewer.switchLOD) {{
                                    btn.textContent = 'Loading...';
                                    try {{
                                        await viewer.switchLOD(level);
                                        updateLODButtons(level);
                                    }} finally {{
                                        btn.textContent = level.toUpperCase();
                                    }}
                                }}
                            }});
                        }});
                        
                        function updateLODButtons(activeLevel) {{
                            document.querySelectorAll('.lod-btn').forEach(btn => {{
                                if (btn.dataset.lod === activeLevel) {{
                                    btn.classList.add('active');
                                }} else {{
                                    btn.classList.remove('active');
                                }}
                            }});
                        }}
                        
                        // 默认激活第一个LOD级别
                        const firstBtn = document.querySelector('.lod-btn');
                        if (firstBtn) {{
                            updateLODButtons(firstBtn.dataset.lod);
                        }}
                        ''' if has_lod else '''
                        // 直接加载模型
                        const response = await fetch(`/api/lod/{model_type}/{model_id}/data/?lod=preview&format=glb`);
                        if (response.ok) {{
                            const blob = await response.blob();
                            const url = URL.createObjectURL(blob);
                            await viewer.loadModel(url);
                        }}
                        '''}
                        
                        console.log('嵌入式3D查看器初始化成功');
                        
                    }} catch (error) {{
                        console.error('嵌入式查看器初始化失败:', error);
                        document.getElementById('viewer-container').innerHTML = `
                            <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #dc3545; text-align: center;">
                                <div>
                                    <div style="font-size: 24px; margin-bottom: 8px;">⚠️</div>
                                    <div>3D预览加载失败</div>
                                    <div style="font-size: 12px; margin-top: 8px; opacity: 0.7;">${{error.message}}</div>
                                </div>
                            </div>
                        `;
                    }}
                }}
                
                // 页面加载完成后初始化
                document.addEventListener('DOMContentLoaded', initEmbedViewer);
                
                // 清理
                window.addEventListener('beforeunload', () => {{
                    if (viewer && viewer.dispose) {{
                        viewer.dispose();
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        return HttpResponse(embed_html, content_type='text/html')
        
    except Exception as e:
        return HttpResponse(
            f'<div style="text-align:center; padding:40px; color:#dc3545;">嵌入式预览加载失败: {str(e)}</div>',
            status=500,
            content_type='text/html'
        )


def three_viewer_compatibility_check(request):
    """
    Three.js兼容性检查页面
    
    Returns:
        兼容性检查结果页面
    """
    check_html = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Three.js兼容性检查</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background: #f8f9fa;
            }
            
            .check-container {
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .check-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 0;
                border-bottom: 1px solid #e9ecef;
            }
            
            .check-item:last-child {
                border-bottom: none;
            }
            
            .check-label {
                font-weight: 500;
            }
            
            .check-result {
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
            }
            
            .check-result.pass {
                background: #d4edda;
                color: #155724;
            }
            
            .check-result.fail {
                background: #f8d7da;
                color: #721c24;
            }
            
            .check-result.warning {
                background: #fff3cd;
                color: #856404;
            }
            
            .overall-status {
                text-align: center;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
                font-size: 18px;
                font-weight: 600;
            }
            
            .overall-status.compatible {
                background: #d4edda;
                color: #155724;
            }
            
            .overall-status.incompatible {
                background: #f8d7da;
                color: #721c24;
            }
            
            .recommendations {
                background: #e2e3e5;
                padding: 16px;
                border-radius: 4px;
                margin-top: 20px;
            }
            
            .recommendations h4 {
                margin-bottom: 12px;
                color: #495057;
            }
            
            .recommendations ul {
                margin: 0;
                padding-left: 20px;
            }
            
            .recommendations li {
                margin: 6px 0;
                color: #6c757d;
            }
        </style>
    </head>
    <body>
        <div class="check-container">
            <h2>Three.js兼容性检查</h2>
            <p>检查您的浏览器是否支持Three.js 3D渲染功能</p>
            
            <div id="check-results">
                <div class="check-item">
                    <div class="check-label">正在检查...</div>
                    <div class="check-result">请等待</div>
                </div>
            </div>
            
            <div id="overall-status" class="overall-status">
                检查中...
            </div>
            
            <div id="recommendations" class="recommendations" style="display: none;">
                <h4>建议：</h4>
                <ul id="recommendation-list"></ul>
            </div>
        </div>
        
        <script>
            async function runCompatibilityCheck() {
                const results = [];
                const recommendations = [];
                
                // WebGL支持检查
                const canvas = document.createElement('canvas');
                const webglContext = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                results.push({
                    label: 'WebGL支持',
                    passed: !!webglContext,
                    critical: true
                });
                if (!webglContext) {
                    recommendations.push('升级浏览器到最新版本');
                    recommendations.push('更新显卡驱动程序');
                }
                
                // WebGL 2支持检查
                const webgl2Context = canvas.getContext('webgl2');
                results.push({
                    label: 'WebGL 2支持',
                    passed: !!webgl2Context,
                    critical: false
                });
                
                // JavaScript ES6支持
                let es6Support = false;
                try {
                    new Function('(a = 0) => a');
                    es6Support = true;
                } catch (e) {}
                results.push({
                    label: 'ES6支持',
                    passed: es6Support,
                    critical: true
                });
                if (!es6Support) {
                    recommendations.push('使用现代浏览器（Chrome 58+, Firefox 55+, Safari 10.1+）');
                }
                
                // Fetch API支持
                results.push({
                    label: 'Fetch API支持',
                    passed: typeof fetch !== 'undefined',
                    critical: true
                });
                
                // Canvas支持
                results.push({
                    label: 'Canvas支持',
                    passed: !!document.createElement('canvas').getContext,
                    critical: true
                });
                
                // 设备内存（如果可用）
                const deviceMemory = navigator.deviceMemory;
                results.push({
                    label: `设备内存 (${deviceMemory ? deviceMemory + 'GB' : '未知'})`,
                    passed: !deviceMemory || deviceMemory >= 2,
                    critical: false
                });
                if (deviceMemory && deviceMemory < 2) {
                    recommendations.push('建议使用内存更大的设备以获得更好性能');
                }
                
                // GPU信息（如果可用）
                if (webglContext) {
                    const debugInfo = webglContext.getExtension('WEBGL_debug_renderer_info');
                    if (debugInfo) {
                        const renderer = webglContext.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                        results.push({
                            label: `GPU: ${renderer.substring(0, 50)}`,
                            passed: true,
                            critical: false
                        });
                    }
                }
                
                // 移动设备检查
                const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
                results.push({
                    label: '设备类型',
                    passed: !isMobile,
                    critical: false,
                    value: isMobile ? '移动设备' : '桌面设备'
                });
                if (isMobile) {
                    recommendations.push('移动设备可能需要较低的渲染质量以保证性能');
                }
                
                // 显示结果
                displayResults(results, recommendations);
            }
            
            function displayResults(results, recommendations) {
                const container = document.getElementById('check-results');
                const overallStatus = document.getElementById('overall-status');
                const recommendationContainer = document.getElementById('recommendations');
                const recommendationList = document.getElementById('recommendation-list');
                
                container.innerHTML = '';
                
                let criticalFailures = 0;
                let totalFailures = 0;
                
                results.forEach(result => {
                    const item = document.createElement('div');
                    item.className = 'check-item';
                    
                    const label = document.createElement('div');
                    label.className = 'check-label';
                    label.textContent = result.label;
                    
                    const status = document.createElement('div');
                    status.className = 'check-result';
                    
                    if (result.passed) {
                        status.classList.add('pass');
                        status.textContent = result.value || '✓ 支持';
                    } else {
                        if (result.critical) {
                            status.classList.add('fail');
                            status.textContent = '✗ 不支持';
                            criticalFailures++;
                        } else {
                            status.classList.add('warning');
                            status.textContent = '⚠ 有限支持';
                        }
                        totalFailures++;
                    }
                    
                    item.appendChild(label);
                    item.appendChild(status);
                    container.appendChild(item);
                });
                
                // 总体状态
                if (criticalFailures === 0) {
                    overallStatus.className = 'overall-status compatible';
                    overallStatus.textContent = totalFailures === 0 ? 
                        '✓ 完全兼容 - 您的浏览器支持Three.js高性能渲染' :
                        '✓ 基本兼容 - 可以使用Three.js，但可能有性能限制';
                } else {
                    overallStatus.className = 'overall-status incompatible';
                    overallStatus.textContent = '✗ 不兼容 - 您的浏览器不支持Three.js渲染';
                }
                
                // 建议
                if (recommendations.length > 0) {
                    recommendationContainer.style.display = 'block';
                    recommendationList.innerHTML = '';
                    recommendations.forEach(rec => {
                        const li = document.createElement('li');
                        li.textContent = rec;
                        recommendationList.appendChild(li);
                    });
                }
            }
            
            // 页面加载后运行检查
            document.addEventListener('DOMContentLoaded', runCompatibilityCheck);
        </script>
    </body>
    </html>
    """
    
    return HttpResponse(check_html, content_type='text/html')
