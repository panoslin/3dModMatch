"""
等待数据库启动的Django管理命令
"""

import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    """等待数据库可用"""
    
    help = '等待数据库启动'
    
    def handle(self, *args, **options):
        """等待数据库连接"""
        self.stdout.write('等待数据库启动...')
        db_conn = None
        while not db_conn:
            try:
                db_conn = connections['default']
                with db_conn.cursor() as cursor:
                    cursor.execute('SELECT 1')
                self.stdout.write(
                    self.style.SUCCESS('数据库连接成功!')
                )
            except OperationalError:
                self.stdout.write('数据库不可用，等待1秒后重试...')
                time.sleep(1)
