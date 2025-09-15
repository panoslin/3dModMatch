"""
初始化测试数据的Django管理命令
"""

import os
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files import File
from apps.blanks.models import BlankCategory, BlankModel
from apps.shoes.models import ShoeModel


class Command(BaseCommand):
    """初始化测试数据"""
    
    help = '初始化测试数据（粗胚文件和鞋模文件）'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--candidates-dir',
            default='/app/test_data/candidates',
            help='候选粗胚文件目录'
        )
        parser.add_argument(
            '--models-dir', 
            default='/app/test_data/models',
            help='鞋模文件目录'
        )
    
    def handle(self, *args, **options):
        """初始化测试数据"""
        candidates_dir = Path(options['candidates_dir'])
        models_dir = Path(options['models_dir'])
        
        self.stdout.write('开始初始化测试数据...')
        
        # 创建测试分类
        self.create_test_categories()
        
        # 导入粗胚文件
        if candidates_dir.exists():
            self.import_blank_files(candidates_dir)
        else:
            self.stdout.write(f'警告: 候选目录不存在 {candidates_dir}')
        
        # 导入鞋模文件
        if models_dir.exists():
            self.import_shoe_files(models_dir)
        else:
            self.stdout.write(f'警告: 鞋模目录不存在 {models_dir}')
        
        self.stdout.write(
            self.style.SUCCESS('测试数据初始化完成!')
        )
    
    def create_test_categories(self):
        """创建测试分类"""
        self.stdout.write('创建测试分类...')
        
        # 主分类
        main_category, created = BlankCategory.objects.get_or_create(
            name='测试粗胚',
            defaults={
                'description': '用于测试的粗胚分类',
                'sort_order': 1
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ 创建主分类: {main_category.name}')
        
        # 子分类
        subcategories = [
            ('小号粗胚', '小尺寸粗胚'),
            ('大号粗胚', '大尺寸粗胚'),
            ('加大粗胚', '加大尺寸粗胚'),
        ]
        
        for name, desc in subcategories:
            subcategory, created = BlankCategory.objects.get_or_create(
                name=name,
                parent=main_category,
                defaults={
                    'description': desc,
                    'sort_order': len(subcategories)
                }
            )
            
            if created:
                self.stdout.write(f'  ✅ 创建子分类: {subcategory.name}')
    
    def import_blank_files(self, candidates_dir):
        """导入粗胚文件"""
        self.stdout.write(f'从 {candidates_dir} 导入粗胚文件...')
        
        # 获取测试分类
        test_category = BlankCategory.objects.get(name='测试粗胚')
        
        # 查找3DM文件
        blank_files = list(candidates_dir.glob('*.3dm'))
        
        for blank_file in blank_files:
            # 检查是否已存在
            if BlankModel.objects.filter(name=blank_file.stem).exists():
                continue
            
            try:
                # 创建粗胚记录
                blank = BlankModel.objects.create(
                    name=blank_file.stem,
                    is_processed=True,  # 标记为已处理，跳过异步处理
                    processing_status='completed'
                )
                
                # 复制文件到media目录
                from django.conf import settings
                media_root = Path(settings.MEDIA_ROOT)
                media_path = media_root / 'blanks' / '2025' / '01'
                media_path.mkdir(parents=True, exist_ok=True)
                
                dest_file = media_path / blank_file.name
                shutil.copy2(blank_file, dest_file)
                
                # 设置文件字段
                blank.file.name = f'blanks/2025/01/{blank_file.name}'
                blank.categories.add(test_category)
                blank.save()
                
                self.stdout.write(f'  ✅ 导入粗胚: {blank.name}')
                
            except Exception as e:
                self.stdout.write(f'  ❌ 导入失败 {blank_file.name}: {e}')
    
    def import_shoe_files(self, models_dir):
        """导入鞋模文件"""
        self.stdout.write(f'从 {models_dir} 导入鞋模文件...')
        
        # 查找3DM文件
        shoe_files = list(models_dir.glob('*.3dm'))
        
        for shoe_file in shoe_files:
            # 检查是否已存在
            if ShoeModel.objects.filter(name=shoe_file.stem).exists():
                continue
            
            try:
                # 创建鞋模记录
                shoe = ShoeModel.objects.create(
                    name=shoe_file.stem,
                    is_processed=True,  # 标记为已处理，跳过异步处理
                    processing_status='completed'
                )
                
                # 复制文件到media目录
                from django.conf import settings
                media_root = Path(settings.MEDIA_ROOT)
                media_path = media_root / 'shoes' / '2025' / '01'
                media_path.mkdir(parents=True, exist_ok=True)
                
                dest_file = media_path / shoe_file.name
                shutil.copy2(shoe_file, dest_file)
                
                # 设置文件字段
                shoe.file.name = f'shoes/2025/01/{shoe_file.name}'
                shoe.save()
                
                self.stdout.write(f'  ✅ 导入鞋模: {shoe.name}')
                
            except Exception as e:
                self.stdout.write(f'  ❌ 导入失败 {shoe_file.name}: {e}')
