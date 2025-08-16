"""
3D鞋模匹配系统核心视图
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import json
import logging

from .models import ShoeModel, BlankModel, MatchingResult, ProcessingLog
from .forms import FileUploadForm, AnalysisForm

logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    """首页视图"""
    template_name = 'core/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 基础统计数据
        context.update({
            'shoe_models_count': ShoeModel.objects.count(),
            'blank_models_count': BlankModel.objects.count(),
            'total_matches': MatchingResult.objects.count(),
            'recent_results': MatchingResult.objects.filter(
                is_optimal=True
            ).select_related('shoe_model', 'blank_model')[:5],
        })
        
        return context


class DashboardView(TemplateView):
    """仪表盘视图"""
    template_name = 'core/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 详细统计数据
        stats = {
            'shoe_models': {
                'total': ShoeModel.objects.count(),
                'processed': ShoeModel.objects.filter(is_processed=True).count(),
                'processing': ShoeModel.objects.filter(processing_status='processing').count(),
            },
            'blank_models': {
                'total': BlankModel.objects.count(),
                'processed': BlankModel.objects.filter(is_processed=True).count(),
            },
            'matching_results': {
                'total': MatchingResult.objects.count(),
                'optimal': MatchingResult.objects.filter(is_optimal=True).count(),
                'avg_utilization': MatchingResult.objects.aggregate(
                    avg=Avg('material_utilization')
                )['avg'] or 0,
            }
        }
        
        # 最近的文件
        recent_shoes = ShoeModel.objects.order_by('-created_at')[:10]
        recent_blanks = BlankModel.objects.order_by('-created_at')[:10]
        
        # 最佳匹配结果
        best_matches = MatchingResult.objects.filter(
            is_optimal=True
        ).select_related('shoe_model', 'blank_model').order_by(
            '-material_utilization'
        )[:10]
        
        context.update({
            'stats': stats,
            'recent_shoes': recent_shoes,
            'recent_blanks': recent_blanks,
            'best_matches': best_matches,
        })
        
        return context


class FileUploadView(FormView):
    """文件上传视图"""
    template_name = 'core/upload.html'
    form_class = FileUploadForm
    success_url = '/dashboard/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 添加统计数据
        from django.db.models import Avg
        context['stats'] = {
            'shoe_models': ShoeModel.objects.count(),
            'blank_models': BlankModel.objects.count(), 
            'total_matches': MatchingResult.objects.count(),
            'avg_utilization': MatchingResult.objects.aggregate(
                avg=Avg('material_utilization')
            )['avg'] or 0,
        }
        
        return context
    
    def form_valid(self, form):
        try:
            # 获取表单数据
            shoe_files = self.request.FILES.getlist('shoe_files')
            blank_files = self.request.FILES.getlist('blank_files')
            margin_distance = form.cleaned_data.get('margin_distance', 2.5)
            auto_process = form.cleaned_data.get('auto_process', True)
            
            uploaded_shoes = []
            uploaded_blanks = []
            
            # 处理鞋模文件
            for file in shoe_files:
                # 文件验证
                if not self._validate_file(file):
                    continue
                    
                shoe = ShoeModel.objects.create(
                    filename=file.name,
                    file=file,
                    file_size=file.size,
                    file_format=self._get_file_format(file.name),
                    uploaded_by=self.request.user if self.request.user.is_authenticated else None
                )
                uploaded_shoes.append(shoe)
                
                # 记录上传日志
                ProcessingLog.objects.create(
                    operation='upload',
                    level='info',
                    message=f'成功上传鞋模文件: {file.name} ({self._format_file_size(file.size)})',
                    shoe_model=shoe
                )
            
            # 处理粗胚文件
            for file in blank_files:
                # 文件验证
                if not self._validate_file(file):
                    continue
                    
                blank = BlankModel.objects.create(
                    filename=file.name,
                    file=file,
                    file_size=file.size,
                    file_format=self._get_file_format(file.name)
                )
                uploaded_blanks.append(blank)
                
                # 记录上传日志
                ProcessingLog.objects.create(
                    operation='upload',
                    level='info',
                    message=f'成功上传粗胚文件: {file.name} ({self._format_file_size(file.size)})',
                    blank_model=blank
                )
            
            # 触发文件处理
            if auto_process and (uploaded_shoes or uploaded_blanks):
                self._trigger_file_processing(uploaded_shoes, uploaded_blanks, margin_distance)
            
            messages.success(
                self.request,
                f'成功上传 {len(uploaded_shoes)} 个鞋模文件和 {len(uploaded_blanks)} 个粗胚文件！' +
                ('系统正在后台处理中...' if auto_process else '请手动开始处理。')
            )
            
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            messages.error(self.request, f'上传失败: {str(e)}')
            return self.form_invalid(form)
    
    def _validate_file(self, file):
        """验证文件"""
        valid_extensions = ['.3dm', '.mod', '.MOD']
        max_size = 100 * 1024 * 1024  # 100MB
        
        # 检查扩展名
        extension = '.' + file.name.split('.')[-1]
        if extension not in valid_extensions:
            logger.warning(f"不支持的文件格式: {file.name}")
            return False
        
        # 检查文件大小
        if file.size > max_size:
            logger.warning(f"文件过大: {file.name} ({self._format_file_size(file.size)})")
            return False
            
        return True
    
    def _get_file_format(self, filename):
        """获取文件格式"""
        return '3dm' if filename.lower().endswith('.3dm') else 'mod'
    
    def _format_file_size(self, size):
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        else:
            return f"{size/(1024*1024):.1f} MB"
    
    def _trigger_file_processing(self, shoe_models, blank_models, margin_distance):
        """触发文件处理"""
        try:
            # 注意：这里使用了简单的导入，实际项目中可能需要Celery等异步任务队列
            from apps.file_processing.tasks import process_uploaded_files
            process_uploaded_files.delay(
                shoe_ids=[s.id for s in shoe_models],
                blank_ids=[b.id for b in blank_models],
                margin_distance=margin_distance
            )
        except ImportError:
            # 如果没有Celery，可以同步处理或记录任务
            logger.info("异步任务处理不可用，将文件标记为待处理")


class FileListView(ListView):
    """文件列表视图"""
    template_name = 'core/file_list.html'
    context_object_name = 'files'
    paginate_by = 20
    
    def get_queryset(self):
        file_type = self.request.GET.get('type', 'all')
        search = self.request.GET.get('search', '')
        
        # 组合鞋模和粗胚文件
        shoe_query = ShoeModel.objects.all()
        blank_query = BlankModel.objects.all()
        
        if search:
            shoe_query = shoe_query.filter(filename__icontains=search)
            blank_query = blank_query.filter(filename__icontains=search)
        
        if file_type == 'shoes':
            return shoe_query.order_by('-created_at')
        elif file_type == 'blanks':
            return blank_query.order_by('-created_at')
        else:
            # 合并查询结果
            from itertools import chain
            return sorted(
                chain(shoe_query, blank_query),
                key=lambda x: x.created_at,
                reverse=True
            )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 添加统计数据
        shoe_count = ShoeModel.objects.count()
        blank_count = BlankModel.objects.count()
        processed_count = (
            ShoeModel.objects.filter(is_processed=True).count() +
            BlankModel.objects.filter(is_processed=True).count()
        )
        processing_count = (
            ShoeModel.objects.filter(processing_status='processing').count() +
            BlankModel.objects.filter(processing_status='processing').count()
        )
        
        context.update({
            'current_type': self.request.GET.get('type', 'all'),
            'search_query': self.request.GET.get('search', ''),
            'shoe_count': shoe_count,
            'blank_count': blank_count,
            'processed_count': processed_count,
            'processing_count': processing_count,
        })
        
        return context


class AnalysisView(TemplateView):
    """分析页面视图"""
    template_name = 'core/analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 获取可用的鞋模
        available_shoes = ShoeModel.objects.filter(is_processed=True)
        available_blanks = BlankModel.objects.filter(is_processed=True)
        
        context.update({
            'available_shoes': available_shoes,
            'available_blanks': available_blanks,
            'form': AnalysisForm(),
        })
        
        return context


class AnalysisDetailView(DetailView):
    """分析详情视图"""
    model = ShoeModel
    template_name = 'core/analysis_detail.html'
    context_object_name = 'shoe_model'
    pk_url_kwarg = 'shoe_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shoe_model = self.get_object()
        margin_distance = float(self.request.GET.get('margin', 2.5))
        
        # 获取匹配结果
        matching_results = MatchingResult.objects.filter(
            shoe_model=shoe_model,
            margin_distance=margin_distance,
            is_feasible=True
        ).select_related('blank_model').order_by('-material_utilization')
        
        # 最优匹配
        optimal_match = matching_results.filter(is_optimal=True).first()
        
        context.update({
            'margin_distance': margin_distance,
            'matching_results': matching_results[:10],  # 显示前10个结果
            'optimal_match': optimal_match,
            'available_blanks': BlankModel.objects.filter(is_processed=True).count(),
        })
        
        return context


class ResultsView(ListView):
    """结果列表视图"""
    model = MatchingResult
    template_name = 'core/results.html'
    context_object_name = 'results'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = MatchingResult.objects.select_related(
            'shoe_model', 'blank_model'
        ).order_by('-created_at')
        
        # 筛选条件
        show_optimal_only = self.request.GET.get('optimal', False)
        if show_optimal_only:
            queryset = queryset.filter(is_optimal=True)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_optimal_only'] = self.request.GET.get('optimal', False)
        
        # 统计信息
        context['stats'] = {
            'total_results': MatchingResult.objects.count(),
            'optimal_results': MatchingResult.objects.filter(is_optimal=True).count(),
            'avg_utilization': MatchingResult.objects.aggregate(
                avg=Avg('material_utilization')
            )['avg'] or 0,
        }
        
        return context


class ResultDetailView(DetailView):
    """结果详情视图"""
    model = MatchingResult
    template_name = 'core/result_detail.html'
    context_object_name = 'result'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.get_object()
        
        # 同一鞋模的其他匹配结果
        alternative_results = MatchingResult.objects.filter(
            shoe_model=result.shoe_model,
            is_feasible=True
        ).exclude(id=result.id).select_related('blank_model').order_by(
            '-material_utilization'
        )[:5]
        
        context.update({
            'alternative_results': alternative_results,
            'cost_savings': result.cost_savings,
        })
        
        return context


# AJAX API视图

@method_decorator(csrf_exempt, name='dispatch')
class StartMatchingView(View):
    """开始匹配分析的AJAX视图"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            shoe_id = data.get('shoe_id')
            margin_distance = float(data.get('margin', 2.5))
            
            if not shoe_id:
                return JsonResponse({'success': False, 'error': '缺少鞋模ID'})
            
            shoe_model = get_object_or_404(ShoeModel, id=shoe_id)
            
            # 异步启动匹配任务
            from apps.matching.tasks import perform_matching_analysis
            task = perform_matching_analysis.delay(shoe_id, margin_distance)
            
            return JsonResponse({
                'success': True,
                'task_id': task.id,
                'message': '匹配分析已开始，请稍候...'
            })
            
        except Exception as e:
            logger.error(f"启动匹配分析失败: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})


class GetProgressView(View):
    """获取进度的AJAX视图"""
    
    def get(self, request):
        task_id = request.GET.get('task_id')
        
        if not task_id:
            return JsonResponse({'success': False, 'error': '缺少任务ID'})
        
        try:
            # 这里应该查询Celery任务状态
            # 暂时返回模拟数据
            return JsonResponse({
                'success': True,
                'status': 'completed',
                'progress': 100,
                'result_url': '/results/'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


@method_decorator(csrf_exempt, name='dispatch') 
class DeleteFileView(View):
    """删除文件的AJAX视图"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            file_id = data.get('file_id')
            file_type = data.get('file_type')  # 'shoe' or 'blank'
            
            if file_type == 'shoe':
                file_obj = get_object_or_404(ShoeModel, id=file_id)
            else:
                file_obj = get_object_or_404(BlankModel, id=file_id)
            
            # 删除文件和数据库记录
            if file_obj.file:
                file_obj.file.delete()
            file_obj.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'文件 {file_obj.filename} 已删除'
            })
            
        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})


class MatchingView(TemplateView):
    """匹配功能主页面"""
    template_name = 'core/matching.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 获取可用的鞋模和粗胚
        context['available_shoes'] = ShoeModel.objects.filter(is_processed=True)
        context['available_blanks'] = BlankModel.objects.filter(is_processed=True)
        
        # 获取最近的匹配任务
        try:
            from apps.matching.models import MatchingTask
            context['recent_tasks'] = MatchingTask.objects.order_by('-created_at')[:10]
        except ImportError:
            context['recent_tasks'] = []
        
        return context


class MatchingResultsView(TemplateView):
    """匹配结果展示页面"""
    template_name = 'core/matching_results.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task_id = kwargs.get('task_id')
        
        try:
            from apps.matching.models import MatchingTask
            # 获取匹配任务
            task = get_object_or_404(MatchingTask, task_id=task_id)
            context['task'] = task
            
            # 获取匹配结果
            results = MatchingResult.objects.filter(
                shoe_model=task.shoe_model
            ).select_related('blank_model').order_by('-total_score')
            
            context['results'] = results
            context['optimal_match'] = results.first() if results.exists() else None
            context['shoe_model'] = task.shoe_model
            context['margin_distance'] = task.margin_distance
            context['processing_time'] = task.result_data.get('processing_time', 0)
            
        except ImportError:
            context['task'] = None
            context['results'] = []
            context['optimal_match'] = None
            context['shoe_model'] = None
            context['margin_distance'] = 2.5
            context['processing_time'] = 0
        
        return context


class FilePreviewView(TemplateView):
    """文件预览页面"""
    template_name = 'core/file_preview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        file_id = kwargs.get('pk')
        
        # 尝试获取鞋模或粗胚
        try:
            file_obj = ShoeModel.objects.get(id=file_id)
            context['file_obj'] = file_obj
            context['file_type'] = 'shoe'
        except ShoeModel.DoesNotExist:
            try:
                file_obj = BlankModel.objects.get(id=file_id)
                context['file_obj'] = file_obj
                context['file_type'] = 'blank'
            except BlankModel.DoesNotExist:
                context['file_obj'] = None
                context['file_type'] = None
        
        return context


class File3DView(TemplateView):
    """3D模型查看页面"""
    template_name = 'core/file_3d.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        file_id = kwargs.get('pk')
        
        # 获取文件对象
        try:
            file_obj = ShoeModel.objects.get(id=file_id)
            context['file_obj'] = file_obj
            context['file_type'] = 'shoe'
        except ShoeModel.DoesNotExist:
            try:
                file_obj = BlankModel.objects.get(id=file_id)
                context['file_obj'] = file_obj
                context['file_type'] = 'blank'
            except BlankModel.DoesNotExist:
                context['file_obj'] = None
                context['file_type'] = None
        
        return context


# API视图
class FileUploadAPIView(View):
    """文件上传API"""
    
    def post(self, request):
        try:
            form = FileUploadForm(request.POST, request.FILES)
            if form.is_valid():
                # 处理文件上传
                return JsonResponse({'success': True, 'message': '文件上传成功'})
            else:
                return JsonResponse({'success': False, 'errors': form.errors})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class FileListAPIView(View):
    """文件列表API"""
    
    def get(self, request):
        try:
            files = []
            
            # 获取鞋模
            shoes = ShoeModel.objects.all()
            for shoe in shoes:
                files.append({
                    'id': shoe.id,
                    'filename': shoe.filename,
                    'file_type': 'shoe',
                    'file_format': shoe.file_format,
                    'file_size': shoe.file_size,
                    'is_processed': shoe.is_processed,
                    'uploaded_at': shoe.created_at.isoformat() if hasattr(shoe, 'created_at') else None
                })
            
            # 获取粗胚
            blanks = BlankModel.objects.all()
            for blank in blanks:
                files.append({
                    'id': blank.id,
                    'filename': blank.filename,
                    'file_type': 'blank',
                    'file_format': blank.file_format,
                    'file_size': blank.file_size,
                    'is_processed': blank.is_processed,
                    'uploaded_at': blank.created_at.isoformat() if hasattr(blank, 'created_at') else None
                })
            
            return JsonResponse({'success': True, 'files': files})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class Model3DComparisonView(TemplateView):
    """3D模型对比视图"""
    template_name = 'core/3d_comparison.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 获取鞋模和粗胚ID
        shoe_id = self.request.GET.get('shoe_id')
        blank_id = self.request.GET.get('blank_id')
        
        if shoe_id and blank_id:
            try:
                shoe_model = ShoeModel.objects.get(id=shoe_id)
                blank_model = BlankModel.objects.get(id=blank_id)
                
                context['shoe_model'] = shoe_model
                context['blank_model'] = blank_model
                
                # 获取匹配结果数据
                try:
                    matching_result = MatchingResult.objects.filter(
                        shoe_model=shoe_model,
                        blank_model=blank_model
                    ).first()  # 获取第一个匹配结果
                    
                    context.update({
                        'match_score': matching_result.total_score,
                        'material_utilization': matching_result.material_utilization,
                        'coverage_score': matching_result.coverage_score,
                        'average_margin': matching_result.average_margin,
                        'min_margin': matching_result.min_margin,
                        'cost_savings': matching_result.cost_savings,
                    })
                    
                    # 计算匹配质量等级
                    if matching_result.total_score >= 80:
                        context['match_quality'] = 'excellent'
                    elif matching_result.total_score >= 60:
                        context['match_quality'] = 'good'
                    elif matching_result.total_score >= 40:
                        context['match_quality'] = 'fair'
                    else:
                        context['match_quality'] = 'poor'
                        
                except MatchingResult.DoesNotExist:
                    # 如果没有匹配结果，使用默认值
                    context.update({
                        'match_score': 0,
                        'material_utilization': 0,
                        'coverage_score': 0,
                        'average_margin': 0,
                        'min_margin': 0,
                        'cost_savings': 0,
                        'match_quality': 'poor'
                    })
                    
            except (ShoeModel.DoesNotExist, BlankModel.DoesNotExist):
                # 如果模型不存在，重定向到错误页面
                from django.shortcuts import redirect
                from django.contrib import messages
                messages.error(self.request, '指定的模型不存在')
                return redirect('core:matching')
        else:
            # 如果没有提供ID，重定向到匹配页面
            from django.shortcuts import redirect
            return redirect('core:matching')
        
        return context
