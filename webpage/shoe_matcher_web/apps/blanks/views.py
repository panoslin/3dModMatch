"""
粗胚管理视图
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from .models import BlankModel, BlankCategory
from .serializers import BlankModelSerializer, BlankCategorySerializer
from .pagination import BlankListPagination
import os

# 导入文件转换服务
from utils.file_conversion_service import FileConversionService


class BlankListCreateAPIView(generics.ListCreateAPIView):
    """粗胚列表和创建API"""
    queryset = BlankModel.objects.filter(is_active=True)
    serializer_class = BlankModelSerializer
    parser_classes = (MultiPartParser, FormParser)
    pagination_class = BlankListPagination
    
    def get_queryset(self):
        queryset = super().get_queryset()
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
        return queryset
    
    
    def create(self, request, *args, **kwargs):
        """创建新的粗胚 - 支持STL自动转换"""
        try:
            # 检查是否需要文件转换
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                return Response({
                    'success': False,
                    'error': 'no_file',
                    'message': '请选择要上传的文件'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            conversion_info = {}
            original_format = FileConversionService.get_file_format(uploaded_file)
            
            # 如果是STL文件，进行自动转换
            if FileConversionService.is_conversion_needed(uploaded_file):
                conversion_result = FileConversionService.convert_if_needed(
                    uploaded_file, 
                    user=request.user if request.user.is_authenticated else None
                )
                
                if not conversion_result['success']:
                    return Response({
                        'success': False,
                        'error': 'conversion_failed',
                        'message': f'文件转换失败: {conversion_result["error"]}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # 使用转换后的文件 - 确保使用正确的3DM文件名
                converted_file = conversion_result['converted_file']
                
                # 强制修改文件名为3DM格式 - 这次直接修改原始上传文件对象
                base_name = os.path.splitext(uploaded_file.name)[0]
                correct_3dm_name = f"{base_name}_converted.3dm"
                
                # 关键修复：直接修改上传文件对象的名称
                uploaded_file.name = correct_3dm_name
                # 替换文件内容但保持修改后的文件名
                uploaded_file.file = converted_file.file
                
                conversion_info = conversion_result['conversion_info']
            
            # 验证和保存模型
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            blank = serializer.save(is_active=True)  # 确保新创建的粗胚是活跃状态
            
            # 记录转换信息（如果有转换的话）
            if conversion_info:
                from datetime import datetime
                blank.original_format = original_format.lstrip('.')  # 去掉点号
                blank.conversion_info = conversion_info
                blank.converted_at = datetime.now()
                blank.save()
                
                # 转换服务已经返回正确命名的文件，无需重命名操作
                print(f"[转换成功] 文件已保存为: {blank.file.name}")
            
            # 异步处理3DM文件
            from .tasks import process_blank_file
            process_blank_file.delay(blank.id)
            
            # 准备响应消息
            message = '粗胚上传成功，正在处理中...'
            if conversion_info:
                message += f' (已从{original_format}格式自动转换)'
            
            response_data = serializer.data.copy()
            if conversion_info:
                response_data['conversion_info'] = FileConversionService.get_conversion_stats(conversion_info)
            
            return Response({
                'success': True,
                'data': response_data,
                'message': message
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'upload_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class BlankDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """粗胚详情API"""
    queryset = BlankModel.objects.filter(is_active=True)
    serializer_class = BlankModelSerializer
    
    def destroy(self, request, *args, **kwargs):
        """删除粗胚"""
        blank = self.get_object()
        blank.is_active = False  # 软删除
        blank.save()
        
        return Response({
            'success': True,
            'message': '粗胚删除成功'
        }, status=status.HTTP_200_OK)


class CategoryListCreateAPIView(generics.ListCreateAPIView):
    """分类列表和创建API"""
    queryset = BlankCategory.objects.filter(is_active=True)
    serializer_class = BlankCategorySerializer
    
    def list(self, request, *args, **kwargs):
        """获取分类树"""
        categories = self.get_queryset().filter(parent=None)
        serializer = self.get_serializer(categories, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """创建新分类"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            category = serializer.save()
            
            return Response({
                'success': True,
                'data': serializer.data,
                'message': '分类创建成功'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'create_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """分类详情API"""
    queryset = BlankCategory.objects.filter(is_active=True)
    serializer_class = BlankCategorySerializer
    
    def update(self, request, *args, **kwargs):
        """编辑分类"""
        try:
            category = self.get_object()
            
            # 验证父分类，防止循环引用
            parent_id = request.data.get('parent')
            if parent_id:
                if int(parent_id) == category.id:
                    return Response({
                        'success': False,
                        'error': 'invalid_parent',
                        'message': '分类不能设置自己为父分类'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # 检查是否会形成循环引用
                def check_circular_reference(parent_id, target_id):
                    try:
                        parent = BlankCategory.objects.get(id=parent_id)
                        if parent.parent and parent.parent.id == target_id:
                            return True
                        elif parent.parent:
                            return check_circular_reference(parent.parent.id, target_id)
                    except BlankCategory.DoesNotExist:
                        pass
                    return False
                
                if check_circular_reference(parent_id, category.id):
                    return Response({
                        'success': False,
                        'error': 'circular_reference',
                        'message': '不能形成循环引用'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(category, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            return Response({
                'success': True,
                'data': serializer.data,
                'message': '分类更新成功'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'update_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        """删除分类"""
        try:
            category = self.get_object()
            
            # 检查是否有子分类
            children_count = BlankCategory.objects.filter(parent=category, is_active=True).count()
            if children_count > 0:
                return Response({
                    'success': False,
                    'error': 'has_children',
                    'message': f'该分类下还有 {children_count} 个子分类，请先删除或移动子分类'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 检查是否有关联的粗胚
            blanks_count = BlankModel.objects.filter(categories=category, is_active=True).count()
            if blanks_count > 0:
                return Response({
                    'success': False,
                    'error': 'has_blanks',
                    'message': f'该分类下还有 {blanks_count} 个粗胚文件，请先删除或移动这些文件'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 软删除
            category.is_active = False
            category.save()
            
            return Response({
                'success': True,
                'message': '分类删除成功'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'delete_failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

