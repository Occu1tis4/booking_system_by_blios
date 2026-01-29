from django.core.management.base import BaseCommand
from app.queue_manager import AppointmentQueueManager

class Command(BaseCommand):
    help = '手动刷新预约处理队列'
    
    def handle(self, *args, **options):
        self.stdout.write("开始刷新预约处理队列...")
        
        queue = AppointmentQueueManager.refresh_queue()
        
        stats = AppointmentQueueManager.get_queue_stats()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"队列刷新完成！\n"
                f"队列长度: {stats['total']}\n"
                f"优先级统计: 4级={stats['priority_counts'][4]}, "
                f"3级={stats['priority_counts'][3]}, "
                f"2级={stats['priority_counts'][2]}, "
                f"1级={stats['priority_counts'][1]}\n"
                f"预估等待时间: {stats['estimated_wait_time']}分钟"
            )
        )