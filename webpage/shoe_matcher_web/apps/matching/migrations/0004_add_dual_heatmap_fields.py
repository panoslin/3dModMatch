# Generated manually for dual heatmap support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0003_add_dual_heatmap_support'),
    ]

    operations = [
        # 添加双模型热力图状态字段
        migrations.AddField(
            model_name='matchingtask',
            name='dual_heatmap_status',
            field=models.CharField(
                choices=[
                    ('not_started', '未开始'),
                    ('generating', '生成中'),
                    ('completed', '已完成'),
                    ('failed', '生成失败')
                ],
                default='not_started',
                max_length=20,
                verbose_name='双模型热力图状态'
            ),
        ),
        
        # 添加双模型热力图数据字段
        migrations.AddField(
            model_name='matchingtask',
            name='dual_heatmap_data',
            field=models.JSONField(
                default=dict,
                verbose_name='双模型热力图数据'
            ),
        ),
        
        # 添加对齐数据存储字段
        migrations.AddField(
            model_name='matchingtask',
            name='alignment_data',
            field=models.JSONField(
                default=dict,
                verbose_name='对齐数据'
            ),
        ),
        
        # 添加间隙计算缓存字段
        migrations.AddField(
            model_name='matchingtask',
            name='clearance_cache',
            field=models.JSONField(
                default=dict,
                verbose_name='间隙计算缓存'
            ),
        ),
    ]
