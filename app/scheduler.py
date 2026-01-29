import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django.utils import timezone
from django.conf import settings
import sys

logger = logging.getLogger(__name__)

def start():
    """启动调度器"""
    if settings.DEBUG:
        # 开发环境下，你可以选择不在启动时运行
        return
    
    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(DjangoJobStore(), "default")
    
    # 添加你的两个任务
    from app.management.commands import check_users_for_deletion, delete_marked_users
    from django.core.management import call_command
    
    @scheduler.scheduled_job('cron', day='1', hour='0', minute='0', id='check_users')
    def check_users_job():
        """每月1日检查用户"""
        logger.info("开始执行每月1日的账户检查...")
        try:
            call_command('check_users_for_deletion')
        except Exception as e:
            logger.error(f"检查用户任务失败: {e}")
    
    @scheduler.scheduledscheduled_job('cron', day='7', hour='0', minute='0', id='delete_users')
    def delete_users_job():
        """每月7日删除用户"""
        logger.info("开始执行每月7日的账户删除...")
        try:
            call_command('delete_marked_users')
        except Exception as e:
            logger.error(f"删除用户任务失败: {e}")
    
    # 清理旧的任务执行记录（可选）
    @scheduler.scheduled_job('interval', hours=24, id='cleanup_jobs')
    def cleanup():
        DjangoJobExecution.objects.delete_old_job_executions(604800)  # 删除7天前的记录
    
    try:
        scheduler.start()
        logger.info("调度器已启动")
    except Exception as e:
        logger.error(f"调度器启动失败: {e}")
        scheduler.shutdown()