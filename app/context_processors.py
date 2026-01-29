from .models import Appointment

def doctor_stats(request):
    """为所有医师模板提供统计数据"""
    if request.user.is_authenticated and request.user.is_superuser:
        # 计算统计数据
        urge_count = Appointment.objects.filter(
            is_urged=True,
            is_processed=False,
            is_deleted=False
        ).count()
        
        unresponded_count = Appointment.objects.filter(
            is_responded=False,
            is_processed=False,
            is_deleted=False
        ).exclude(is_urged=True).count()
        
        unprocessed_count = Appointment.objects.filter(
            is_urged=False,
            is_responded=True,
            is_processed=False,
            is_deleted=False
        ).count()
        
        processed_count = Appointment.objects.filter(
            is_processed=True,
            is_deleted=False
        ).count()
        
        all_count = Appointment.objects.filter(is_deleted=False).count()
        
        return {
            'urge_count': urge_count,
            'unresponded_count': unresponded_count,
            'unprocessed_count': unprocessed_count,
            'processed_count': processed_count,
            'all_count': all_count,
        }
    
    # 如果不是医师，返回空字典
    return {}