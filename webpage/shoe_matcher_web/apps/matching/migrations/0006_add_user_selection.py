# Generated manually on 2025-10-03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0005_add_total_candidates'),
    ]

    operations = [
        migrations.AddField(
            model_name='matchingtask',
            name='user_selected_blank',
            field=models.CharField(blank=True, help_text='用户最终选择的粗胚文件名', max_length=500, verbose_name='用户选择的粗胚'),
        ),
        migrations.AddField(
            model_name='matchingtask',
            name='user_selected_index',
            field=models.IntegerField(blank=True, help_text='用户选择的结果在results数组中的索引', null=True, verbose_name='用户选择的索引'),
        ),
        migrations.AddField(
            model_name='matchingtask',
            name='user_selected_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='用户选择时间'),
        ),
        migrations.AddField(
            model_name='matchingtask',
            name='user_selection_note',
            field=models.TextField(blank=True, help_text='用户选择此粗胚的原因或备注', verbose_name='选择备注'),
        ),
    ]

