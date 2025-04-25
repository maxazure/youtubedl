"""
Utility functions for YouTube Downloader Flask Application
"""

import os
import json
import math
import shutil
from datetime import datetime, UTC, timedelta
from werkzeug.utils import secure_filename

# Global variable for task notification
has_new_tasks = True

def process_video_task(app, task_id, youtube_url):
    """处理视频下载任务的后台函数"""
    # 导入在这里进行，避免循环导入
    import youtube_content_extractor
    from models import db, SubtitleContent
    
    # 创建应用上下文，以便在线程中访问数据库
    with app.app_context():
        try:
            # 更新任务状态为处理中
            task = SubtitleContent.query.get(task_id)
            task.status = 'processing'
            db.session.commit()
            
            # 调用处理函数
            result = youtube_content_extractor.process_youtube_video(youtube_url)
            
            # 更新任务信息，只存储文件名而不是完整路径
            task.audio_filename = os.path.basename(result['audio_path'])
            task.subtitle_filename = os.path.basename(result['subtitle_path'])
            task.status = 'completed'
            task.completed_at = datetime.now(UTC)
            db.session.commit()
            
        except Exception as e:
            # 处理失败，更新错误信息
            task = SubtitleContent.query.get(task_id)
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.now(UTC)
            db.session.commit()

def check_storage_limit(app, additional_size=0):
    """
    检查存储空间是否超过限制
    
    参数:
        additional_size: 即将添加的文件大小
        
    返回:
        bool: 如果添加新文件后会超过存储限制，则返回True
    """
    # 获取当前存储目录大小
    current_size = get_directory_size(app.config['DOWNLOAD_FOLDER'])
    
    # 如果添加新文件会超出限制，返回True
    return (current_size + additional_size) > app.config['STORAGE_LIMIT']

def get_directory_size(path):
    """计算目录的总大小（字节）"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size