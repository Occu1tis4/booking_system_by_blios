import os
import sys
import django
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail
from app.models import CustomUser, Appointment
from django.db.models import Q
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '每月1日检查用户账户，标记无未处理预约的账户为待删除并发送通知邮件'
    
    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # 检查是否是每月1日
        if today.day != 1:
            self.stdout.write(f"今天不是1号，跳过检查。今天是：{today}")
            return
        
        self.stdout.write(f"开始执行每月1日的账户检查...")
        
        # 获取所有普通用户（非超级用户/医师）
        users = CustomUser.objects.filter(is_superuser=False, is_staff=False)
        
        marked_count = 0
        notified_count = 0
        
        for user in users:
            try:
                # 检查用户是否有未处理的预约（不包括已删除的）
                has_unprocessed_appointments = Appointment.objects.filter(
                    guest=user,
                    is_processed=False,
                    is_deleted=False
                ).exists()
                
                if not has_unprocessed_appointments:
                    # 标记为待删除
                    if not user.to_be_deleted:
                        user.to_be_deleted = True
                        user.to_be_deleted_notified_at = timezone.now()
                        user.save()
                        marked_count += 1
                    
                    # 发送通知邮件（如果本月还没发送过）
                    # 检查本月是否已发送过通知
                    if (not user.to_be_deleted_notified_at or 
                        user.to_be_deleted_notified_at.month != today.month or
                        user.to_be_deleted_notified_at.year != today.year):
                        
                        self.send_deletion_notification_email(user)
                        user.to_be_deleted_notified_at = timezone.now()
                        user.save()
                        notified_count += 1
                        
                        self.stdout.write(f"已通知用户 {user.email} 账户将被删除")
                    else:
                        self.stdout.write(f"用户 {user.email} 本月已收到通知，跳过重复通知")
                        
            except Exception as e:
                logger.error(f"处理用户 {user.email} 时出错: {e}")
                self.stdout.write(f"处理用户 {user.email} 时出错: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"检查完成！标记了 {marked_count} 个待删除账户，发送了 {notified_count} 封通知邮件"
            )
        )
    
    def send_deletion_notification_email(self, user):
        """发送账户即将被删除的通知邮件"""
        subject = '【缥缈旅】您的账户即将被删除'
        
        message = f'''
亲爱的用户 {user.email}：

伯里欧斯的小助手检查发现，您的账户目前没有未处理的预约。

根据系统规则，我将在本月7日删除您的账户。

如果您希望保留账户，请在本月7日之前登录系统。登录后，您的账户将不会被删除。

如果您的账户被删除，您将需要重新注册才能使用预约服务。

感谢您使用缥缈旅！

伯里欧斯的小助理
        '''
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"发送删除通知邮件失败: {e}")
            return False