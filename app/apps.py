from django.apps import AppConfig
from django.conf import settings


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        # 确保只在主进程中运行一次
        import os
        if os.environ.get('RUN_MAIN') or not settings.DEBUG:
            from .scheduler import start
            start()