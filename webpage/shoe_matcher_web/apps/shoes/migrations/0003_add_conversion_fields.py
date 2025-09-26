# Generated manually for STL conversion support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shoes', '0002_add_lod_support'),
    ]

    operations = [
        migrations.AddField(
            model_name='shoemodel',
            name='original_format',
            field=models.CharField(
                default='3dm',
                help_text='上传时的原始文件格式，如 .stl, .3dm 等',
                max_length=10,
                verbose_name='原始文件格式'
            ),
        ),
        migrations.AddField(
            model_name='shoemodel',
            name='conversion_info',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='文件转换的详细信息，包括转换类型、统计数据等',
                verbose_name='转换信息'
            ),
        ),
        migrations.AddField(
            model_name='shoemodel',
            name='converted_at',
            field=models.DateTimeField(
                blank=True,
                help_text='文件转换完成的时间',
                null=True,
                verbose_name='转换时间'
            ),
        ),
    ]
