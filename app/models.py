from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime
import pytz

class CustomUserManager(BaseUserManager):
    """自定义用户管理器，适配无username的CustomUser模型"""
    
    def create_user(self, email, password=None, **extra_fields):
        """创建普通用户"""
        if not email:
            raise ValueError('用户必须提供邮箱地址')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """创建超级用户（医师账号）"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('超级用户必须设置 is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('超级用户必须设置 is_superuser=True')
        
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    """自定义用户模型，使用邮箱作为唯一标识"""
    username = None  # 移除默认的用户名字段
    email = models.EmailField(_('邮箱地址'), unique=True)

    # 添加账户状态字段
    to_be_deleted = models.BooleanField(default=False, verbose_name="标记为待删除")
    to_be_deleted_notified_at = models.DateTimeField(null=True, blank=True, verbose_name="待删除通知时间")
    last_login_before_deletion = models.DateTimeField(null=True, blank=True, verbose_name="删除前最后登录时间")

    last_announcement_view_time = models.DateTimeField(
        default=timezone.make_aware(datetime(1970, 1, 1), pytz.UTC),
        verbose_name="上次查看公告时间",
    )

    PRIORITY_CHOICES = [
        (1, '低'),
        (2, '中'),
        (3, '高'),
        (4, '危'),
    ]

    last_processed_priority = models.IntegerField(
        default=1,
        choices=PRIORITY_CHOICES,
        verbose_name="上次处理的优先级",
        help_text="记录医师上次处理的1-3级预约的优先级，用于轮询算法"
    )
    
    # 使用自定义的管理器
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'  # 使用email作为登录字段
    REQUIRED_FIELDS = []  # 创建超级用户时不需要额外字段
    
    def __str__(self):
        return self.email

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

class Appointment(models.Model):
    """预约表"""
    PRIORITY_CHOICES = [
        (1, '低'),
        (2, '中'),
        (3, '高'),
        (4, '危'),
    ]

    patient_name = models.CharField(max_length=100, verbose_name="预约人")
    demand = models.TextField(verbose_name="需求描述")
    wechat_id = models.CharField(max_length=100, verbose_name="微信号")
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=1, verbose_name="优先级")
    
    is_responded = models.BooleanField(default=False, verbose_name="已回应")
    is_processed = models.BooleanField(default=False, verbose_name="已处理")
    is_urged = models.BooleanField(default=False, verbose_name="已催单")
    urged_at = models.DateTimeField(null=True, blank=True, verbose_name="催单时间")

    last_modified_at = models.DateTimeField(null=True, blank=True, verbose_name="最后修改时间")
    today_modified_count = models.IntegerField(default=0, verbose_name="今日修改次数")
    
    annotation = models.TextField(blank=True, verbose_name="批注（医师填写，访客可见）")
    note = models.TextField(blank=True, verbose_name="备注（仅医师可见）")
    
    # 使用settings.AUTH_USER_MODEL
    guest = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="归属账号")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    is_deleted = models.BooleanField(default=False, verbose_name="是否已删除")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="删除时间")

    def __str__(self):
        return f"{self.patient_name} - {self.get_priority_display()}"
    
    def can_modify_today_simple(self):
        """简化的检查方法"""
        import datetime
        from django.utils import timezone
    
        # 已处理的不可以修改
        if self.is_processed:
            return False
    
        # 没有修改记录可以修改
        if not self.last_modified_at:
            return True
    
        # 获取本地时间的日期部分
        now_local = timezone.localtime(timezone.now())
        last_modified_local = timezone.localtime(self.last_modified_at)
    
        # 比较日期
        if now_local.date() != last_modified_local.date():
            return True
    
        # 同一天，检查次数
        return self.today_modified_count < 1
    
    def can_modify_today(self):
        """检查今天是否还可以修改"""
        from django.utils import timezone
        from datetime import datetime
    
        # 检查1：已处理的预约不能修改
        if self.is_processed:
            return False, "已处理的预约不能修改"
    
        # 检查2：如果今天没有修改过
        if not self.last_modified_at:
            return True, "可以修改"
    
        # 使用Django的时区工具
        now = timezone.now()
        today = now.date()
    
        # 将 last_modified_at 转换为本地日期
        last_modified_date = self.last_modified_at.astimezone(timezone.get_current_timezone()).date()
    
        # 检查3：如果今天没有修改过
        if last_modified_date != today:
            return True, "可以修改"
    
        # 检查4：如果今天修改过，但次数小于1
        if self.today_modified_count < 1:
            return True, "可以修改"
    
        return False, "该预约今天已经修改过，请明天再试"

    # 添加这两个属性方法，方便在模板中调用
    def can_modify_today_bool(self):
        """返回是否可以修改的布尔值"""
        can_modify, _ = self.can_modify_today()
        return can_modify

    def can_modify_today_reason(self):
        """返回不能修改的原因"""
        _, reason = self.can_modify_today()
        return reason

    class Meta:
        verbose_name = "预约"
        verbose_name_plural = "预约列表"
    
    @classmethod
    def reset_daily_modification_counts(cls):
        """重置所有预约的每日修改次数（可以在每日任务中调用）"""
        # 找到今天修改过的预约，重置计数
        from datetime import datetime
        from django.utils import timezone
        today = timezone.now().date()
        
        # 找到最后修改日期不是今天的预约，重置计数
        appointments_to_reset = cls.objects.exclude(
            last_modified_at__date=today
        ).filter(today_modified_count__gt=0)
        
        count = appointments_to_reset.count()
        appointments_to_reset.update(today_modified_count=0)
        
        return count

# 在 Appointment 模型后面添加处理池模型
class DoctorProcessingPool(models.Model):
    """医师处理池，存放已处理的预约ID"""
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, verbose_name="预约")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="添加时间")
    is_removed = models.BooleanField(default=False, verbose_name="已移除")
    
    class Meta:
        verbose_name = "处理池记录"
        verbose_name_plural = "处理池记录"
    
    def __str__(self):
        return f"{self.appointment.patient_name} - {self.added_at}"
    
class DailyAppointmentCreation(models.Model):
    """记录用户每日预约创建次数，即使预约删除也保留记录"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    creation_date = models.DateField(verbose_name="创建日期")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="记录时间")
    
    class Meta:
        verbose_name = "每日创建记录"
        verbose_name_plural = "每日创建记录"
        # 确保每个用户每天只有一条记录（配合信号使用）
        unique_together = ['user', 'creation_date']
    
    def __str__(self):
        return f"{self.user.email} - {self.creation_date}"

# 在 models.py 的 Appointment 模型后面添加

class Profile(models.Model):
    """用户档案"""
    
    name = models.CharField(max_length=20, verbose_name="姓名")
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="归属账号",
        related_name='profiles'
    )
    wechat_id = models.CharField(max_length=30, verbose_name="微信号")
    notes = models.TextField(verbose_name="备注", blank=True)
    overview = models.TextField(verbose_name="概述（仅医师可见）", blank=True)
    is_urged = models.BooleanField(default=False, verbose_name="是否催促")
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_profiles',
        verbose_name="创建者"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        verbose_name = "用户档案"
        verbose_name_plural = "用户档案"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name} - {self.wechat_id}"


class ProfileRecord(models.Model):
    """档案记录"""
    RECORD_TYPE_CHOICES = [
        ('user', '访客'),
        ('doctor_public', '医师（公开）'),
        ('doctor_private', '医师（仅医师）'),
    ]
    
    profile = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='records',
        verbose_name="档案"
    )
    content = models.TextField(verbose_name="记录内容")
    record_type = models.CharField(
        max_length=20, 
        choices=RECORD_TYPE_CHOICES, 
        verbose_name="记录类型"
    )
    
    # 创建者（医师填写时为医师，用户填写时为档案所属用户）
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="创建者"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "档案记录"
        verbose_name_plural = "档案记录"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.profile.name} - {self.get_record_type_display()} - {self.created_at}"
    
    def is_visible_to_patient(self):
        """检查记录是否对访客可见"""
        return self.record_type in ['user', 'doctor_public']

# 在 models.py 中添加 Announcement 模型
class Announcement(models.Model):
    title = models.CharField(max_length=200, verbose_name="标题")
    content = models.TextField(verbose_name="内容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="发布者"
    )
    
    class Meta:
        verbose_name = "公告"
        verbose_name_plural = "公告"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title