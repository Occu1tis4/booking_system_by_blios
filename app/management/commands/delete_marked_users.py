import os
import sys
import django
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from app.models import CustomUser
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '每月7日删除标记为待删除的账户'
    
    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # 检查是否是每月7日
        if today.day != 7:
            self.stdout.write(f"今天不是7号，跳过删除。今天是：{today}")
            return
        
        self.stdout.write(f"开始执行每月7日的账户删除...")
        
        # 获取所有标记为待删除的账户
        users_to_delete = CustomUser.objects.filter(
            to_be_deleted=True,
            is_superuser=False,
            is_staff=False
        )
        
        deleted_count = 0
        
        for user in users_to_delete:
            try:
                # 记录用户信息（可选，用于审计）
                user_email = user.email
                user_date_joined = user.date_joined
                
                # 删除用户
                user.delete()
                deleted_count += 1
                
                self.stdout.write(f"已删除用户: {user_email} (注册时间: {user_date_joined})")
                
            except Exception as e:
                logger.error(f"删除用户 {user.email} 时出错: {e}")
                self.stdout.write(f"删除用户 {user.email} 时出错: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(f"删除完成！共删除了 {deleted_count} 个账户")
        )