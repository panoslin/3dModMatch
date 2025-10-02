# Generated manually on 2025-10-03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0004_add_dual_heatmap_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='matchingtask',
            name='total_candidates',
            field=models.IntegerField(default=0, verbose_name='候选粗胚总数'),
        ),
    ]

