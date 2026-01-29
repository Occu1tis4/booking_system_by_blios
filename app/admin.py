from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Appointment
from django.utils.translation import gettext_lazy as _

class CustomUserAdmin(UserAdmin):
    """自定义用户管理界面"""
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('个人信息'), {'fields': ('first_name', 'last_name')}),
        (_('账户状态'), {'fields': ('to_be_deleted', 'to_be_deleted_notified_at', 'last_login_before_deletion')}),
        (_('医师设置'), {'fields': ('last_processed_priority',)}),  # 新增医师设置部分
        (_('权限'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('重要日期'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'to_be_deleted', 'last_processed_priority')
    list_filter = ('to_be_deleted', 'is_staff', 'is_superuser')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

# 注册模型到管理员后台
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Appointment)