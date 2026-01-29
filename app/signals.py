from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Appointment, DailyAppointmentCreation

@receiver(post_save, sender=Appointment)
def record_daily_creation(sender, instance, created, **kwargs):
    """当预约创建时，记录到每日创建记录"""
    if created:  # 只有新创建的预约才记录
        from datetime import date
        from django.db import models
        
        # 获取今天的日期（使用服务器时区）
        today = timezone.now().date()
        
        # 尝试获取或创建今天的记录
        daily_record, created = DailyAppointmentCreation.objects.get_or_create(
            user=instance.guest,
            creation_date=today,
            defaults={'user': instance.guest, 'creation_date': today}
        )
        
        # 注意：这里我们不存储计数，而是通过查询DailyAppointmentCreation的数量来计算
        # 因为每次创建预约都会创建一条新的记录

from django.contrib.auth.signals import user_logged_in

@receiver(user_logged_in)
def handle_user_login(sender, request, user, **kwargs):
    """用户登录时清除待删除标记"""
    if hasattr(user, 'to_be_deleted') and user.to_be_deleted:
        user.to_be_deleted = False
        user.last_login_before_deletion = timezone.now()
        user.save(update_fields=['to_be_deleted', 'last_login_before_deletion'])

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Appointment
from .queue_manager import AppointmentQueueManager

# 定义影响队列的关键字段
QUEUE_RELATED_FIELDS = {
    'is_responded',
    'is_processed', 
    'is_deleted',
    'priority'
}

@receiver(post_save, sender=Appointment)
def handle_appointment_save(sender, instance, created, **kwargs):
    """
    预约保存时更新队列
    只在实际影响队列的字段发生变化时触发
    """
    # 如果是新创建的预约
    if created:
        # 不影响队列
        return
    
    # 如果不是新创建，检查是否有影响队列的字段被更新
    try:
        # 获取更新前的实例
        old_instance = Appointment.objects.get(pk=instance.pk)
        
        # 检查关键字段是否发生变化
        needs_refresh = False
        
        # 检查每个关键字段
        for field in QUEUE_RELATED_FIELDS:
            if getattr(old_instance, field) != getattr(instance, field):
                needs_refresh = True
                break
        
        # 如果关键字段发生变化，使队列失效
        if needs_refresh:
            AppointmentQueueManager.invalidate_queue()
            
    except Appointment.DoesNotExist:
        # 实例不存在，可能是并发操作，安全起见使队列失效
        AppointmentQueueManager.invalidate_queue()

@receiver(post_delete, sender=Appointment)
def handle_appointment_delete(sender, instance, **kwargs):
    """
    预约删除时更新队列
    只删除已回应未处理的预约才需要更新队列
    """
    # 检查被删除的预约是否在队列中
    if (instance.is_responded and 
        not instance.is_processed and 
        not instance.is_deleted):
        AppointmentQueueManager.invalidate_queue()