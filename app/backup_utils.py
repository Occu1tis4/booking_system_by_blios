import json
import zipfile
import tempfile
import os
import django  # 添加django导入
from django.core import serializers
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import datetime
import pytz  # 添加pytz时区库
from .models import (
    CustomUser, Appointment, Profile, ProfileRecord, 
    DailyAppointmentCreation, Announcement, DoctorProcessingPool
)

class DataBackupManager:
    """数据备份管理器"""
    
    @staticmethod
    def get_backup_directory():
        """获取备份目录"""
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir
    
    @staticmethod
    def create_backup():
        """
        创建数据备份
        返回备份文件的路径
        """
        backup_dir = DataBackupManager.get_backup_directory()
        
        # 创建临时目录存储JSON文件
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_files = {}
            
            try:
                # 1. 备份用户数据（排除超级用户/医师账号）
                users = CustomUser.objects.filter(is_superuser=False, is_staff=False)
                users_data = serializers.serialize('json', users, use_natural_foreign_keys=True)
                users_file = os.path.join(temp_dir, 'users.json')
                with open(users_file, 'w', encoding='utf-8') as f:
                    f.write(users_data)
                backup_files['users'] = users_file
                print(f"备份用户数据: {users.count()} 条记录")
                
                # 2. 备份预约数据
                appointments = Appointment.objects.all()
                appointments_data = serializers.serialize('json', appointments, use_natural_foreign_keys=True)
                appointments_file = os.path.join(temp_dir, 'appointments.json')
                with open(appointments_file, 'w', encoding='utf-8') as f:
                    f.write(appointments_data)
                backup_files['appointments'] = appointments_file
                print(f"备份预约数据: {appointments.count()} 条记录")
                
                # 3. 备份档案数据
                profiles = Profile.objects.all()
                profiles_data = serializers.serialize('json', profiles, use_natural_foreign_keys=True)
                profiles_file = os.path.join(temp_dir, 'profiles.json')
                with open(profiles_file, 'w', encoding='utf-8') as f:
                    f.write(profiles_data)
                backup_files['profiles'] = profiles_file
                print(f"备份档案数据: {profiles.count()} 条记录")
                
                # 4. 备份档案记录数据
                profile_records = ProfileRecord.objects.all()
                profile_records_data = serializers.serialize('json', profile_records, use_natural_foreign_keys=True)
                profile_records_file = os.path.join(temp_dir, 'profile_records.json')
                with open(profile_records_file, 'w', encoding='utf-8') as f:
                    f.write(profile_records_data)
                backup_files['profile_records'] = profile_records_file
                print(f"备份档案记录数据: {profile_records.count()} 条记录")
                
                # 5. 备份每日创建记录
                daily_creations = DailyAppointmentCreation.objects.all()
                daily_creations_data = serializers.serialize('json', daily_creations, use_natural_foreign_keys=True)
                daily_creations_file = os.path.join(temp_dir, 'daily_creations.json')
                with open(daily_creations_file, 'w', encoding='utf-8') as f:
                    f.write(daily_creations_data)
                backup_files['daily_creations'] = daily_creations_file
                print(f"备份每日创建记录: {daily_creations.count()} 条记录")
                
                # 6. 备份公告数据
                announcements = Announcement.objects.all()
                announcements_data = serializers.serialize('json', announcements, use_natural_foreign_keys=True)
                announcements_file = os.path.join(temp_dir, 'announcements.json')
                with open(announcements_file, 'w', encoding='utf-8') as f:
                    f.write(announcements_data)
                backup_files['announcements'] = announcements_file
                print(f"备份公告数据: {announcements.count()} 条记录")
                
                # 7. 备份处理池数据
                processing_pools = DoctorProcessingPool.objects.all()
                processing_pools_data = serializers.serialize('json', processing_pools, use_natural_foreign_keys=True)
                processing_pools_file = os.path.join(temp_dir, 'processing_pools.json')
                with open(processing_pools_file, 'w', encoding='utf-8') as f:
                    f.write(processing_pools_data)
                backup_files['processing_pools'] = processing_pools_file
                print(f"备份处理池数据: {processing_pools.count()} 条记录")
                
                # 获取北京时间
                beijing_tz = pytz.timezone('Asia/Shanghai')
                beijing_time = datetime.now(beijing_tz)
                
                # 创建备份信息文件
                backup_info = {
                    'backup_date': beijing_time.isoformat(),
                    'django_version': django.get_version(),  # 使用django.get_version()获取版本
                    'models_backed_up': list(backup_files.keys()),
                    'record_counts': {
                        'users': users.count(),
                        'appointments': appointments.count(),
                        'profiles': profiles.count(),
                        'profile_records': profile_records.count(),
                        'daily_creations': daily_creations.count(),
                        'announcements': announcements.count(),
                        'processing_pools': processing_pools.count(),
                    },
                    'timezone': 'Asia/Shanghai'
                }
                
                backup_info_file = os.path.join(temp_dir, 'backup_info.json')
                with open(backup_info_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_info, f, ensure_ascii=False, indent=2)
                
                # 创建ZIP文件 - 使用北京时间
                timestamp = beijing_time.strftime('%Y%m%d_%H%M%S')
                zip_filename = f'backup_{timestamp}.zip'
                zip_path = os.path.join(backup_dir, zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # 添加所有JSON文件到ZIP
                    zipf.write(backup_info_file, 'backup_info.json')
                    zipf.write(users_file, 'users.json')
                    zipf.write(appointments_file, 'appointments.json')
                    zipf.write(profiles_file, 'profiles.json')
                    zipf.write(profile_records_file, 'profile_records.json')
                    zipf.write(daily_creations_file, 'daily_creations.json')
                    zipf.write(announcements_file, 'announcements.json')
                    zipf.write(processing_pools_file, 'processing_pools.json')
                
                print(f"备份完成，文件保存在: {zip_path}")
                return zip_path
                
            except Exception as e:
                print(f"备份过程中出错: {str(e)}")
                raise
    
    @staticmethod
    @transaction.atomic
    def restore_backup(backup_file):
        """
        恢复数据备份
        
        Args:
            backup_file: 上传的备份文件路径或文件对象
        
        Returns:
            dict: 恢复统计信息
        """
        restore_stats = {
            'users': 0,
            'appointments': 0,
            'profiles': 0,
            'profile_records': 0,
            'daily_creations': 0,
            'announcements': 0,
            'processing_pools': 0,
            'errors': []
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 解压备份文件
                with zipfile.ZipFile(backup_file, 'r') as zipf:
                    zipf.extractall(temp_dir)
                
                # 读取备份信息
                backup_info_path = os.path.join(temp_dir, 'backup_info.json')
                if not os.path.exists(backup_info_path):
                    raise ValueError("备份文件无效：缺少备份信息文件")
                
                with open(backup_info_path, 'r', encoding='utf-8') as f:
                    backup_info = json.load(f)
                
                # 解析备份时间
                backup_date_str = backup_info.get('backup_date', '')
                if backup_date_str:
                    try:
                        # 尝试解析ISO格式时间
                        from dateutil import parser
                        backup_date = parser.isoparse(backup_date_str)
                        print(f"开始恢复备份，备份时间: {backup_date}")
                    except:
                        print(f"开始恢复备份，备份时间: {backup_date_str}")
                else:
                    print("开始恢复备份，备份时间未知")
                
                # 1. 恢复用户数据
                users_path = os.path.join(temp_dir, 'users.json')
                if os.path.exists(users_path):
                    with open(users_path, 'r', encoding='utf-8') as f:
                        users_data = f.read()
                    
                    # 使用Django的反序列化
                    for obj in serializers.deserialize('json', users_data):
                        try:
                            # 检查是否已存在相同邮箱的用户
                            existing_user = CustomUser.objects.filter(email=obj.object.email).first()
                            if existing_user:
                                # 跳过超级用户账号
                                if existing_user.is_superuser:
                                    print(f"跳过医师账号: {obj.object.email}")
                                    continue
                                # 更新现有用户（包括密码）
                                for field, value in obj.object.__dict__.items():
                                    if field not in ['id', '_state']:  # 只排除id和_state
                                        setattr(existing_user, field, value)
                                existing_user.save()
                            else:
                                obj.save()
                            restore_stats['users'] += 1
                        except Exception as e:
                            restore_stats['errors'].append(f"用户恢复错误 (邮箱: {obj.object.email}): {str(e)}")
                
                # 2. 恢复档案数据
                profiles_path = os.path.join(temp_dir, 'profiles.json')
                if os.path.exists(profiles_path):
                    with open(profiles_path, 'r', encoding='utf-8') as f:
                        profiles_data = f.read()
                    
                    for obj in serializers.deserialize('json', profiles_data):
                        try:
                            # 检查关联用户是否存在
                            if obj.object.account:
                                try:
                                    # 确保用户对象存在
                                    obj.object.account = CustomUser.objects.get(id=obj.object.account.id)
                                except CustomUser.DoesNotExist:
                                    # 用户不存在，设为None
                                    obj.object.account = None
                                    print(f"警告：档案 {obj.object.name} 的关联用户不存在，已解除关联")
                            
                            obj.save()
                            restore_stats['profiles'] += 1
                        except Exception as e:
                            restore_stats['errors'].append(f"档案恢复错误 (ID: {obj.object.id}): {str(e)}")
                
                # 3. 恢复档案记录数据
                profile_records_path = os.path.join(temp_dir, 'profile_records.json')
                if os.path.exists(profile_records_path):
                    with open(profile_records_path, 'r', encoding='utf-8') as f:
                        profile_records_data = f.read()
                    
                    for obj in serializers.deserialize('json', profile_records_data):
                        try:
                            # 检查关联档案是否存在
                            try:
                                obj.object.profile = Profile.objects.get(id=obj.object.profile.id)
                            except Profile.DoesNotExist:
                                restore_stats['errors'].append(f"档案记录恢复错误: 关联档案不存在 (ID: {obj.object.profile.id})")
                                continue
                            
                            # 检查创建者是否存在
                            try:
                                obj.object.created_by = CustomUser.objects.get(id=obj.object.created_by.id)
                            except CustomUser.DoesNotExist:
                                restore_stats['errors'].append(f"档案记录恢复错误: 创建者用户不存在 (ID: {obj.object.created_by.id})")
                                continue
                            
                            obj.save()
                            restore_stats['profile_records'] += 1
                        except Exception as e:
                            restore_stats['errors'].append(f"档案记录恢复错误 (ID: {obj.object.id}): {str(e)}")
                
                # 4. 恢复预约数据
                appointments_path = os.path.join(temp_dir, 'appointments.json')
                if os.path.exists(appointments_path):
                    with open(appointments_path, 'r', encoding='utf-8') as f:
                        appointments_data = f.read()
                    
                    for obj in serializers.deserialize('json', appointments_data):
                        try:
                            # 检查关联用户是否存在
                            try:
                                obj.object.guest = CustomUser.objects.get(id=obj.object.guest.id)
                            except CustomUser.DoesNotExist:
                                restore_stats['errors'].append(f"预约恢复错误: 关联用户不存在 (ID: {obj.object.guest.id})")
                                continue
                            
                            obj.save()
                            restore_stats['appointments'] += 1
                        except Exception as e:
                            restore_stats['errors'].append(f"预约恢复错误 (ID: {obj.object.id}): {str(e)}")
                
                # 5. 恢复每日创建记录
                daily_creations_path = os.path.join(temp_dir, 'daily_creations.json')
                if os.path.exists(daily_creations_path):
                    with open(daily_creations_path, 'r', encoding='utf-8') as f:
                        daily_creations_data = f.read()
                    
                    for obj in serializers.deserialize('json', daily_creations_data):
                        try:
                            # 检查关联用户是否存在
                            try:
                                obj.object.user = CustomUser.objects.get(id=obj.object.user.id)
                            except CustomUser.DoesNotExist:
                                restore_stats['errors'].append(f"每日创建记录恢复错误: 关联用户不存在 (ID: {obj.object.user.id})")
                                continue
                            
                            obj.save()
                            restore_stats['daily_creations'] += 1
                        except Exception as e:
                            restore_stats['errors'].append(f"每日创建记录恢复错误 (ID: {obj.object.id}): {str(e)}")
                
                # 6. 恢复公告数据
                announcements_path = os.path.join(temp_dir, 'announcements.json')
                if os.path.exists(announcements_path):
                    with open(announcements_path, 'r', encoding='utf-8') as f:
                        announcements_data = f.read()
                    
                    for obj in serializers.deserialize('json', announcements_data):
                        try:
                            # 检查创建者是否存在
                            if obj.object.created_by:
                                try:
                                    obj.object.created_by = CustomUser.objects.get(id=obj.object.created_by.id)
                                except CustomUser.DoesNotExist:
                                    # 创建者不存在，设为None
                                    obj.object.created_by = None
                                    print(f"警告：公告 {obj.object.title} 的创建者不存在，已设为空")
                            
                            obj.save()
                            restore_stats['announcements'] += 1
                        except Exception as e:
                            restore_stats['errors'].append(f"公告恢复错误 (ID: {obj.object.id}): {str(e)}")
                
                # 7. 恢复处理池数据
                processing_pools_path = os.path.join(temp_dir, 'processing_pools.json')
                if os.path.exists(processing_pools_path):
                    with open(processing_pools_path, 'r', encoding='utf-8') as f:
                        processing_pools_data = f.read()
                    
                    for obj in serializers.deserialize('json', processing_pools_data):
                        try:
                            # 检查关联预约是否存在
                            try:
                                obj.object.appointment = Appointment.objects.get(id=obj.object.appointment.id)
                            except Appointment.DoesNotExist:
                                restore_stats['errors'].append(f"处理池恢复错误: 关联预约不存在 (ID: {obj.object.appointment.id})")
                                continue
                            
                            obj.save()
                            restore_stats['processing_pools'] += 1
                        except Exception as e:
                            restore_stats['errors'].append(f"处理池恢复错误 (ID: {obj.object.id}): {str(e)}")
                
                print(f"恢复完成: {restore_stats}")
                return restore_stats
                
            except Exception as e:
                print(f"恢复过程中出错: {str(e)}")
                restore_stats['errors'].append(f"恢复过程错误: {str(e)}")
                raise
    
    @staticmethod
    def list_backups():
        """列出所有备份文件"""
        backup_dir = DataBackupManager.get_backup_directory()
        backups = []
        
        for filename in os.listdir(backup_dir):
            if filename.endswith('.zip'):
                filepath = os.path.join(backup_dir, filename)
                stat = os.stat(filepath)
                backups.append({
                    'filename': filename,
                    'path': filepath,
                    'size': stat.st_size,
                    'created_time': datetime.fromtimestamp(stat.st_ctime),
                    'modified_time': datetime.fromtimestamp(stat.st_mtime),
                })
        
        # 按修改时间倒序排序
        backups.sort(key=lambda x: x['modified_time'], reverse=True)
        return backups
    
    @staticmethod
    def delete_backup(filename):
        """删除指定的备份文件"""
        backup_dir = DataBackupManager.get_backup_directory()
        filepath = os.path.join(backup_dir, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    
    @staticmethod
    def get_database_info():
        """获取数据库统计信息"""
        info = {
            'users': CustomUser.objects.filter(is_superuser=False, is_staff=False).count(),
            'appointments': Appointment.objects.count(),
            'profiles': Profile.objects.count(),
            'profile_records': ProfileRecord.objects.count(),
            'daily_creations': DailyAppointmentCreation.objects.count(),
            'announcements': Announcement.objects.count(),
            'processing_pools': DoctorProcessingPool.objects.count(),
        }
        return info