"""
数据库初始化脚本

运行此脚本来创建或重置数据库表结构
"""

import os
from app import create_app
from models import db
import config

if __name__ == '__main__':
    print("正在初始化数据库...")
    
    # 确保 instance 目录存在
    instance_dir = os.path.join(config.BASE_DIR, 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)
        print(f"已创建目录: {instance_dir}")
    
    app = create_app()
    with app.app_context():
        db.create_all()
    print("数据库初始化完成！")