from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, get_user_model
from django.contrib import messages
from .models import Appointment, CustomUser, ProfileRecord
from .forms import AppointmentForm, CustomUserCreationForm
from datetime import datetime as dt, timedelta  # 使用别名避免冲突
import pytz
from .forms import AppointmentForm, CustomUserCreationForm, AppointmentUpdateForm, EmailVerificationForm
from .models import Appointment, CustomUser, DailyAppointmentCreation
from django.utils import timezone
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from .doctor_utils import DoctorQueueManager

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

User = get_user_model()

from django.contrib.auth import login

def send_appointment_notification(appointment, action_type, annotation='', note=''):
    """
    发送预约通知邮件给访客
    
    Args:
        appointment: 预约对象
        action_type: 操作类型 ('responded', 'processed', 'urge_processed')
        annotation: 批注内容
        note: 备注内容（可选）
    """
    try:
        # 邮件主题
        if action_type == 'responded':
            subject = f'【缥缈旅】您的预约已得到回应'
        elif action_type == 'processed':
            subject = f'【缥缈旅】您的预约即将处理'
        elif action_type == 'urge_processed':
            subject = f'【缥缈旅】您的催单已处理'
        else:
            subject = f'【缥缈旅】您的预约状态已更新'
        
        # 构建邮件内容
        context = {
            'appointment': appointment,
            'action_type': action_type,
            'annotation': annotation,
            'note': note,
            'site_name': '伯里欧斯的小助手',
        }
        
        # 渲染HTML邮件模板
        html_message = render_to_string('emails/appointment_notification.html', context)
        plain_message = strip_tags(html_message)
        
        # 发送邮件
        recipient_list = [appointment.guest.email]
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=True,  # 邮件发送失败不影响主要功能
        )
        
        print(f"邮件已发送至 {appointment.guest.email}，预约ID: {appointment.id}，操作: {action_type}")
        
    except Exception as e:
        print(f"邮件发送失败: {str(e)}")
        # 记录日志但不中断流程
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"发送预约通知邮件失败: {str(e)}")


def send_profile_record_notification(profile, record, action_type):
    """
    发送档案记录通知邮件给档案关联账号的用户
    
    Args:
        profile: 档案对象
        record: 记录对象
        action_type: 操作类型 ('record_added')
    """
    try:
        # 检查是否有关联账号且用户有邮箱
        if not profile.account or not profile.account.email:
            print(f"档案 {profile.name} 无关联账号或邮箱，跳过邮件发送")
            return
        
        # 邮件主题
        subject = f'【缥缈旅】您的档案 {profile.name} 有更新'
        
        # 构建邮件内容
        context = {
            'profile': profile,
            'record': record,
            'action_type': action_type,
            'site_name': '伯里欧斯的小助手',
            'record_type_display': record.get_record_type_display(),
        }
        
        # 渲染HTML邮件模板
        html_message = render_to_string('emails/profile_record_notification.html', context)
        plain_message = strip_tags(html_message)
        
        # 发送邮件
        recipient_list = [profile.account.email]
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=True,  # 邮件发送失败不影响主要功能
        )
        
        print(f"档案记录邮件已发送至 {profile.account.email}，档案: {profile.name}，记录ID: {record.id}")
        
    except Exception as e:
        print(f"档案记录邮件发送失败: {str(e)}")
        # 记录日志但不中断流程
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"发送档案记录通知邮件失败: {str(e)}")

def login_redirect(request):
    """登录后重定向 - 根据用户类型跳转到不同页面"""
    # 确保用户已经登录
    if not request.user.is_authenticated:
        return redirect('login')
    
    # 添加延迟，确保会话状态已同步
    import time
    time.sleep(0.1)  # 100ms延迟，确保会话状态同步
    
    # 重新从数据库获取用户，确保获得最新状态
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        # 重新从数据库获取用户对象
        current_user = User.objects.get(id=request.user.id)
        
        print(f"DEBUG - 用户重定向检查:")
        print(f"  邮箱: {current_user.email}")
        print(f"  is_superuser: {current_user.is_superuser}")
        print(f"  is_staff: {current_user.is_staff}")
        print(f"  is_active: {current_user.is_active}")
        
        # 检查是否是医师（超级用户且是职员）
        if current_user.is_superuser and current_user.is_staff:
            print("DEBUG - 重定向到医师界面")
            return redirect('doctor_index')
        else:
            print("DEBUG - 重定向到访客首页")
            return redirect('index')
            
    except User.DoesNotExist:
        print("DEBUG - 用户不存在")
        return redirect('login')

def clear_deletion_mark_on_login(request, user):
    """用户登录时清除待删除标记"""
    if user.to_be_deleted:
        user.to_be_deleted = False
        user.last_login_before_deletion = timezone.now()
        user.save()
        
        # 可选：发送确认邮件
        try:
            subject = '账户保留确认'
            message = f'''
亲爱的用户 {user.email}：

您已成功登录缥缈旅，您的账户已从待删除列表中移除。

感谢您继续使用我们的服务！

伯里欧斯的小助理
            '''
            
            from django.core.mail import send_mail
            from django.conf import settings
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            # 邮件发送失败不影响主要功能
            pass

def cleanup_expired_deleted_appointments():
    """清理昨天及更早删除的预约（处理时区）"""
    from django.utils import timezone
    from datetime import datetime, timedelta, date
    
    # 获取当前时区的今天日期
    now = timezone.now()
    today = now.date()
    
    # 获取昨天的日期
    yesterday = today - timedelta(days=1)
    
    # 创建昨天的开始和结束时间（用于调试）
    yesterday_start = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
    yesterday_end = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    
    print(f"清理条件：删除日期 <= {yesterday}")
    print(f"时间范围：{yesterday_start} 到 {yesterday_end}")
    
    # 查找所有在昨天或之前被删除的预约
    expired_appointments = Appointment.objects.filter(
        is_deleted=True,
        deleted_at__date__lte=yesterday  # 删除日期小于等于昨天
    )
    
    expired_count = expired_appointments.count()
    
    if expired_count > 0:
        # 显示将要删除的预约信息（用于调试）
        for app in expired_appointments[:5]:  # 只显示前5个
            print(f"  将要删除：ID={app.id}, 删除时间={app.deleted_at}")
        
        # 真正删除这些预约
        deleted_count, _ = expired_appointments.delete()
        print(f"已自动清理 {deleted_count} 个昨天及更早删除的预约")
        return deleted_count
    
    print("没有需要清理的过期预约")
    return 0

# 用户注册视图
from .utils import send_verification_code, verify_code

def register(request):
    """两步注册流程"""
    # 第一步：输入邮箱并发送验证码
    if request.method == 'GET':
        email_form = EmailVerificationForm()
        return render(request, 'app/register_step1.html', {'form': email_form})
    
    # 处理POST请求
    if 'send_code' in request.POST:
        # 发送验证码请求
        email_form = EmailVerificationForm(request.POST)
        if email_form.is_valid():
            email = email_form.cleaned_data['email']
            
            # 检查每日注册限制
            from datetime import date
            from django.utils import timezone
            today = timezone.now().date()

            today_registrations = CustomUser.objects.filter(date_joined__date=today)
            if today_registrations.count() >= 10:
                messages.error(request, '今日注册名额已满，请明天再试。')
                return render(request, 'app/register_step1.html', {'form': email_form})
            
            # 发送验证码
            success, message = send_verification_code(email)
            if success:
                # 保存邮箱到session，进入第二步
                request.session['register_email'] = email
                request.session['register_step'] = 2
                
                # 创建第二步的表单
                register_form = CustomUserCreationForm(email=email)
                return render(request, 'app/register_step2.html', {
                    'form': register_form,
                    'email': email,
                    'success_message': message
                })
            else:
                messages.error(request, message)
                return render(request, 'app/register_step1.html', {'form': email_form})
        else:
            return render(request, 'app/register_step1.html', {'form': email_form})
    
    elif 'register' in request.POST:
        # 第二步：完成注册
        email = request.session.get('register_email')
        if not email:
            messages.error(request, '注册会话已过期，请重新开始。')
            return redirect('register')
        
        register_form = CustomUserCreationForm(request.POST, email=email)
        if register_form.is_valid():
            # 再次检查每日注册限制
            from datetime import date
            from django.utils import timezone
            today = timezone.now().date()
            today_registrations = CustomUser.objects.filter(date_joined__date=today)
            if today_registrations.count() >= 10:
                messages.error(request, '今日注册名额已满，请明天再试。')
                return redirect('register')
            
            # 保存用户
            user = register_form.save(commit=False)
            user.email = email
            user.username = email  # 确保username字段有值
            user.save()
            
            # 清除session
            request.session.pop('register_email', None)
            request.session.pop('register_step', None)
            
            # 自动登录
            login(request, user)
            messages.success(request, '注册成功！欢迎使用预约系统。')
            return redirect('index')
        else:
            return render(request, 'app/register_step2.html', {
                'form': register_form,
                'email': email
            })
    
    # 默认返回第一步
    return redirect('register')


@login_required
def user_index(request):
    """用户首页 - 导航页"""
    # 计算统计数据
    unfinished_count = Appointment.objects.filter(
        guest=request.user,
        is_processed=False,
    ).count()
    
    # 计算今日创建次数
    from django.utils import timezone
    today = timezone.now().date()
    daily_creations = DailyAppointmentCreation.objects.filter(
        user=request.user,
        creation_date=today
    ).count()
    
    # 计算本周催单次数
    from datetime import timedelta
    start_of_week = today - timedelta(days=today.weekday())
    weekly_urges = Appointment.objects.filter(
        guest=request.user,
        is_urged=True,
        is_deleted=False,
        urged_at__gte=start_of_week
    ).count()
    
    context = {
        'unfinished_count': unfinished_count,
        'daily_creation_count': daily_creations,
        'daily_creation_left': max(0, 3 - daily_creations),
        'weekly_urges': weekly_urges,
        'urges_left': max(0, 1 - weekly_urges),
    }
    return render(request, 'app/index.html', context)

@login_required
def patient_profile_detail(request, profile_id):
    """访客查看档案详情"""
    # 确保当前用户是档案的拥有者
    profile = get_object_or_404(Profile, id=profile_id, account=request.user)
    
    # 获取时间筛选参数
    month_filter = request.GET.get('month', '')
    
    # 获取记录（访客只能看到访客记录和医师公开记录）
    records = profile.records.filter(
        record_type__in=['user', 'doctor_public']
    ).order_by('-created_at')
    
    # 应用时间筛选
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            # 计算该月的开始和结束日期
            import calendar
            from datetime import datetime, timedelta
            
            # 该月的第一天
            start_date = datetime(year, month, 1).date()
            
            # 该月的最后一天
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime(year, month, last_day).date()
            next_day = end_date + timedelta(days=1)
            
            # 筛选该月内的记录
            records = records.filter(
                created_at__date__gte=start_date,
                created_at__date__lt=next_day
            )
            
            print(f"筛选月份: {year}-{month:02d}, 记录数量: {records.count()}")
        except (ValueError, IndexError) as e:
            print(f"月份参数解析错误: {str(e)}")
            # 参数格式错误，忽略筛选
            pass

    # 判断是否显示催促按钮：只有最新一条记录是访客填写时才显示
    latest_record = profile.records.order_by('-created_at').first()
    show_urge_button = False
    if latest_record and latest_record.record_type == 'user':
        show_urge_button = True
    
    # 处理催促请求
    if request.method == 'POST':
        if 'toggle_urge' in request.POST:
            # 切换催促状态
            profile.is_urged = not profile.is_urged
            profile.save()
            
            if profile.is_urged:
                messages.success(request, '已设置期待回复')
            else:
                messages.success(request, '已取消期待回复')
            
            return redirect('patient_profile_detail', profile_id=profile.id)
        
        # 原有的添加记录逻辑
        elif 'add_record' in request.POST:
            content = request.POST.get('content', '').strip()
            if content:
                ProfileRecord.objects.create(
                    profile=profile,
                    content=content,
                    record_type='user',
                    created_by=request.user
                )
                messages.success(request, '记录添加成功')
                return redirect('patient_profile_detail', profile_id=profile.id)
    
    from django.db.models.functions import ExtractYear, ExtractMonth
    
    record_months = profile.records.annotate(
        year=ExtractYear('created_at'),
        month=ExtractMonth('created_at')
    ).values('year', 'month').distinct().order_by('-year', '-month')
    
    # 格式化为YYYY-MM格式
    month_choices = []
    for record in record_months:
        year = record['year']
        month = record['month']
        month_str = f"{year}-{month:02d}"
        month_choices.append({
            'value': month_str,
            'display': f"{year}年{month}月"
        })
    
    context = {
        'profile': profile,
        'records': records,
        'month_choices': month_choices,
        'month_filter': month_filter,
        'show_urge_button': show_urge_button,
    }
    return render(request, 'app/patient_profile_detail.html', context)

@login_required
def create_appointment(request):
    """创建预约页面"""
    # 复制原index视图中的创建逻辑
    from .forms import AppointmentForm
    
    # 计算统计数据
    unfinished_count = Appointment.objects.filter(
        guest=request.user,
        is_processed=False,
    ).count()
    
    today = timezone.now().date()
    daily_creations = DailyAppointmentCreation.objects.filter(
        user=request.user,
        creation_date=today
    ).count()
    
    error = None
    
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        
        # 每日创建次数限制检查
        if daily_creations >= 3:
            error = f'您今天已经创建了{daily_creations}个预约（包括已删除的），达到每日3次上限。'
        # 未处理预约数量限制检查
        elif unfinished_count >= 3:
            error = '您已有3个未处理或未删除预约，请等待处理完成后或明天再创建新预约。'
        elif form.is_valid():
            new_appointment = form.save(commit=False)
            new_appointment.guest = request.user
            new_appointment.save()
            messages.success(request, '预约创建成功！')
            return redirect('my_appointments')
    else:
        form = AppointmentForm()
    
    context = {
        'form': form,
        'unfinished_count': unfinished_count,
        'daily_creation_left': max(0, 3 - daily_creations),
        'error': error,
    }
    return render(request, 'app/create_appointment.html', context)

@login_required
def my_appointments(request):
    """我的预约列表页面"""
    # 获取用户的预约列表
    my_appointments = Appointment.objects.filter(
        guest=request.user
    ).order_by('-created_at')
    
    # 计算统计数据
    unfinished_count = Appointment.objects.filter(
        guest=request.user,
        is_processed=False,
    ).count()
    
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    weekly_urges = Appointment.objects.filter(
        guest=request.user,
        is_urged=True,
        is_deleted=False,
        urged_at__gte=start_of_week
    ).count()
    
    # 计算排队位置
    for app in my_appointments:
        if not app.is_processed and not app.is_deleted and app.is_responded:
            app.queue_position = DoctorQueueManager.get_queue_position(app)
        else:
            app.queue_position = None
    
    context = {
        'appointments': my_appointments,
        'unfinished_count': unfinished_count,
        'weekly_urges': weekly_urges,
        'urges_left': max(0, 1 - weekly_urges),
    }
    return render(request, 'app/my_appointments.html', context)

@login_required
def view_my_profile(request):
    """查看个人档案列表"""
    # 获取用户的档案列表
    profiles = Profile.objects.filter(account=request.user).order_by('-updated_at')
    
    # 为每个档案添加记录数量
    for profile in profiles:
        profile.record_count = profile.records.filter(
            record_type__in=['user', 'doctor_public']
        ).count()
    
    context = {
        'profiles': profiles,
    }
    return render(request, 'app/view_my_profile.html', context)

# 访客首页：创建预约 + 查看我的预约
@login_required
def index(request):
    """访客首页：显示预约表单和预约列表"""
    # 触发清理过期的已删除预约（使用缓存避免频繁清理）
    from django.core.cache import cache
    last_cleanup = cache.get(f'last_cleanup_{request.user.id}')
    
    if not last_cleanup:
        cleanup_expired_deleted_appointments()
        # 记录清理时间，缓存1小时（3600秒）
        cache.set(f'last_cleanup_{request.user.id}', timezone.now(), 3600)
    
    # 处理预约创建（POST请求）
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        
        # === 每日创建次数限制检查 ===
        today = timezone.now().date()
        daily_creations = DailyAppointmentCreation.objects.filter(
            user=request.user,
            creation_date=today
        ).count()
        
        if daily_creations >= 3:
            # 获取用户所有预约（包括已删除的）
            all_appointments = Appointment.objects.filter(
                guest=request.user
            ).order_by('-created_at')
            
            # 获取未删除的预约用于显示
            active_appointments = Appointment.objects.filter(
                guest=request.user,
                is_deleted=False
            ).order_by('-created_at')
            
            # 计算未处理预约数量
            unfinished_count = Appointment.objects.filter(
                guest=request.user,
                is_processed=False,
            ).count()
            
            # 计算本周催单次数
            start_of_week = today - timedelta(days=today.weekday())
            weekly_urges = Appointment.objects.filter(
                guest=request.user,
                is_urged=True,
                is_deleted=False,
                urged_at__gte=start_of_week
            ).count()
            
            return render(request, 'app/index.html', {
                'form': form,
                'appointments': active_appointments,
                'weekly_urges': weekly_urges,
                'urges_left': max(0, 1 - weekly_urges),
                'unfinished_count': unfinished_count,
                'daily_creation_count': daily_creations,
                'daily_creation_left': max(0, 3 - daily_creations),
                'error': f'您今天已经创建了{daily_creations}个预约（包括已删除的），达到每日3次上限。'
            })
        # === 每日限制检查结束 ===
        
        # === 未处理预约数量限制检查 ===
        unfinished_appointments = Appointment.objects.filter(
            guest=request.user,
            is_processed=False,
        ).count()
        
        if unfinished_appointments >= 3:
            # 获取今日创建次数（用于模板）
            daily_creations = DailyAppointmentCreation.objects.filter(
                user=request.user,
                creation_date=today
            ).count()
            
            # 计算本周催单次数
            start_of_week = today - timedelta(days=today.weekday())
            weekly_urges = Appointment.objects.filter(
                guest=request.user,
                is_urged=True,
                is_deleted=False,
                urged_at__gte=start_of_week
            ).count()
            
            return render(request, 'app/index.html', {
                'form': form,
                'appointments': Appointment.objects.filter(
                    guest=request.user,
                    is_deleted=False
                ).order_by('-created_at'),
                'daily_creation_count': daily_creations,
                'daily_creation_left': max(0, 3 - daily_creations),
                'weekly_urges': weekly_urges,
                'urges_left': max(0, 1 - weekly_urges),
                'unfinished_count': unfinished_appointments,
                'error': '您已有3个未处理或未删除预约，请等待处理完成后或明天再创建新预约。'
            })
        # === 未处理预约限制结束 ===
        
        # 验证并保存预约
        if form.is_valid():
            new_appointment = form.save(commit=False)
            new_appointment.guest = request.user
            new_appointment.save()
            
            # 创建每日创建记录（信号会自动处理）
            # 这里我们也可以手动创建，但信号已经处理了
            
            return redirect('index')
    else:
        form = AppointmentForm()
    
    # GET请求：显示预约列表和表单
    
    # 查询当前用户的所有预约（包括已删除的）
    my_appointments = Appointment.objects.filter(
        guest=request.user
    ).order_by('-created_at')
    
    # 计算今日创建次数
    today = timezone.now().date()
    daily_creations = DailyAppointmentCreation.objects.filter(
        user=request.user,
        creation_date=today
    ).count()
    
    # 计算本周催单次数
    start_of_week = today - timedelta(days=today.weekday())
    weekly_urges = Appointment.objects.filter(
        guest=request.user,
        is_urged=True,
        is_deleted=False,
        urged_at__gte=start_of_week
    ).count()
    
    # 计算未处理预约数量
    unfinished_count = Appointment.objects.filter(
        guest=request.user,
        is_processed=False,
    ).count()

    for app in my_appointments:
        if not app.is_processed and not app.is_deleted and app.is_responded:
            app.queue_position = DoctorQueueManager.get_queue_position(app)
        else:
            app.queue_position = None
    
    # 获取所有公告（按时间倒序）
    all_announcements = Announcement.objects.all().order_by('-created_at')
    
    # 获取用户上次登录时间（如果没有last_login，则使用注册时间）
    last_announcement_view_time = request.user.last_announcement_view_time
    # 原来的
    last_login_time = request.user.last_login if request.user.last_login else request.user.date_joined
    
    # 计算未读公告数量（发布时间晚于上次登录时间的公告）
    unread_announcements_count = 0
    for announcement in all_announcements:
        if announcement.created_at > last_announcement_view_time:
            unread_announcements_count += 1
    
    return render(request, 'app/index.html', {
        'form': form,
        'appointments': my_appointments,
        'weekly_urges': weekly_urges,
        'urges_left': max(0, 1 - weekly_urges),
        'unfinished_count': unfinished_count,
        'daily_creation_count': daily_creations,
        'daily_creation_left': max(0, 3 - daily_creations),
        'all_announcements': all_announcements,
        'unread_announcements_count': unread_announcements_count,
        'last_announcement_view_time': last_announcement_view_time,
        'last_login_time': last_login_time,
    })

@login_required
def delete_appointment(request, appointment_id):
    """软删除预约：标记为已删除，第二天自动清理"""
    appointment = get_object_or_404(Appointment, id=appointment_id, guest=request.user)
    
    # 检查预约是否已被删除
    if appointment.is_deleted:
        messages.warning(request, '此预约已被删除，等待系统清理。')
        return redirect('index')
    
    DoctorQueueManager.delete_appointment(appointment)
    # 触发一次清理已过期的已删除预约
    cleanup_expired_deleted_appointments()
    
    messages.success(request, '预约已标记为删除，将于明天自动清理。')
    return redirect('index')

# 催单功能
@login_required
def urge_appointment(request, appointment_id):
    """催单功能"""
    appointment = get_object_or_404(Appointment, id=appointment_id, guest=request.user)
    
    # 检查本周是否已经催单过 - 使用更简单的方法
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # 获取本周开始时间
    now = timezone.now()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 检查当前用户本周是否有催单记录
    weekly_urges = Appointment.objects.filter(
        guest=request.user,
        is_urged=True,
        urged_at__gte=start_of_week
    ).count()
    
    if weekly_urges >= 1:
        messages.error(request, '本周您已经催单过一次，请下周再试。')
        return redirect('index')
    
    # 检查预约是否符合催单条件：已回应、未处理、未催单
    if appointment.is_responded and not appointment.is_processed and not appointment.is_urged:
        appointment.is_urged = True
        appointment.urged_at = timezone.now()  # 使用本地时间
        appointment.save()
        messages.success(request, '催单成功！')
        
        # 记录日志
        print(f"催单成功 - 用户: {request.user.email}, 预约ID: {appointment_id}, 时间: {appointment.urged_at}")
    else:
        messages.error(request, '该预约当前无法催单。')
    
    return redirect('index')

@login_required
def update_appointment(request, appointment_id):
    """修改预约（只能修改需求和微信号）"""
    from django.utils import timezone
    from datetime import datetime
    
    appointment = get_object_or_404(Appointment, id=appointment_id, guest=request.user)
    
    # 检查1：已处理的预约不能修改
    if appointment.is_processed:
        messages.error(request, '该预约已处理，无法修改。')
        return redirect('index')
    
    # 检查2：今天是否还可以修改（使用新的属性方法）
    can_modify = appointment.can_modify_today_bool()
    modify_reason = appointment.can_modify_today_reason()
    
    if not can_modify:
        messages.error(request, f'无法修改：{modify_reason}')
        return redirect('index')
    
    if request.method == 'POST':
        form = AppointmentUpdateForm(request.POST, instance=appointment)
        if form.is_valid():
            # 使用Django的时区时间
            now = timezone.now()
            today = now.date()
            
            # 获取上次修改的日期（如果有）
            if appointment.last_modified_at:
                last_modified_date = appointment.last_modified_at.astimezone(
                    timezone.get_current_timezone()
                ).date()
            else:
                last_modified_date = None
            
            # 检查是否是今天第一次修改
            if last_modified_date != today:
                # 不是今天，或者从未修改过，重置为1
                appointment.today_modified_count = 1
            else:
                # 今天已经修改过，增加次数
                appointment.today_modified_count += 1
            
            # 更新修改时间
            appointment.last_modified_at = now
            
            # 保存修改
            form.save()
            appointment.save()
            
            messages.success(request, '预约修改成功！')
            return redirect('index')
    else:
        form = AppointmentUpdateForm(instance=appointment)
    
    return render(request, 'app/update_appointment.html', {
        'form': form,
        'appointment': appointment,
        'can_modify': can_modify,
        'modify_reason': modify_reason
    })

# 在现有导入后面添加
from .doctor_utils import DoctorQueueManager

# 医师装饰器（检查是否是医师）
def doctor_required(view_func):
    """装饰器：检查用户是否是医师（超级用户）"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_superuser:
            messages.error(request, '您没有权限访问医师界面')
            return redirect('index')
        return view_func(request, *args, **kwargs)
    return wrapper

# 医师首页
@doctor_required
def doctor_index(request):
    """医师首页"""
    # 统计数量
    urge_count = Appointment.objects.filter(
        is_urged=True,
        is_processed=False,
        is_deleted=False
    ).count()
    
    unresponded_count = Appointment.objects.filter(
        is_responded=False,
        is_processed=False,
        is_deleted=False
    ).count()
    
    unprocessed_count = Appointment.objects.filter(
        is_urged=False,
        is_responded=True,
        is_processed=False,
        is_deleted=False
    ).count()
    
    # 获取最近的公告（最多5条）
    announcements = Announcement.objects.all().order_by('-created_at')[:5]
    
    context = {
        'urge_count': urge_count,
        'unresponded_count': unresponded_count,
        'unprocessed_count': unprocessed_count,
        'announcements': announcements,
        'now': timezone.now(),
    }
    return render(request, 'app/doctor_index.html', context)

@doctor_required
def doctor_respond(request):
    """回应预约"""
    appointment = DoctorQueueManager.get_unresponded_appointment()
    
    if request.method == 'POST':
        if appointment:
            # 更新预约信息
            appointment.annotation = request.POST.get('annotation', '')
            appointment.note = request.POST.get('note', '')
            
            # 可以修改优先级
            if 'priority' in request.POST:
                appointment.priority = int(request.POST['priority'])
            
            # 标记为已回应
            appointment.is_responded = True
            appointment.is_processed = False
            appointment.save()

            send_appointment_notification(
                appointment=appointment,
                action_type='responded',
                annotation=appointment.annotation,
                note=appointment.note
            )
            
            messages.success(request, '预约已回应')
    
    # 获取下一个未回应的预约
    appointment = DoctorQueueManager.get_unresponded_appointment()
    
    context = {
        'appointment': appointment,
    }
    return render(request, 'app/doctor_respond.html', context)

@doctor_required
def doctor_urge(request):
    """处理催单"""
    appointment = DoctorQueueManager.get_urge_appointment()
    
    if request.method == 'POST':
        if appointment:
            annotation = request.POST.get('annotation', '')
            note = request.POST.get('note', '')
            priority = request.POST.get('priority', appointment.priority)
            
            DoctorQueueManager.urge_appointment(appointment, annotation, note, priority)

            send_appointment_notification(
                appointment=appointment,
                action_type='urge_processed',
                annotation=annotation,
                note=note
            )
            
            messages.success(request, '催单已处理')
    
    # 获取下一个催单（处理完成后）
    appointment = DoctorQueueManager.get_urge_appointment()
    
    context = {
        'appointment': appointment,
        'queue_stats': DoctorQueueManager.get_queue_stats(),
    }
    return render(request, 'app/doctor_urge.html', context)

# 在处理预约的视图中添加优先级更新

@doctor_required
def doctor_process(request):
    """处理预约"""

    if request.method == 'POST' and 'refresh_queue' in request.POST:
        DoctorQueueManager.refresh_queue()
        messages.success(request, '队列已刷新！')
        return redirect('doctor_process')

    appointment = DoctorQueueManager.get_next_processing_appointment()
    
    if request.method == 'POST':
        if appointment:
            # 使用新的处理函数
            annotation = request.POST.get('annotation', '')
            note = request.POST.get('note', '')
            
            # 处理预约
            DoctorQueueManager.process_appointment(appointment, annotation, note)

            send_appointment_notification(
                appointment=appointment,
                action_type='processed',
                annotation=annotation,
                note=note
            )
            
            messages.success(request, f'预约 #{appointment.id} 已处理，已发送邮件通知访客')
            
            # 重定向回处理页面，获取下一个预约
            return redirect('doctor_process')
    
    # 获取下一个待处理的预约
    appointment = DoctorQueueManager.get_next_processing_appointment()
    
    context = {
        'appointment': appointment,
        'queue_stats': DoctorQueueManager.get_queue_stats(),
    }
    return render(request, 'app/doctor_process.html', context)

# 更新医生所有预约页面，确保正确处理预约后的队列更新
@doctor_required
def doctor_all(request):
    """查看所有预约 - 支持筛选和直接操作"""
    # 获取筛选参数
    filter_type = request.GET.get('filter', 'all')
    search_query = request.GET.get('search', '')
    page = request.GET.get('page', 1)
    
    # 基础查询集（排除已删除的）
    appointments = Appointment.objects.filter(is_deleted=False)
    
    # 应用筛选
    if filter_type == 'urge':
        appointments = appointments.filter(
            is_urged=True,
            is_responded=False,
            is_processed=False
        )
    elif filter_type == 'unresponded':
        appointments = appointments.filter(
            is_responded=False,
            is_processed=False
        ).exclude(is_urged=True)  # 排除催单，因为催单有单独筛选
    elif filter_type == 'processed':
        appointments = appointments.filter(is_processed=True)
    elif filter_type == 'responded_unprocessed':
        appointments = appointments.filter(
            is_responded=True,
            is_processed=False
        )
    
    # 应用搜索
    if search_query:
        appointments = appointments.filter(
            Q(patient_name__icontains=search_query) |
            Q(demand__icontains=search_query) |
            Q(wechat_id__icontains=search_query) |
            Q(annotation__icontains=search_query) |
            Q(note__icontains=search_query)
        )
    
    # 排序：按创建时间倒序
    appointments = appointments.order_by('-created_at')
    
    # 分页（每页20条）
    from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
    paginator = Paginator(appointments, 20)
    try:
        appointments_page = paginator.page(page)
    except PageNotAnInteger:
        appointments_page = paginator.page(1)
    except EmptyPage:
        appointments_page = paginator.page(paginator.num_pages)
    
    # 处理回应预约的POST请求
    if request.method == 'POST' and 'respond' in request.POST:
        appointment_id = request.POST.get('appointment_id')
        try:
            appointment = Appointment.objects.get(id=appointment_id, is_deleted=False)
            
            # 使用新的回应函数
            annotation = request.POST.get('annotation', '')
            note = request.POST.get('note', '')
            priority = request.POST.get('priority', appointment.priority)
            
            DoctorQueueManager.respond_appointment(
                appointment, 
                annotation, 
                note, 
                int(priority) if priority else None
            )
            
            # 如果是催单，处理完成后重置催单状态
            if appointment.is_urged:
                appointment.is_urged = False
                appointment.save()
            
            send_appointment_notification(
                appointment=appointment,
                action_type='responded',
                annotation=annotation,
                note=note
            )
            
            messages.success(request, f'预约 #{appointment.id} 已回应')
            
            # 重定向回当前页面，保持筛选条件
            params = request.GET.copy()
            return redirect(f"{request.path}?{params.urlencode()}")
            
        except Appointment.DoesNotExist:
            messages.error(request, '预约不存在')
    
    # 处理处理预约的POST请求
    elif request.method == 'POST' and 'process' in request.POST:
        appointment_id = request.POST.get('appointment_id')
        try:
            appointment = Appointment.objects.get(id=appointment_id, is_deleted=False)
            
            # 使用新的处理函数
            annotation = request.POST.get('annotation', '')
            note = request.POST.get('note', '')
            
            DoctorQueueManager.process_appointment(appointment, annotation, note)

            send_appointment_notification(
                appointment=appointment,
                action_type='processed',
                annotation=annotation,
                note=note
            )
            
            messages.success(request, f'预约 #{appointment.id} 已处理')
            
            # 重定向回当前页面，保持筛选条件
            params = request.GET.copy()
            return redirect(f"{request.path}?{params.urlencode()}")
            
        except Appointment.DoesNotExist:
            messages.error(request, '预约不存在')
    
    context = {
        'appointments': appointments_page,
        'filter_type': filter_type,
        'search_query': search_query,
        'page': page,
        'queue_stats': DoctorQueueManager.get_queue_stats(),
    }
    return render(request, 'app/doctor_all.html', context)

# 从处理池中移除预约
@doctor_required
def doctor_remove_from_pool(request, appointment_id):
    """从处理池中移除预约"""
    DoctorQueueManager.remove_from_processing_pool(appointment_id)
    messages.success(request, '已从处理池中移除')
    return redirect('doctor_all')

@doctor_required
def user_accounts(request):
    """用户档案管理"""
    search_query = request.GET.get('search', '')
    page = request.GET.get('page', 1)
    
    # 获取所有用户（排除医师账号）
    users = CustomUser.objects.filter(is_superuser=False)
    
    # 应用搜索
    if search_query:
        users = users.filter(
            Q(email__icontains=search_query)
        )
    
    # 为每个用户添加统计数据
    for user in users:
        # 用户的预约总数
        user.total_appointments = Appointment.objects.filter(
            guest=user
        ).count()
        
        # 进行中的预约（已回应但未处理）
        user.active_appointments = Appointment.objects.filter(
            guest=user,
            is_responded=True,
            is_processed=False,
            is_deleted=False
        ).count()
        
        # 已完成的预约
        user.completed_appointments = Appointment.objects.filter(
            guest=user,
            is_processed=True,
            is_deleted=False
        ).count()
    
    # 排序：按最后登录时间倒序，从未登录的排最后
    users = sorted(users, key=lambda u: u.last_login or timezone.make_aware(dt.min), reverse=True)
    
    # 分页（每页10条）
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    paginator = Paginator(users, 10)
    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)
    
    # 统计数据
    total_users = CustomUser.objects.filter(is_superuser=False).count()
    active_users = CustomUser.objects.filter(
        is_superuser=False,
        is_active=True
    ).count()
    
    # 7日内新增用户
    from datetime import timedelta
    week_ago = timezone.now() - timedelta(days=7)
    new_users_7days = CustomUser.objects.filter(
        is_superuser=False,
        date_joined__gte=week_ago
    ).count()
    
    # 总预约数
    appointments_total = Appointment.objects.filter(is_deleted=False).count()
    
    context = {
        'users': users_page,
        'search_query': search_query,
        'total_users': total_users,
        'active_users': active_users,
        'new_users_7days': new_users_7days,
        'appointments_total': appointments_total,
    }
    
    return render(request, 'app/user_accounts.html', context)

@doctor_required
def toggle_user_status(request, user_id):
    """切换用户状态（激活/停用）"""
    user = get_object_or_404(CustomUser, id=user_id, is_superuser=False)
    
    # 切换状态
    user.is_active = not user.is_active
    user.save()
    
    action = "激活" if user.is_active else "停用"
    messages.success(request, f'用户 {user.email} 已{action}')
    
    return redirect('user_accounts')

# 在 views.py 中添加以下视图函数

from .forms import ProfileForm, ProfileRecordForm  # 稍后需要创建这些表单
from .models import Profile, ProfileRecord

@doctor_required
def patients_info(request):
    """档案管理页面"""
    search_query = request.GET.get('search', '')
    page = request.GET.get('page', 1)
    
    # 获取所有档案
    profiles = Profile.objects.all().order_by('-is_urged', '-updated_at')
    
    # 应用搜索
    if search_query:
        profiles = profiles.filter(
            Q(name__icontains=search_query) |
            Q(wechat_id__icontains=search_query) |
            Q(account__email__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    # 为每个档案添加统计信息
    for profile in profiles:
        profile.record_count = profile.records.count()
        profile.latest_record = profile.records.first()
    
    # 分页（每页15条）
    paginator = Paginator(profiles, 15)
    try:
        profiles_page = paginator.page(page)
    except PageNotAnInteger:
        profiles_page = paginator.page(1)
    except EmptyPage:
        profiles_page = paginator.page(paginator.num_pages)
    
    # 统计信息
    total_profiles = Profile.objects.count()
    profiles_with_account = Profile.objects.filter(account__isnull=False).count()
    total_records = ProfileRecord.objects.count()
    urged_profiles_count = Profile.objects.filter(is_urged=True).count()
    
    context = {
        'profiles': profiles_page,
        'search_query': search_query,
        'total_profiles': total_profiles,
        'profiles_with_account': profiles_with_account,
        'total_records': total_records,
        'urged_profiles_count': urged_profiles_count,
        'page': page,
    }
    
    return render(request, 'app/patients_info.html', context)

@doctor_required
def profile_detail(request, profile_id):
    """查看档案详情"""
    profile = get_object_or_404(Profile, id=profile_id)
    
    # 获取时间筛选参数
    date_filter = request.GET.get('date', '')
    record_type_filter = request.GET.get('record_type', '')
    
    # 获取记录（访客只能看到公开的记录）
    if request.user.is_superuser:
        # 医师可以看到所有记录
        records = profile.records.all()
    else:
        # 访客只能看到访客记录和医师公开记录
        records = profile.records.filter(
            record_type__in=['user', 'doctor_public']
        )
    
    # 应用筛选
    if date_filter:
        try:
            # 转换为日期范围
            from datetime import datetime, timedelta
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            next_day = filter_date + timedelta(days=1)
            
            records = records.filter(
                created_at__date__gte=filter_date,
                created_at__date__lt=next_day
            )
        except ValueError:
            pass
    
    if record_type_filter in ['user', 'doctor_public', 'doctor_private']:
        records = records.filter(record_type=record_type_filter)
    
    # 获取所有有记录的日期
    record_dates = profile.records.dates('created_at', 'day', order='DESC')
    
    # 处理添加记录
    if request.method == 'POST':
        if 'add_record' in request.POST:
            if not request.user.is_superuser:
                post_data = request.POST.copy()
                post_data['record_type'] = 'user'
                record_form = ProfileRecordForm(post_data, user=request.user)
            else:
                record_form = ProfileRecordForm(request.POST, user=request.user)
            
            if record_form.is_valid():
                record = record_form.save(commit=False)
                record.profile = profile
                record.created_by = request.user
                record.save()
                
                # 更新档案的更新时间
                profile.save()
                
                # 检查是否发送邮件：只有医师添加的用户可见记录才发送
                # 用户可见的记录类型包括：'user'（访客记录）和 'doctor_public'（医师公开记录）
                # 但通常只有医师的 'doctor_public' 记录需要通知用户，访客的 'user' 记录不需要通知
                if (record.record_type in ['doctor_public'] and 
                    profile.account and 
                    profile.account.email):
                    
                    # 发送邮件通知用户
                    send_profile_record_notification(
                        profile=profile,
                        record=record,
                        action_type='record_added'
                    )
                    
                    # 如果档案处于催促状态，重置为False
                    if profile.is_urged:
                        profile.is_urged = False
                        profile.save()
                        print(f"档案 {profile.name} 催促状态已重置")
                
                messages.success(request, '记录添加成功')
                return redirect('profile_detail', profile_id=profile.id)
    
    record_form = ProfileRecordForm(user=request.user)
    
    context = {
        'profile': profile,
        'records': records,
        'record_form': record_form,
        'record_dates': record_dates,
        'date_filter': date_filter,
        'record_type_filter': record_type_filter,
    }
    return render(request, 'app/profile_detail.html', context)


@doctor_required
def create_profile(request):
    """创建档案"""
    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.created_by = request.user
            profile.save()
            
            # 添加创建记录
            initial_record = form.cleaned_data.get('initial_record')
            if initial_record:
                ProfileRecord.objects.create(
                    profile=profile,
                    content=initial_record,
                    record_type='doctor',
                    created_by=request.user
                )
            
            messages.success(request, f'档案 {profile.name} 创建成功')
            return redirect('patients_info')
    else:
        form = ProfileForm()
    
    context = {
        'form': form,
        'title': '创建档案',
    }
    return render(request, 'app/profile_form.html', context)

@doctor_required
def edit_profile(request, profile_id):
    """编辑档案"""
    profile = get_object_or_404(Profile, id=profile_id)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f'档案 {profile.name} 更新成功')
            return redirect('profile_detail', profile_id=profile.id)
    else:
        form = ProfileForm(instance=profile)
    
    context = {
        'form': form,
        'profile': profile,
        'title': '编辑档案',
    }
    return render(request, 'app/profile_form.html', context)


@doctor_required
def delete_profile_record(request, record_id):
    """删除档案记录"""
    record = get_object_or_404(ProfileRecord, id=record_id)
    profile_id = record.profile.id
    
    if request.method == 'POST':
        record.delete()
        messages.success(request, '记录删除成功')
    
    return redirect('profile_detail', profile_id=profile_id)


@doctor_required
def delete_profile(request, profile_id):
    """删除档案"""
    profile = get_object_or_404(Profile, id=profile_id)
    
    if request.method == 'POST':
        name = profile.name
        profile.delete()
        messages.success(request, f'档案 {name} 删除成功')
        return redirect('patients_info')
    
    context = {
        'profile': profile,
    }
    return render(request, 'app/confirm_delete_profile.html', context)

# 在 views.py 中添加以下视图函数

from django.http import JsonResponse

@doctor_required
def autocomplete_accounts(request):
    """自动完成账号搜索"""
    query = request.GET.get('q', '').strip()
    
    print(f"搜索账号查询: {query}")  # 调试信息
    
    if not query:
        return JsonResponse([], safe=False)
    
    # 搜索非医师账号（排除超级用户）
    users = CustomUser.objects.filter(
        email__icontains=query,
        is_superuser=False
    ).order_by('email')[:10]  # 限制返回10个结果
    
    print(f"找到 {users.count()} 个匹配用户")  # 调试信息
    
    # 构建返回数据
    results = []
    for user in users:
        results.append({
            'id': user.id,
            'email': user.email,
            'display': f'{user.email} (用户ID: {user.id})'
        })
    
    print(f"返回结果: {results}")  # 调试信息
    
    return JsonResponse(results, safe=False)


# 在导入部分添加
from .models import Announcement
from .forms import AnnouncementForm

# 在 views.py 中添加以下函数

def send_announcement_notification(announcement):
    """
    发送纯文本公告通知邮件给所有用户
    """
    try:
        # 获取所有活跃的非超级用户邮箱
        recipients = list(CustomUser.objects.filter(
            is_active=True,
            is_superuser=False
        ).exclude(email='').distinct())
        
        if not recipients:
            print("没有找到有效的收件人")
            return
        
        # 将时间转换为东八区时间（北京时间）
        from django.utils import timezone
        import pytz
        
        # 获取公告的创建时间（已经是带时区的时间）
        created_at = announcement.created_at
        
        # 转换为东八区时间
        beijing_tz = pytz.timezone('Asia/Shanghai')
        beijing_time = created_at.astimezone(beijing_tz)
        
        # 邮件主题
        subject = f'【缥缈旅】公告：{announcement.title}'
        
        # 构建纯文本邮件内容
        message = f"""
=== 伯里欧斯的公告 ===

标题：{announcement.title}

公告内容：
{announcement.content}

发布时间：{beijing_time.strftime('%Y年%m月%d日 %H:%M')}（北京时间）

=== 温馨提示 ===
1. 此邮件由系统自动发送，请勿直接回复
2. 感谢您使用缥缈旅

伯里欧斯的小助手
"""
        
        # 提取邮箱列表
        recipient_emails = [user.email for user in recipients if user.email]
        
        # 发送邮件
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_emails,
            fail_silently=True,
        )
        
        print(f"纯文本公告邮件已发送至 {len(recipient_emails)} 个用户")
        
    except Exception as e:
        print(f"公告邮件发送失败: {str(e)}")


@doctor_required
def create_announcement(request):
    """创建公告"""
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            # 检查公告数量，最多保留5条
            announcement_count = Announcement.objects.count()
            if announcement_count >= 5:
                # 删除最早的公告（按创建时间排序）
                oldest_announcement = Announcement.objects.order_by('created_at').first()
                if oldest_announcement:
                    oldest_announcement.delete()
                    print(f"已删除最早的公告: {oldest_announcement.title}")
            
            # 保存新公告
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            
            # 发送邮件通知
            send_announcement_notification(announcement)
            
            messages.success(request, '公告发布成功，已发送邮件通知所有用户！')
            return redirect('doctor_index')
    else:
        form = AnnouncementForm()
    
    return render(request, 'app/create_announcement.html', {'form': form})


@doctor_required
def delete_announcement(request, announcement_id):
    """删除公告"""
    announcement = get_object_or_404(Announcement, id=announcement_id)
    
    if request.method == 'POST':
        title = announcement.title
        announcement.delete()
        messages.success(request, f'公告 "{title}" 已删除')
        return redirect('doctor_index')
    
    return render(request, 'app/confirm_delete_announcement.html', {
        'announcement': announcement
    })

@login_required
def announcement_list(request):
    """公告列表页面"""
    # 获取所有公告（按时间倒序）
    announcements = Announcement.objects.all().order_by('-created_at')
    
    # 获取用户上次登录时间
    last_view_time = request.user.last_announcement_view_time
    
    # 标记未读公告（发布时间晚于上次查看公告时间的公告）
    unread_announcements = []
    for announcement in announcements:
        # 如果用户从未查看过公告，或者公告发布时间晚于上次查看时间，则标记为未读
        if not last_view_time or announcement.created_at > last_view_time:
            announcement.is_unread = True
            unread_announcements.append(announcement)
        else:
            announcement.is_unread = False
    
    # 计算未读公告数量
    unread_count = len(unread_announcements)

    request.user.last_announcement_view_time = timezone.now()
    request.user.save()
    
    context = {
        'announcements': announcements,
        'unread_count': unread_count,
        'last_login_time': last_view_time,
        'now': timezone.now(),
    }
    
    return render(request, 'app/announcement_list.html', context)

@doctor_required
def delete_user_account(request, user_id):
    """删除用户账号"""
    user = get_object_or_404(CustomUser, id=user_id, is_superuser=False)
    
    if request.method == 'POST':
        # 获取用户邮箱用于显示消息
        user_email = user.email
        
        # 1. 软删除该用户的所有预约
        Appointment.objects.filter(guest=user).update(
            is_deleted=True,
            deleted_at=timezone.now()
        )
        
        # 2. 将该用户的档案的account字段设为NULL（保持档案不删除）
        Profile.objects.filter(account=user).update(account=None)
        
        # 3. 删除用户账号
        user.delete()
        
        messages.success(request, f'用户 {user_email} 的账号已删除')
        return redirect('user_accounts')
    
    # 如果是GET请求，显示确认页面
    # 统计用户相关信息用于显示
    appointments_count = Appointment.objects.filter(guest=user).count()
    active_appointments_count = Appointment.objects.filter(
        guest=user,
        is_deleted=False
    ).count()
    profiles_count = Profile.objects.filter(account=user).count()
    
    context = {
        'user': user,
        'appointments_count': appointments_count,
        'active_appointments_count': active_appointments_count,
        'profiles_count': profiles_count,
    }
    
    return render(request, 'app/confirm_delete_user.html', context)


from .backup_utils import DataBackupManager
from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render
import os

@doctor_required
def data_backup(request):
    """数据备份页面"""
    # 列出已有备份
    backups = DataBackupManager.list_backups()

    # 获取当前数据库统计信息
    stats = DataBackupManager.get_database_info()
    
    context = {
        'backups': backups,
        'stats': stats,
    }
    return render(request, 'app/data_backup.html', context)

@doctor_required
def download_backup(request, filename):
    """下载备份文件"""
    backup_dir = DataBackupManager.get_backup_directory()
    filepath = os.path.join(backup_dir, filename)
    
    if os.path.exists(filepath):
        response = FileResponse(open(filepath, 'rb'), as_attachment=True)
        response['Content-Type'] = 'application/zip'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        messages.error(request, '备份文件不存在')
        return redirect('data_backup')


import traceback  # 添加这行到文件顶部导入部分

@doctor_required
def create_backup(request):
    """创建数据备份"""
    try:
        backup_path = DataBackupManager.create_backup()
        filename = os.path.basename(backup_path)
        
        messages.success(request, f'数据备份创建成功: {filename}')
        
        # 返回备份文件下载
        response = FileResponse(open(backup_path, 'rb'), as_attachment=True)
        response['Content-Type'] = 'application/zip'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        error_msg = f'备份创建失败: {str(e)}'
        print(f"备份错误详情: {traceback.format_exc()}")  # 打印详细错误信息
        messages.error(request, error_msg)
        return redirect('data_backup')

@doctor_required
def restore_backup(request):
    """恢复数据备份"""
    if request.method == 'POST':
        if 'backup_file' not in request.FILES:
            messages.error(request, '请选择备份文件')
            return redirect('data_backup')
        
        backup_file = request.FILES['backup_file']
        
        # 检查文件类型
        if not backup_file.name.endswith('.zip'):
            messages.error(request, '请上传ZIP格式的备份文件')
            return redirect('data_backup')
        
        # 检查文件大小（限制为100MB）
        if backup_file.size > 100 * 1024 * 1024:
            messages.error(request, '备份文件太大，请确保文件小于100MB')
            return redirect('data_backup')
        
        # 保存上传的文件到临时位置
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            for chunk in backup_file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name
        
        try:
            # 执行恢复
            restore_stats = DataBackupManager.restore_backup(temp_path)
            
            # 清理临时文件
            os.unlink(temp_path)
            
            # 统计结果
            total_restored = sum(restore_stats.get(key, 0) for key in [
                'users', 'appointments', 'profiles', 'profile_records',
                'daily_creations', 'announcements', 'processing_pools'
            ])
            
            error_count = len(restore_stats.get('errors', []))
            
            if error_count == 0:
                messages.success(request, f'数据恢复成功！共恢复 {total_restored} 条记录。')
            else:
                # 显示前5个错误
                error_samples = restore_stats['errors'][:5]
                error_message = f'数据恢复完成，共恢复 {total_restored} 条记录，但有 {error_count} 个错误。'
                if error_samples:
                    error_message += f' 示例错误: {error_samples[0]}'
                messages.warning(request, error_message)
            
            return redirect('data_backup')
            
        except Exception as e:
            # 清理临时文件
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            
            error_msg = f'数据恢复失败: {str(e)}'
            print(f"恢复错误详情: {traceback.format_exc()}")  # 打印详细错误信息
            messages.error(request, error_msg)
            return redirect('data_backup')
    
    return redirect('data_backup')

@doctor_required
def delete_backup(request, filename):
    """删除备份文件"""
    try:
        success = DataBackupManager.delete_backup(filename)
        if success:
            messages.success(request, f'备份文件 {filename} 已删除')
        else:
            messages.error(request, '备份文件删除失败')
    except Exception as e:
        messages.error(request, f'删除失败: {str(e)}')
    
    return redirect('data_backup')

@doctor_required
def backup_info(request, filename):
    """获取备份文件信息"""
    backup_dir = DataBackupManager.get_backup_directory()
    filepath = os.path.join(backup_dir, filename)
    
    if not os.path.exists(filepath):
        return JsonResponse({'error': '文件不存在'}, status=404)
    
    try:
        import zipfile
        import json
        
        with zipfile.ZipFile(filepath, 'r') as zipf:
            # 读取备份信息
            with zipf.open('backup_info.json') as f:
                backup_info = json.load(f)
            
            # 获取文件大小
            file_stat = os.stat(filepath)
            
            return JsonResponse({
                'filename': filename,
                'size': file_stat.st_size,
                'created_time': file_stat.st_ctime,
                'backup_info': backup_info,
            })
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)