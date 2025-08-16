"""
匹配算法应用视图
"""

from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db import transaction
import json
import logging
from typing import List, Dict, Any
import time

from apps.core.models import ShoeModel, BlankModel, MatchingResult
from .algorithms import IntelligentMatcher, MatchingResult as AlgorithmResult
from .models import MatchingTask
from django.db import models

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AnalyzeMatchView(View):
    """匹配分析API视图"""
    
    def post(self, request):
        """执行匹配分析"""
        try:
            # 解析请求数据
            data = json.loads(request.body)
            shoe_model_id = data.get('shoe_model_id')
            margin_distance = float(data.get('margin_distance', 2.5))
            
            if not shoe_model_id:
                return JsonResponse({
                    'success': False,
                    'error': '缺少鞋模ID'
                })
            
            # 获取鞋模和所有粗胚
            shoe_model = get_object_or_404(ShoeModel, id=shoe_model_id)
            blank_models = BlankModel.objects.filter(is_processed=True)
            
            if not blank_models.exists():
                return JsonResponse({
                    'success': False,
                    'error': '没有可用的粗胚模型'
                })
            
            # 创建匹配任务
            import uuid
            task = MatchingTask.objects.create(
                task_id=f"match_{shoe_model.id}_{uuid.uuid4().hex[:8]}",
                status='processing',
                margin_distance=margin_distance,
                shoe_model=shoe_model
            )
            
            try:
                # 首先检查数据库中是否已有匹配结果
                existing_results = MatchingResult.objects.filter(
                    shoe_model=shoe_model,
                    margin_distance=margin_distance
                ).select_related('blank_model').order_by('-total_score')
                
                if existing_results.exists():
                    # 如果已有结果，直接返回
                    logger.info(f"找到现有匹配结果: {existing_results.count()} 个")
                    saved_results = list(existing_results)
                else:
                    # 如果没有结果，执行新的匹配
                    logger.info("执行新的智能匹配...")
                    matcher = IntelligentMatcher(
                        margin_distance=margin_distance,
                        weight_geometric=0.4,
                        weight_margin=0.4,
                        weight_efficiency=0.2
                    )
                    
                    algorithm_results = matcher.find_optimal_match(shoe_model, blank_models)
                    
                    # 保存匹配结果到数据库
                    saved_results = self._save_matching_results(
                        shoe_model, algorithm_results, margin_distance
                    )
                
                # 更新任务状态
                task.status = 'completed'
                task.result_data = {
                    'total_matches': len(saved_results),
                    'optimal_match': saved_results[0].id if saved_results else None,
                    'processing_time': sum(getattr(r, 'processing_time', 0) for r in saved_results),
                    'margin_distance': margin_distance
                }
                task.save()
                
                # 返回结果
                return JsonResponse({
                    'success': True,
                    'task_id': task.task_id,
                    'results': self._format_results(saved_results),
                    'optimal_match': self._format_optimal_match(saved_results[0]) if saved_results else None
                })
                
            except Exception as e:
                task.status = 'failed'
                task.save()
                raise e
                
        except Exception as e:
            logger.error(f"匹配分析失败: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def _save_matching_results(self, shoe_model: ShoeModel, 
                              algorithm_results: List[AlgorithmResult], 
                              margin_distance: float) -> List[MatchingResult]:
        """保存匹配结果到数据库"""
        saved_results = []
        
        for i, result in enumerate(algorithm_results):
            try:
                blank_model = BlankModel.objects.get(id=result.blank_id)
                
                # 判断是否为最优匹配
                is_optimal = (i == 0 and result.match_score > 0.5)
                
                # 计算成本节省
                cost_savings = self._calculate_cost_savings(result, algorithm_results)
                
                # 创建匹配结果
                matching_result = MatchingResult.objects.create(
                    shoe_model=shoe_model,
                    blank_model=blank_model,
                    margin_distance=margin_distance,
                    total_score=result.match_score * 100,  # 转换为0-100分
                    similarity_score=result.geometric_similarity * 100,
                    material_utilization=result.volume_efficiency * 100,
                    coverage_score=result.margin_coverage * 100,
                    size_compatibility_score=result.geometric_similarity * 100,
                    cost_effectiveness_score=result.volume_efficiency * 100,
                    average_margin=result.avg_margin,
                    min_margin=result.min_margin,
                    max_margin=result.max_margin,
                    is_feasible=result.margin_coverage >= 0.95,
                    is_optimal=is_optimal,
                    computation_time=result.processing_time,
                    analysis_details={
                        'geometric_similarity': result.geometric_similarity,
                        'min_margin': result.min_margin,
                        'max_margin': result.max_margin,
                        'avg_margin': result.avg_margin,
                        'margin_variance': result.margin_variance,
                        'processing_time': result.processing_time,
                        'margin_coverage': result.margin_coverage,
                        'volume_efficiency': result.volume_efficiency
                    }
                )
                
                saved_results.append(matching_result)
                
            except Exception as e:
                logger.error(f"保存匹配结果失败: {e}")
                continue
        
        return saved_results
    
    def _calculate_cost_savings(self, target_result: AlgorithmResult, 
                               all_results: List[AlgorithmResult]) -> float:
        """计算成本节省百分比"""
        try:
            # 找到满足余量要求的粗胚
            feasible_results = [r for r in all_results if r.margin_coverage >= 0.95]
            
            if not feasible_results:
                return 0.0
            
            # 假设成本与体积成正比，找到最大体积的可行粗胚
            max_volume = max(r.volume_efficiency for r in feasible_results)
            target_volume = target_result.volume_efficiency
            
            if max_volume <= 0 or target_volume <= 0:
                return 0.0
            
            # 计算成本节省
            cost_savings = ((max_volume - target_volume) / max_volume) * 100
            return max(0.0, cost_savings)
            
        except Exception as e:
            logger.error(f"成本节省计算失败: {e}")
            return 0.0
    
    def _format_results(self, results: List[MatchingResult]) -> List[Dict[str, Any]]:
        """格式化匹配结果"""
        formatted = []
        for result in results:
            formatted.append({
                'id': result.id,
                'blank_name': result.blank_model.filename,
                'blank_id': result.blank_model.id,
                'match_score': round(result.total_score, 2),
                'material_utilization': round(result.material_utilization, 2),
                'coverage_score': round(result.coverage_score, 2),
                'is_optimal': result.is_optimal,
                'is_feasible': result.is_feasible,
                'cost_savings': round(result.cost_savings, 2),
                'analysis_details': result.analysis_details
            })
        return formatted
    
    def _format_optimal_match(self, result: MatchingResult) -> Dict[str, Any]:
        """格式化最优匹配结果"""
        return {
            'id': result.id,
            'blank_name': result.blank_model.filename,
            'blank_id': result.blank_model.id,
            'match_score': round(result.total_score, 2),
            'material_utilization': round(result.material_utilization, 2),
            'coverage_score': round(result.coverage_score, 2),
            'cost_savings': round(result.cost_savings, 2),
            'summary': f"最优粗胚: {result.blank_model.filename}，匹配分数: {result.total_score:.1f}，材料利用率: {result.material_utilization:.1f}%"
        }


@method_decorator(csrf_exempt, name='dispatch')
class OptimizeMatchView(View):
    """匹配优化API视图"""
    
    def post(self, request):
        """优化匹配结果"""
        try:
            data = json.loads(request.body)
            matching_result_id = data.get('matching_result_id')
            
            if not matching_result_id:
                return JsonResponse({
                    'success': False,
                    'error': '缺少匹配结果ID'
                })
            
            # 获取匹配结果
            matching_result = get_object_or_404(MatchingResult, id=matching_result_id)
            
            # 执行优化分析
            optimization_result = self._optimize_match(matching_result)
            
            return JsonResponse({
                'success': True,
                'optimization': optimization_result
            })
            
        except Exception as e:
            logger.error(f"匹配优化失败: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def _optimize_match(self, matching_result: MatchingResult) -> Dict[str, Any]:
        """优化匹配结果"""
        try:
            # 分析当前匹配的改进空间
            current_score = matching_result.total_score
            current_utilization = matching_result.material_utilization
            
            # 计算改进建议
            improvements = []
            
            if current_score < 80:
                improvements.append("匹配分数较低，建议检查几何特征提取精度")
            
            if current_utilization < 70:
                improvements.append("材料利用率较低，建议寻找更小尺寸的粗胚")
            
            if current_utilization > 95:
                improvements.append("材料利用率过高，可能存在余量不足的风险")
            
            # 计算优化潜力
            optimization_potential = max(0, 100 - current_score)
            
            return {
                'current_score': current_score,
                'current_utilization': current_utilization,
                'optimization_potential': optimization_potential,
                'improvements': improvements,
                'recommendations': [
                    "考虑调整余量距离参数",
                    "检查点云数据质量",
                    "优化几何特征提取算法"
                ]
            }
            
        except Exception as e:
            logger.error(f"优化分析失败: {e}")
            return {
                'error': str(e)
            }


@method_decorator(csrf_exempt, name='dispatch')
class MatchHistoryView(View):
    """匹配历史视图"""
    
    def get(self, request):
        """获取匹配历史"""
        try:
            # 获取最近的匹配结果
            recent_matches = MatchingResult.objects.select_related(
                'shoe_model', 'blank_model'
            ).order_by('-processing_time')[:20]
            
            history = []
            for match in recent_matches:
                history.append({
                    'id': match.id,
                    'shoe_name': match.shoe_model.filename,
                    'blank_name': match.blank_model.filename,
                    'match_score': round(match.total_score, 2),
                    'material_utilization': round(match.material_utilization, 2),
                    'is_optimal': match.is_optimal,
                    'processing_time': match.processing_time.isoformat() if match.processing_time else None
                })
            
            return JsonResponse({
                'success': True,
                'history': history
            })
            
        except Exception as e:
            logger.error(f"获取匹配历史失败: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@method_decorator(csrf_exempt, name='dispatch')
class MatchStatisticsView(View):
    """匹配统计视图"""
    
    def get(self, request):
        """获取匹配统计信息"""
        try:
            # 统计信息
            total_matches = MatchingResult.objects.count()
            optimal_matches = MatchingResult.objects.filter(is_optimal=True).count()
            feasible_matches = MatchingResult.objects.filter(is_feasible=True).count()
            
            # 平均分数
            avg_score = MatchingResult.objects.aggregate(
                avg_score=models.Avg('total_score')
            )['avg_score'] or 0
            
            # 平均材料利用率
            avg_utilization = MatchingResult.objects.aggregate(
                avg_utilization=models.Avg('material_utilization')
            )['avg_utilization'] or 0
            
            return JsonResponse({
                'success': True,
                'statistics': {
                    'total_matches': total_matches,
                    'optimal_matches': optimal_matches,
                    'feasible_matches': feasible_matches,
                    'avg_score': round(avg_score, 2),
                    'avg_utilization': round(avg_utilization, 2),
                    'success_rate': round(feasible_matches / total_matches * 100, 2) if total_matches > 0 else 0
                }
            })
            
        except Exception as e:
            logger.error(f"获取匹配统计失败: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
