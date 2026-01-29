from django.core.cache import cache
from django.db.models import Q
from .models import Appointment, CustomUser
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class AppointmentQueueManager:
    """预约队列管理器"""
    
    CACHE_KEY_QUEUE = 'appointment_processing_queue'
    CACHE_TIMEOUT = 300  # 5分钟
    
    @classmethod
    def get_doctor_user(cls):
        """获取医师用户（通常是第一个超级用户）"""
        try:
            # 获取第一个超级用户作为医师账号
            return CustomUser.objects.filter(is_superuser=True).first()
        except Exception as e:
            logger.error(f"获取医师用户失败: {e}")
            return None
    
    @classmethod
    def get_last_processed_priority(cls):
        """获取上次处理的优先级（从医师账号字段）"""
        doctor_user = cls.get_doctor_user()
        if doctor_user and hasattr(doctor_user, 'last_processed_priority'):
            return doctor_user.last_processed_priority
        return 3  # 默认值
    
    @classmethod
    def update_last_processed_priority(cls, priority):
        """更新上次处理的优先级（保存到医师账号字段）"""
        if priority != 4:  # 优先级4不影响轮询
            doctor_user = cls.get_doctor_user()
            if doctor_user and hasattr(doctor_user, 'last_processed_priority'):
                doctor_user.last_processed_priority = priority
                doctor_user.save(update_fields=['last_processed_priority'])
                logger.info(f"医师上次处理的优先级已更新为: {priority}")
    
    @classmethod
    def get_queue(cls, force_refresh=False):
        """获取或生成处理队列"""
        # 如果强制刷新或缓存不存在，重新生成队列
        if force_refresh or cache.get(cls.CACHE_KEY_QUEUE) is None:
            return cls._generate_queue()
        
        # 从缓存获取队列
        queue_data = cache.get(cls.CACHE_KEY_QUEUE)
        
        # 检查队列是否过期（超过5分钟）
        if queue_data and 'generated_at' in queue_data:
            generated_time = datetime.fromisoformat(queue_data['generated_at'])
            if datetime.now() - generated_time > timedelta(seconds=cls.CACHE_TIMEOUT):
                return cls._generate_queue()
        
        return queue_data.get('queue', []) if queue_data else []
    
    @classmethod
    def _generate_queue(cls):
        """生成处理队列（按照优先级算法排序）"""
        # 获取所有已回应、未处理、未删除的预约
        appointments = Appointment.objects.filter(
            is_responded=True,
            is_processed=False,
            is_deleted=False
        ).order_by('id')
        
        if not appointments.exists():
            # 空队列
            queue_data = {
                'queue': [],
                'generated_at': datetime.now().isoformat()
            }
            cache.set(cls.CACHE_KEY_QUEUE, queue_data, cls.CACHE_TIMEOUT)
            return []
        
        # 按照算法排序
        sorted_appointments = cls._sort_appointments(appointments)
        
        # 提取ID列表
        queue_ids = [app.id for app in sorted_appointments]
        
        # 缓存队列
        queue_data = {
            'queue': queue_ids,
            'generated_at': datetime.now().isoformat(),
            'appointment_count': len(queue_ids)
        }
        cache.set(cls.CACHE_KEY_QUEUE, queue_data, cls.CACHE_TIMEOUT)
        
        logger.info(f"队列已重新生成，包含 {len(queue_ids)} 个预约")
        return queue_ids
    
    @classmethod
    def _sort_appointments(cls, appointments):
        """按照优先级算法排序预约"""
        # 分离优先级4的预约
        priority4_appointments = [app for app in appointments if app.priority == 4]
        
        # 非优先级4的预约
        other_appointments = [app for app in appointments if app.priority != 4]
        
        # 获取上次处理的优先级（从数据库字段）
        last_priority = cls.get_last_processed_priority()
        
        # 按照优先级分组（3, 2, 1）
        priority_groups = {3: [], 2: [], 1: []}
        for app in other_appointments:
            if app.priority in priority_groups:
                priority_groups[app.priority].append(app)
        
        # 对每组按ID排序
        for priority in priority_groups:
            priority_groups[priority].sort(key=lambda x: x.id)
        
        # 计算起始索引
        priorities = [3, 2, 1]
        try:
            start_index = priorities.index((4-last_priority)%3)
        except ValueError:
            start_index = 0
        
        # 生成轮询顺序
        sorted_appointments = []
        
        # 首先添加所有优先级4的预约（按ID排序）
        priority4_appointments.sort(key=lambda x: x.id)
        sorted_appointments.extend(priority4_appointments)
        
        # 轮询非4级预约
        round_index = start_index
        while any(priority_groups.values()):
            current_priority = priorities[round_index % len(priorities)]
            
            if priority_groups[current_priority]:
                # 取出当前优先级最早的预约
                sorted_appointments.append(priority_groups[current_priority].pop(0))
            
            round_index += 1
        
        return sorted_appointments
    
    @classmethod
    def get_next_appointment(cls):
        """获取队列中的下一个预约（第一个）"""
        queue = cls.get_queue()
        
        if not queue:
            return None
        
        try:
            appointment_id = queue[0]
            return Appointment.objects.get(id=appointment_id)
        except Appointment.DoesNotExist:
            # 预约不存在，可能是被删除了，重新生成队列
            cls.invalidate_queue()
            return cls.get_next_appointment()
    
    @classmethod
    def get_queue_position(cls, appointment):
        """获取预约在队列中的位置"""
        if not appointment or appointment.is_processed or appointment.is_deleted:
            return None
        
        queue = cls.get_queue()
        
        try:
            # 位置从1开始
            return queue.index(appointment.id) + 1
        except ValueError:
            # 预约不在队列中，可能是未回应
            if not appointment.is_responded:
                return None
            
            # 重新生成队列并再次尝试
            cls.invalidate_queue()
            queue = cls.get_queue()
            
            try:
                return queue.index(appointment.id) + 1
            except ValueError:
                return None
    
    @classmethod
    def invalidate_queue(cls):
        """使队列缓存失效"""
        cache.delete(cls.CACHE_KEY_QUEUE)
        logger.info("队列缓存已失效")
    
    @classmethod
    def handle_appointment_change(cls, appointment):
        """处理预约变化（创建、更新、删除、回应、处理）"""
        # 检查预约状态是否影响队列
        needs_refresh = False
        
        if appointment.is_processed or appointment.is_deleted:
            # 已处理或已删除，需要从队列中移除
            needs_refresh = True
        elif appointment.is_responded and not appointment.is_processed and not appointment.is_deleted:
            # 已回应未处理，可能影响队列
            needs_refresh = True
        
        if needs_refresh:
            cls.invalidate_queue()
    
    @classmethod
    def get_queue_stats(cls):
        """获取队列统计信息"""
        queue = cls.get_queue()
        
        if not queue:
            return {
                'total': 0,
                'priority_counts': {1: 0, 2: 0, 3: 0, 4: 0},
            }
        
        # 获取所有预约信息
        appointments = Appointment.objects.filter(id__in=queue)
        
        # 统计各优先级数量
        priority_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for app in appointments:
            if app.priority in priority_counts:
                priority_counts[app.priority] += 1
        
        return {
            'total': len(queue),
            'priority_counts': priority_counts,
        }
    
    @classmethod
    def refresh_queue(cls):
        """手动刷新队列"""
        return cls._generate_queue()