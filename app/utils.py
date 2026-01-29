import random
import string
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone

def generate_verification_code(length=6):
    """生成随机验证码"""
    # 使用数字和大写字母
    characters = string.digits + string.ascii_uppercase
    return ''.join(random.choice(characters) for _ in range(length))

def send_verification_code(email):
    """发送验证码到指定邮箱"""
    # 生成验证码
    code = generate_verification_code()
    
    # 设置验证码有效时间（10分钟）
    cache_key = f'verification_code_{email}'
    cache.set(cache_key, code, timeout=300)  # 10分钟 = 600秒
    
    # 设置发送频率限制（60秒内只能发送一次）
    rate_limit_key = f'email_rate_limit_{email}'
    if cache.get(rate_limit_key):
        return False, "验证码发送过于频繁，请稍后再试"
    
    cache.set(rate_limit_key, True, timeout=60)  # 60秒内不能重复发送
    
    # 发送邮件
    subject = '【缥缈旅】邮箱验证码'
    message = f'''
    感谢您注册缥缈旅！
    
    您的验证码是：{code}
    
    验证码有效期为5分钟，请尽快完成注册。
    
    如果您没有进行此操作，请忽略此邮件。
    
    伯里欧斯的小助理
    '''
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return True, "验证码已发送到您的邮箱"
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False, "验证码发送失败，请检查邮箱地址"

def verify_code(email, code):
    """验证邮箱和验证码"""
    cache_key = f'verification_code_{email}'
    stored_code = cache.get(cache_key)
    
    if not stored_code:
        return False, "验证码已过期或不存在"
    
    if stored_code != code.upper():  # 转为大写比较
        return False, "验证码不正确"
    
    # 验证成功后删除验证码
    cache.delete(cache_key)
    return True, "验证成功"

def check_email_rate_limit(email):
    """检查邮箱发送频率限制"""
    rate_limit_key = f'email_rate_limit_{email}'
    return cache.get(rate_limit_key) is not None