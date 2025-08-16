"""
3D鞋模匹配系统表单
"""

from django import forms
from django.core.validators import FileExtensionValidator
from django.conf import settings
from .models import ShoeModel, BlankModel


class MultipleFileInput(forms.ClearableFileInput):
    """支持多文件上传的自定义widget"""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """支持多文件上传的自定义字段"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class FileUploadForm(forms.Form):
    """文件上传表单"""
    
    shoe_files = MultipleFileField(
        label="鞋模文件",
        widget=MultipleFileInput(attrs={
            'multiple': True,
            'accept': '.3dm,.mod,.MOD',
            'class': 'form-control',
            'style': 'display: none;'  # 隐藏默认input，使用自定义界面
        }),
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['3dm', 'mod', 'MOD']
            )
        ],
        help_text="支持 .3dm 和 .MOD 格式，可多选"
    )
    
    blank_files = MultipleFileField(
        label="粗胚文件", 
        widget=MultipleFileInput(attrs={
            'multiple': True,
            'accept': '.3dm,.mod,.MOD',
            'class': 'form-control',
            'style': 'display: none;'  # 隐藏默认input，使用自定义界面
        }),
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['3dm', 'mod', 'MOD']
            )
        ],
        help_text="支持 .3dm 和 .MOD 格式，可多选"
    )
    
    margin_distance = forms.FloatField(
        label="余量距离 (mm)",
        initial=2.5,
        min_value=0.1,
        max_value=20.0,
        help_text="匹配时的最小余量距离，单位毫米",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'placeholder': '2.5'
        })
    )
    
    auto_process = forms.BooleanField(
        label="自动开始处理",
        initial=True,
        required=False,
        help_text="上传后立即开始文件分析和匹配",
        widget=forms.CheckboxInput(attrs={
            'class': 'custom-control-input'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        shoe_files = cleaned_data.get('shoe_files')
        blank_files = cleaned_data.get('blank_files')
        
        # 将单个文件转换为列表格式
        if shoe_files and not isinstance(shoe_files, list):
            shoe_files = [shoe_files]
        if blank_files and not isinstance(blank_files, list):
            blank_files = [blank_files]
        
        if not shoe_files and not blank_files:
            raise forms.ValidationError("请至少上传一个文件")
        
        # 检查文件大小
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 100 * 1024 * 1024)
        
        all_files = (shoe_files or []) + (blank_files or [])
        for file in all_files:
            if file and hasattr(file, 'size') and file.size > max_size:
                raise forms.ValidationError(
                    f"文件 {file.name} 太大，最大允许 {max_size // (1024*1024)}MB"
                )
        
        # 更新cleaned_data
        cleaned_data['shoe_files'] = shoe_files
        cleaned_data['blank_files'] = blank_files
        
        return cleaned_data


class AnalysisForm(forms.Form):
    """分析参数表单"""
    
    shoe_model = forms.ModelChoiceField(
        queryset=ShoeModel.objects.filter(is_processed=True),
        label="选择鞋模",
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="-- 请选择鞋模 --"
    )
    
    margin_distance = forms.DecimalField(
        label="余量距离 (mm)",
        initial=2.5,
        min_value=0.5,
        max_value=10.0,
        decimal_places=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'min': '0.5',
            'max': '10.0'
        }),
        help_text="设置粗胚与鞋模之间的间隙距离"
    )
    
    analysis_precision = forms.ChoiceField(
        label="分析精度",
        choices=[
            ('high', '高精度（较慢）'),
            ('medium', '中等精度'),
            ('fast', '快速分析'),
        ],
        initial='high',  # 始终使用高精度
        widget=forms.Select(attrs={'class': 'form-control', 'disabled': True}),
        help_text="系统将使用最高精度进行分析"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 更新鞋模选项
        self.fields['shoe_model'].queryset = ShoeModel.objects.filter(
            is_processed=True
        ).order_by('-created_at')


class SearchForm(forms.Form):
    """搜索表单"""
    
    search = forms.CharField(
        label="搜索",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '输入文件名搜索...'
        })
    )
    
    file_type = forms.ChoiceField(
        label="文件类型",
        choices=[
            ('all', '全部文件'),
            ('shoes', '鞋模文件'),
            ('blanks', '粗胚文件'),
        ],
        initial='all',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    processing_status = forms.ChoiceField(
        label="处理状态",
        choices=[
            ('', '全部状态'),
            ('pending', '待处理'),
            ('processing', '处理中'),
            ('completed', '已完成'),
            ('failed', '处理失败'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class MarginSettingsForm(forms.Form):
    """余量设置表单"""
    
    margin_distance = forms.DecimalField(
        label="余量距离 (mm)",
        min_value=0.5,
        max_value=10.0,
        decimal_places=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'step': '0.1'
        })
    )
    
    def clean_margin_distance(self):
        margin = self.cleaned_data['margin_distance']
        
        # 获取系统配置的范围限制
        min_margin = getattr(settings, 'GEOMETRY_ANALYSIS_SETTINGS', {}).get('MIN_MARGIN_DISTANCE', 0.5)
        max_margin = getattr(settings, 'GEOMETRY_ANALYSIS_SETTINGS', {}).get('MAX_MARGIN_DISTANCE', 10.0)
        
        if margin < min_margin or margin > max_margin:
            raise forms.ValidationError(
                f"余量距离必须在 {min_margin}mm 到 {max_margin}mm 之间"
            )
        
        return margin
