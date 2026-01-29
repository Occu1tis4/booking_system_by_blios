from .queue_manager import AppointmentQueueManager
from .models import Appointment
from django.db.models import Q
from django.utils import timezone

class DoctorQueueManager:
    """医师队列管理器（使用新的队列系统）"""

    @staticmethod
    def fresh(appointment):
        AppointmentQueueManager.handle_appointment_change(appointment)
        return appointment
    
    @staticmethod
    def get_urge_appointment():
        """处理催单：查找ID最小的标记为催单的预约"""
        return Appointment.objects.filter(
            is_urged=True,
            is_responded=True,
            is_processed=False,
            is_deleted=False
        ).order_by('id').first()
    
    @staticmethod
    def get_unresponded_appointment():
        """回应预约：查找ID最小且未回应的预约"""
        return Appointment.objects.filter(
            is_responded=False,
            is_processed=False,
            is_deleted=False
        ).order_by('id').first()
    
    @staticmethod
    def get_next_processing_appointment():
        """处理预约：从队列中获取下一个预约"""
        return AppointmentQueueManager.get_next_appointment()
    
    @staticmethod
    def get_queue_position(appointment):
        """计算预约在处理队列中的位置"""
        return AppointmentQueueManager.get_queue_position(appointment)
    
    @staticmethod
    def add_to_processing_pool(appointment):
        """将预约添加到处理池"""
        from .models import DoctorProcessingPool
        
        # 检查是否已在处理池中
        existing = DoctorProcessingPool.objects.filter(
            appointment=appointment,
            is_removed=False
        ).exists()
        
        if not existing:
            DoctorProcessingPool.objects.create(appointment=appointment)
    
    @staticmethod
    def remove_from_processing_pool(appointment_id):
        """从处理池中移除预约"""
        from .models import DoctorProcessingPool
        
        DoctorProcessingPool.objects.filter(
            appointment_id=appointment_id
        ).update(is_removed=True)
    
    @staticmethod
    def get_processing_pool():
        """获取处理池中的预约"""
        from .models import DoctorProcessingPool
        
        return DoctorProcessingPool.objects.filter(
            is_removed=False
        ).select_related('appointment').order_by('-added_at')
    
    @staticmethod
    def process_appointment(appointment, annotation='', note=''):
        """处理预约的通用方法"""
        if not appointment.is_responded:
            # 如果未回应，先标记为已回应
            appointment.is_responded = True
        
        # 更新批注和备注
        if annotation is not None:
            appointment.annotation = annotation
        if note is not None:
            appointment.note = note
        
        # 标记为已处理
        appointment.is_processed = True
        appointment.save()
        
        # 添加到处理池
        DoctorQueueManager.add_to_processing_pool(appointment)
        
        # 更新上次处理的优先级（如果优先级不是4）
        if appointment.priority != 4:
            AppointmentQueueManager.update_last_processed_priority(appointment.priority)
        
        AppointmentQueueManager.handle_appointment_change(appointment)
        
        return appointment
    
    @staticmethod
    def urge_appointment(appointment, annotation='', note='', priority=None):
        if priority is not None:
            appointment.priority = priority

        # 更新批注和备注
        if annotation is not None:
            appointment.annotation = annotation
        if note is not None:
            appointment.note = note
        
        # 标记为已回应
        appointment.is_urged = False
        appointment.save()

        AppointmentQueueManager.handle_appointment_change(appointment)
        
        return appointment
    
    @staticmethod
    def delete_appointment(appointment):
        # 软删除：标记为已删除，记录删除时间
        appointment.is_deleted = True
        appointment.deleted_at = timezone.now()
        appointment.save()
        AppointmentQueueManager.handle_appointment_change(appointment)
        return appointment

    
    @staticmethod
    def respond_appointment(appointment, annotation='', note='', priority=None):
        """回应预约的通用方法"""
        # 更新优先级（如果提供）
        if priority is not None:
            appointment.priority = priority
        
        # 更新批注和备注
        if annotation is not None:
            appointment.annotation = annotation
        if note is not None:
            appointment.note = note
        
        # 标记为已回应
        appointment.is_responded = True
        appointment.save()

        AppointmentQueueManager.handle_appointment_change(appointment)
        
        return appointment
    
    @staticmethod
    def get_queue_stats():
        """获取队列统计信息"""
        return AppointmentQueueManager.get_queue_stats()
    
    @staticmethod
    def refresh_queue():
        """手动刷新队列"""
        return AppointmentQueueManager.refresh_queue()
    
    @staticmethod
    def get_last_processed_priority():
        """获取上次处理的优先级"""
        return AppointmentQueueManager.get_last_processed_priority()