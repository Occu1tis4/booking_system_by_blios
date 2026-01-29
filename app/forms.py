from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Appointment, CustomUser, Announcement
from django.core.exceptions import ValidationError

class EmailVerificationForm(forms.Form):
    """邮箱验证表单（第一步）"""
    email = forms.EmailField(
        label="邮箱地址",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入您的邮箱',
            'autocomplete': 'email'
        })
    )
    
    def clean_email(self):
        """验证邮箱是否已注册"""
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError("该邮箱已被注册")
        return email

class CustomUserCreationForm(UserCreationForm):
    """自定义用户注册表单（第二步）"""
    verification_code = forms.CharField(
        label="验证码",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '请输入6位验证码',
            'autocomplete': 'off'
        })
    )
    
    class Meta:
        model = CustomUser
        fields = ("email", "password1", "password2", "verification_code")
    
    def __init__(self, *args, **kwargs):
        self.email = kwargs.pop('email', None)
        super().__init__(*args, **kwargs)
        
        # 如果提供了邮箱，则隐藏邮箱字段
        if self.email:
            self.fields['email'].widget = forms.HiddenInput()
            self.fields['email'].initial = self.email
    
    def clean_verification_code(self):
        """验证验证码"""
        from .utils import verify_code
        
        email = self.cleaned_data.get('email') or self.email
        code = self.cleaned_data.get('verification_code')
        
        if not email:
            raise ValidationError("邮箱不能为空")
        
        is_valid, message = verify_code(email, code)
        if not is_valid:
            raise ValidationError(message)
        
        return code

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        # 访客创建预约时允许填写的字段
        fields = ['patient_name', 'demand', 'wechat_id', 'priority']

class AppointmentUpdateForm(forms.ModelForm):
    """修改预约表单（只允许修改需求和微信号）"""
    class Meta:
        model = Appointment
        fields = ['demand', 'wechat_id']  # 只允许修改这两个字段
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 可以为字段添加额外属性
        self.fields['demand'].widget.attrs.update({'rows': 4})

from .models import Profile, ProfileRecord

# 在 forms.py 中修改 ProfileForm

class ProfileForm(forms.ModelForm):
    """档案表单"""
    initial_record = forms.CharField(
        label='初始记录（可选）',
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': '可以在此添加一条初始记录'
        })
    )
    
    account_email = forms.CharField(
        label='归属账号（邮箱）',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'account-autocomplete',
            'placeholder': '输入邮箱搜索并选择...',
            'autocomplete': 'off'
        })
    )
    
    class Meta:
        model = Profile
        fields = ['name', 'wechat_id', 'notes', 'overview']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': '请输入姓名'}),
            'wechat_id': forms.TextInput(attrs={'placeholder': '请输入微信号'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': '备注信息'}),
            'overview': forms.Textarea(attrs={'rows': 3, 'placeholder': '概述信息（仅医师可见）'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 如果有实例，设置初始邮箱值
        if self.instance and self.instance.account:
            self.fields['account_email'].initial = self.instance.account.email
    
    def clean_account_email(self):
        """验证并获取账号邮箱"""
        email = self.cleaned_data.get('account_email', '').strip()
        
        if not email:
            return None
        
        # 尝试通过邮箱查找用户
        try:
            user = CustomUser.objects.get(email=email, is_superuser=False)
            return user
        except CustomUser.DoesNotExist:
            # 如果没有找到用户，可以创建新用户或返回None
            # 这里我们返回None，表示没有关联账号
            return None
    
    def save(self, commit=True):
        """保存表单，处理账号关联"""
        profile = super().save(commit=False)
        
        # 设置关联账号
        user = self.cleaned_data.get('account_email')
        profile.account = user
        
        if commit:
            profile.save()
            self.save_m2m()
        
        return profile


class ProfileRecordForm(forms.ModelForm):
    """档案记录表单"""
    class Meta:
        model = ProfileRecord
        fields = ['content', 'record_type']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '请输入记录内容...',
                'class': 'record-content'
            }),
            'record_type': forms.Select(attrs={'class': 'record-type'}),
        }
    
    def __init__(self, *args, **kwargs):
        # 获取用户信息，如果是医师则可以创建所有类型，否则只能创建访客记录
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.is_superuser:
            # 医师可以选择所有类型
            self.fields['record_type'].choices = ProfileRecord.RECORD_TYPE_CHOICES
            self.fields['record_type'].initial = 'doctor_public'
        else:
            # 访客只能创建访客记录
            self.fields['record_type'].choices = [
                ('user', '访客')
            ]
            self.fields['record_type'].initial = 'user'
            self.fields['record_type'].widget.attrs['disabled'] = True

# 在 forms.py 中添加 AnnouncementForm
class AnnouncementForm(forms.ModelForm):
    """公告表单"""
    class Meta:
        model = Announcement
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入公告标题',
                'maxlength': '200'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': '请输入公告内容...',
                'rows': 5
            })
        }
    
    def clean_title(self):
        """验证标题"""
        title = self.cleaned_data.get('title')
        if not title or title.strip() == '':
            raise forms.ValidationError("标题不能为空")
        return title.strip()
    
    def clean_content(self):
        """验证内容"""
        content = self.cleaned_data.get('content')
        if not content or content.strip() == '':
            raise forms.ValidationError("公告内容不能为空")
        return content.strip()