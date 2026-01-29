# 使用Alpine基础镜像（Python 3.14可能还不存在，建议使用3.11-3.13）
FROM python:3.14-alpine

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=booking_system.settings

# 安装系统依赖（Alpine使用apk）
RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    postgresql-dev \
    jpeg-dev \
    zlib-dev

# 创建非root用户（Alpine使用adduser）
RUN adduser -D -u 1000 appuser

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制
COPY . .

# 复制启动脚本
COPY start.sh /start.sh
RUN chmod +x /start.sh

# 修改文件权限（使用chown在Alpine中）
RUN chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 8000

CMD ["/start.sh"]