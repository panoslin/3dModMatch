"""
3D鞋模匹配系统核心视图
简化版一站式工作台设计
"""

import json
import logging
import os
from typing import Dict, List, Any

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView
from django.core.files.storage import default_storage
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg

from .models import ShoeModel, BlankModel, MatchingResult, ProcessingLog
from apps.file_processing.parsers import ModelFileParser
from apps.matching.algorithms import IntelligentMatcher

logger = logging.getLogger(__name__)


class DashboardView(TemplateView):
    """一站式工作台视图"""
    template_name = 'core/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 获取所有粗胚（资源库）
        blanks = BlankModel.objects.filter(is_processed=True).order_by('volume')
        
        # 获取鞋模列表（分页）
        shoes = ShoeModel.objects.filter(is_processed=True).order_by('-created_at')
        
        # 搜索功能
        search_query = ''
        if hasattr(self, 'request') and self.request:
            search_query = self.request.GET.get('search', '')
            if search_query:
                shoes = shoes.filter(
                    Q(filename__icontains=search_query) |
                    Q(id__icontains=search_query)
                )
        
        # 分页
        paginator = Paginator(shoes, 20)  # 每页20个
        page_number = 1
        if hasattr(self, 'request') and self.request:
            page_number = self.request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # 为每个鞋模获取最佳匹配结果
        for shoe in page_obj:
            # 获取该鞋模的最优匹配
            best_match = MatchingResult.objects.filter(
                shoe_model=shoe,
                is_optimal=True
            ).select_related('blank_model').first()
            
            shoe.best_match = best_match
            
            # 如果没有匹配结果，标记为需要分析
            if not best_match:
                shoe.needs_analysis = True
                shoe.match_status = 'pending'
            else:
                shoe.needs_analysis = False
                shoe.match_status = 'completed'
        
        # 统计信息
        stats = {
            'total_shoes': ShoeModel.objects.count(),
            'total_blanks': BlankModel.objects.count(),
            'total_matches': MatchingResult.objects.filter(is_optimal=True).count(),
            'avg_utilization': MatchingResult.objects.filter(
                is_optimal=True
            ).aggregate(avg=Avg('material_utilization'))['avg'] or 0
        }
        
        context.update({
            'blanks': blanks,
            'shoes': page_obj,
            'search_query': search_query,
            'stats': stats,
            'page_obj': page_obj,
        })
        
        return context


class FileUploadView(View):
    """文件上传视图（支持Ajax）"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        """处理文件上传"""
        try:
            file_type = request.POST.get('type', 'shoe')  # shoe 或 blank
            files = request.FILES.getlist('files')
            
            if not files:
                return JsonResponse({
                    'success': False,
                    'error': '没有选择文件'
                })
            
            uploaded_files = []
            
            for file in files:
                # 保存文件
                file_name = file.name
                file_path = f"{'shoes' if file_type == 'shoe' else 'blanks'}/{file_name}"
                saved_path = default_storage.save(file_path, file)
                
                # 解析文件
                full_path = os.path.join(default_storage.location, saved_path)
                parser = ModelFileParser(full_path)
                parse_result = parser.parse()
                
                if parse_result.get('success'):
                    # 创建模型记录
                    if file_type == 'shoe':
                        model = ShoeModel.objects.create(
                            filename=file_name,
                            file=saved_path,
                            file_size=file.size,
                            file_format='3dm' if file_name.lower().endswith('.3dm') else 'mod',
                            volume=parse_result.get('volume'),
                            bounding_box=parse_result.get('bounds', {}),
                            key_features=parse_result,
                            points_count=parse_result.get('points_count', 0),
                            is_processed=True,
                            processing_status='completed'
                        )
                        model_type = '鞋模'
                    else:
                        model = BlankModel.objects.create(
                            filename=file_name,
                            file=saved_path,
                            file_size=file.size,
                            file_format='3dm' if file_name.lower().endswith('.3dm') else 'mod',
                            volume=parse_result.get('volume'),
                            bounding_box=parse_result.get('bounds', {}),
                            key_features=parse_result,
                            points_count=parse_result.get('points_count', 0),
                            is_processed=True,
                            processing_status='completed'
                        )
                        model_type = '粗胚'
                    
                    uploaded_files.append({
                        'id': model.id,
                        'filename': file_name,
                        'type': model_type,
                        'volume': float(model.volume) if model.volume else 0,
                        'status': 'success'
                    })
                    
                    # 记录日志
                    ProcessingLog.objects.create(
                        operation='upload',
                        level='info',
                        message=f'成功上传{model_type}文件: {file_name}',
                        shoe_model=model if file_type == 'shoe' else None,
                        blank_model=model if file_type == 'blank' else None,
                        extra_data=parse_result
                    )
                else:
                    uploaded_files.append({
                        'filename': file_name,
                        'status': 'failed',
                        'error': parse_result.get('error', '解析失败')
                    })
            
            return JsonResponse({
                'success': True,
                'files': uploaded_files,
                'message': f'成功上传 {len([f for f in uploaded_files if f.get("status") == "success"])} 个文件'
            })
            
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class QuickMatchView(View):
    """快速匹配视图（Ajax）"""
    
    def post(self, request):
        """执行快速匹配分析"""
        try:
            shoe_id = request.POST.get('shoe_id')
            margin_distance = float(request.POST.get('margin_distance', 2.5))
            
            # 获取鞋模
            shoe = get_object_or_404(ShoeModel, id=shoe_id, is_processed=True)
            
            # 获取所有粗胚
            blanks = BlankModel.objects.filter(is_processed=True)
            
            if not blanks.exists():
                return JsonResponse({
                    'success': False,
                    'error': '没有可用的粗胚文件'
                })
            
            # 执行智能匹配
            matcher = IntelligentMatcher(margin_distance=margin_distance)
            results = matcher.find_optimal_match(shoe, list(blanks))
            
            if not results:
                return JsonResponse({
                    'success': False,
                    'error': '未找到合适的匹配方案'
                })
            
            # 保存最优结果
            best_result = results[0]
            best_blank = BlankModel.objects.get(id=best_result.blank_id)
            
            # 更新或创建匹配结果
            matching_result, created = MatchingResult.objects.update_or_create(
                shoe_model=shoe,
                blank_model=best_blank,
                margin_distance=margin_distance,
                defaults={
                    'total_score': best_result.match_score * 100,
                    'similarity_score': best_result.geometric_similarity * 100,
                    'material_utilization': best_result.volume_efficiency * 100,
                    'coverage_score': best_result.margin_coverage * 100,
                    'average_margin': best_result.avg_margin,
                    'min_margin': best_result.min_margin,
                    'max_margin': best_result.max_margin,
                    'is_optimal': True,
                    'is_feasible': best_result.margin_coverage >= 0.95,
                    'analysis_details': {
                        'margin_variance': best_result.margin_variance,
                        'processing_time': best_result.processing_time,
                        'all_results': [
                            {
                                'blank_id': r.blank_id,
                                'blank_name': r.blank_name,
                                'score': r.match_score,
                                'utilization': r.volume_efficiency
                            } for r in results[:5]  # 保存前5个结果
                        ]
                    },
                    'computation_time': best_result.processing_time
                }
            )
            
            # 标记其他结果为非最优
            MatchingResult.objects.filter(
                shoe_model=shoe
            ).exclude(id=matching_result.id).update(is_optimal=False)
            
            # 记录日志
            ProcessingLog.objects.create(
                operation='match',
                level='info',
                message=f'完成匹配分析: {shoe.filename} → {best_blank.filename}',
                shoe_model=shoe,
                blank_model=best_blank,
                extra_data={
                    'margin_distance': margin_distance,
                    'match_score': best_result.match_score,
                    'created': created
                }
            )
            
            # 返回结果
            return JsonResponse({
                'success': True,
                'result': {
                    'id': matching_result.id,
                    'blank_name': best_blank.filename,
                    'material_utilization': float(matching_result.material_utilization),
                    'average_margin': float(matching_result.average_margin),
                    'min_margin': float(matching_result.min_margin),
                    'total_score': float(matching_result.total_score),
                    'is_feasible': matching_result.is_feasible,
                    'alternatives': matching_result.analysis_details.get('all_results', [])
                },
                'message': '匹配分析完成'
            })
            
        except Exception as e:
            logger.error(f"匹配分析失败: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class MatchingDetailView(View):
    """匹配详情视图（Ajax）"""
    
    def get(self, request, matching_id):
        """获取匹配详情数据"""
        try:
            matching = get_object_or_404(
                MatchingResult,
                id=matching_id
            )
            
            # 准备3D可视化数据
            shoe_features = matching.shoe_model.key_features or {}
            blank_features = matching.blank_model.key_features or {}
            
            # 生成热力图数据（模拟）
            heatmap_data = self._generate_heatmap_data(matching)
            
            # 生成截面数据（模拟）
            cross_section_data = self._generate_cross_section_data(matching)
            
            return JsonResponse({
                'success': True,
                'data': {
                    'matching': {
                        'id': matching.id,
                        'shoe_name': matching.shoe_model.filename,
                        'blank_name': matching.blank_model.filename,
                        'total_score': float(matching.total_score),
                        'material_utilization': float(matching.material_utilization),
                        'average_margin': float(matching.average_margin),
                        'min_margin': float(matching.min_margin),
                        'max_margin': float(matching.max_margin),
                        'is_feasible': matching.is_feasible,
                    },
                    'shoe_model': {
                        'id': matching.shoe_model.id,
                        'filename': matching.shoe_model.filename,
                        'volume': float(matching.shoe_model.volume) if matching.shoe_model.volume else 0,
                        'bounds': matching.shoe_model.bounding_box,
                        'points_count': matching.shoe_model.points_count,
                    },
                    'blank_model': {
                        'id': matching.blank_model.id,
                        'filename': matching.blank_model.filename,
                        'volume': float(matching.blank_model.volume) if matching.blank_model.volume else 0,
                        'bounds': matching.blank_model.bounding_box,
                        'points_count': matching.blank_model.points_count,
                    },
                    'visualization': {
                        'heatmap': heatmap_data,
                        'cross_section': cross_section_data,
                    },
                    'alternatives': matching.analysis_details.get('all_results', [])
                }
            })
            
        except Exception as e:
            logger.error(f"获取匹配详情失败: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def _generate_heatmap_data(self, matching: MatchingResult) -> Dict:
        """生成热力图数据（示例）"""
        import random
        
        # 生成示例热力图数据
        grid_size = 20
        heatmap = []
        
        for i in range(grid_size):
            row = []
            for j in range(grid_size):
                # 模拟余量分布
                if i < 5 or i > 15 or j < 5 or j > 15:
                    value = random.uniform(3.0, 5.0)  # 边缘余量充足
                else:
                    value = random.uniform(1.5, 3.0)  # 中心余量较小
                    
                row.append({
                    'x': i,
                    'y': j,
                    'value': value,
                    'color': '#27ae60' if value > 3 else '#f39c12' if value > 2 else '#e74c3c'
                })
            heatmap.append(row)
        
        return {
            'grid': heatmap,
            'min_value': matching.min_margin,
            'max_value': matching.max_margin,
            'avg_value': matching.average_margin
        }
    
    def _generate_cross_section_data(self, matching: MatchingResult) -> Dict:
        """生成截面数据（示例）"""
        # 生成示例截面数据
        sections = []
        
        for plane in ['xy', 'xz', 'yz']:
            section = {
                'plane': plane,
                'position': 0.5,  # 中心位置
                'shoe_contour': [],  # 鞋模轮廓点
                'blank_contour': [],  # 粗胚轮廓点
                'margin_points': []  # 余量点
            }
            
            # 生成示例轮廓（简化为圆形）
            import math
            for angle in range(0, 360, 10):
                rad = math.radians(angle)
                # 鞋模轮廓
                shoe_r = 50
                section['shoe_contour'].append({
                    'x': shoe_r * math.cos(rad),
                    'y': shoe_r * math.sin(rad)
                })
                # 粗胚轮廓（稍大）
                blank_r = 53
                section['blank_contour'].append({
                    'x': blank_r * math.cos(rad),
                    'y': blank_r * math.sin(rad)
                })
                # 余量
                section['margin_points'].append({
                    'x': shoe_r * math.cos(rad),
                    'y': shoe_r * math.sin(rad),
                    'margin': blank_r - shoe_r
                })
            
            sections.append(section)
        
        return {
            'sections': sections,
            'current_plane': 'xy',
            'current_position': 0.5
        }


class BatchProcessView(View):
    """批量处理视图"""
    
    def post(self, request):
        """批量匹配处理"""
        try:
            shoe_ids = request.POST.getlist('shoe_ids[]')
            margin_distance = float(request.POST.get('margin_distance', 2.5))
            
            if not shoe_ids:
                return JsonResponse({
                    'success': False,
                    'error': '请选择要处理的鞋模'
                })
            
            results = []
            success_count = 0
            
            # 获取所有粗胚
            blanks = list(BlankModel.objects.filter(is_processed=True))
            
            if not blanks:
                return JsonResponse({
                    'success': False,
                    'error': '没有可用的粗胚文件'
                })
            
            # 批量处理
            matcher = IntelligentMatcher(margin_distance=margin_distance)
            
            for shoe_id in shoe_ids:
                try:
                    shoe = ShoeModel.objects.get(id=shoe_id, is_processed=True)
                    
                    # 执行匹配
                    match_results = matcher.find_optimal_match(shoe, blanks)
                    
                    if match_results:
                        best_result = match_results[0]
                        best_blank = BlankModel.objects.get(id=best_result.blank_id)
                        
                        # 保存结果
                        matching_result, _ = MatchingResult.objects.update_or_create(
                            shoe_model=shoe,
                            blank_model=best_blank,
                            margin_distance=margin_distance,
                            defaults={
                                'total_score': best_result.match_score * 100,
                                'material_utilization': best_result.volume_efficiency * 100,
                                'average_margin': best_result.avg_margin,
                                'min_margin': best_result.min_margin,
                                'is_optimal': True,
                                'is_feasible': best_result.margin_coverage >= 0.95,
                            }
                        )
                        
                        results.append({
                            'shoe_id': shoe_id,
                            'shoe_name': shoe.filename,
                            'status': 'success',
                            'blank_name': best_blank.filename,
                            'utilization': float(matching_result.material_utilization)
                        })
                        success_count += 1
                    else:
                        results.append({
                            'shoe_id': shoe_id,
                            'shoe_name': shoe.filename,
                            'status': 'no_match',
                            'error': '未找到合适的匹配'
                        })
                        
                except Exception as e:
                    logger.error(f"处理鞋模 {shoe_id} 失败: {str(e)}")
                    results.append({
                        'shoe_id': shoe_id,
                        'status': 'error',
                        'error': str(e)
                    })
            
            return JsonResponse({
                'success': True,
                'results': results,
                'summary': {
                    'total': len(shoe_ids),
                    'success': success_count,
                    'failed': len(shoe_ids) - success_count
                },
                'message': f'批量处理完成: {success_count}/{len(shoe_ids)} 成功'
            })
            
        except Exception as e:
            logger.error(f"批量处理失败: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class ExportResultView(View):
    """导出结果视图"""
    
    def get(self, request, matching_id):
        """导出匹配结果报告"""
        try:
            matching = get_object_or_404(MatchingResult, id=matching_id)
            
            # 生成CSV报告
            import csv
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="matching_report_{matching_id}.csv"'
            
            # 写入BOM以支持Excel打开中文
            response.write('\ufeff')
            
            writer = csv.writer(response)
            writer.writerow(['3D鞋模匹配分析报告'])
            writer.writerow([])
            writer.writerow(['基本信息'])
            writer.writerow(['鞋模文件', matching.shoe_model.filename])
            writer.writerow(['粗胚文件', matching.blank_model.filename])
            writer.writerow(['匹配时间', matching.created_at.strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])
            writer.writerow(['匹配结果'])
            writer.writerow(['总体评分', f'{matching.total_score:.2f}%'])
            writer.writerow(['材料利用率', f'{matching.material_utilization:.2f}%'])
            writer.writerow(['几何相似度', f'{matching.similarity_score:.2f}%'])
            writer.writerow(['覆盖度评分', f'{matching.coverage_score:.2f}%'])
            writer.writerow([])
            writer.writerow(['余量分析'])
            writer.writerow(['平均余量', f'{matching.average_margin:.2f}mm'])
            writer.writerow(['最小余量', f'{matching.min_margin:.2f}mm'])
            writer.writerow(['最大余量', f'{matching.max_margin:.2f}mm'])
            writer.writerow(['余量要求', f'{matching.margin_distance:.2f}mm'])
            writer.writerow([])
            writer.writerow(['体积信息'])
            writer.writerow(['鞋模体积', f'{matching.shoe_model.volume:.2f} mm³' if matching.shoe_model.volume else '未知'])
            writer.writerow(['粗胚体积', f'{matching.blank_model.volume:.2f} mm³' if matching.blank_model.volume else '未知'])
            
            # 添加备选方案
            alternatives = matching.analysis_details.get('all_results', [])
            if alternatives:
                writer.writerow([])
                writer.writerow(['备选方案'])
                writer.writerow(['排名', '粗胚名称', '匹配分数', '材料利用率'])
                for i, alt in enumerate(alternatives[:5], 1):
                    writer.writerow([
                        i,
                        alt.get('blank_name', ''),
                        f"{alt.get('score', 0)*100:.2f}%",
                        f"{alt.get('utilization', 0)*100:.2f}%"
                    ])
            
            return response
            
        except Exception as e:
            logger.error(f"导出失败: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

