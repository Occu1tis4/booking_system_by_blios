from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create_appointment, name='create_appointment'),
    path('my-appointments/', views.my_appointments, name='my_appointments'),
    path('my-profile/', views.view_my_profile, name='view_my_profile'),
    
    path('delete/<int:appointment_id>/', views.delete_appointment, name='delete'),
    path('register/', views.register, name='register'),
    path('urge/<int:appointment_id>/', views.urge_appointment, name='urge'),
    path('update/<int:appointment_id>/', views.update_appointment, name='update'),

    path('login_redirect/', views.login_redirect, name='login_redirect'),
    
    path('doctor/', views.doctor_index, name='doctor_index'),
    path('doctor/urge/', views.doctor_urge, name='doctor_urge'),
    path('doctor/respond/', views.doctor_respond, name='doctor_respond'),
    path('doctor/process/', views.doctor_process, name='doctor_process'),

    path('doctor/all/', views.doctor_all, name='doctor_all'),
    path('doctor/remove_from_pool/<int:appointment_id>/', 
         views.doctor_remove_from_pool, 
         name='doctor_remove_from_pool'),
    path('doctor/accounts/', views.user_accounts, name='user_accounts'),
    path('doctor/accounts/<int:user_id>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
    path('doctor/profiles/', views.patients_info, name='patients_info'),
    path('doctor/profiles/create/', views.create_profile, name='create_profile'),
    path('doctor/profiles/<int:profile_id>/', views.profile_detail, name='profile_detail'),
    path('doctor/profiles/<int:profile_id>/edit/', views.edit_profile, name='edit_profile'),
    path('doctor/profiles/<int:profile_id>/delete/', views.delete_profile, name='delete_profile'),
    path('doctor/profile-records/<int:record_id>/delete/', views.delete_profile_record, name='delete_profile_record'),

    path('doctor/autocomplete/accounts/', views.autocomplete_accounts, name='autocomplete_accounts'),
    path('patient_profile/<int:profile_id>/', views.patient_profile_detail, name='patient_profile_detail'),

    path('doctor/announcement/create/', views.create_announcement, name='create_announcement'),
    path('doctor/announcement/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),
    path('announcements/', views.announcement_list, name='announcement_list'),

    path('doctor/user-accounts/delete/<int:user_id>/', views.delete_user_account, name='delete_user_account'),

    # 数据备份与恢复
    path('doctor/backup/', views.data_backup, name='data_backup'),
    path('doctor/backup/create/', views.create_backup, name='create_backup'),
    path('doctor/backup/download/<str:filename>/', views.download_backup, name='download_backup'),
    path('doctor/backup/restore/', views.restore_backup, name='restore_backup'),
    path('doctor/backup/delete/<str:filename>/', views.delete_backup, name='delete_backup'),
    path('doctor/backup/info/<str:filename>/', views.backup_info, name='backup_info'),
]