from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from app import views as app_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', 
         auth_views.LoginView.as_view(
             template_name='app/login.html',
             redirect_authenticated_user=True,
             next_page='login_redirect'  # 添加这行
         ), 
         name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/accounts/login/'), name='logout'),
    path('', include('app.urls')),
]