#!/bin/sh

# 应用数据库迁移
echo "正在应用数据库迁移..."
python manage.py migrate

# 创建超级用户（如果不存在）
echo "检查并创建超级用户..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='admin@example.com').exists():
    User.objects.create_superuser(email='admin@example.com', password='admin123')
    print('✓ 超级用户创建成功！')
else:
    print('✓ 超级用户已存在，跳过创建。')
EOF

# 启动Django开发服务器
echo "启动Django开发服务器..."
exec python manage.py runserver 0.0.0.0:8000