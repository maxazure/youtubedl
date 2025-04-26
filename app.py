"""
YouTube Downloader Flask Application - Main Entry Point

这个Flask应用提供一个Web界面，允许用户:
- 输入YouTube视频URL
- 创建下载任务请求
- 提供API接口供客户端使用
- 查看和下载处理后的文件

应用使用SQLite数据库来跟踪下载任务状态。
"""

import os
from flask import Flask
from models import db
from routes import register_blueprints
import config

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # 加载配置
    app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['DOWNLOAD_FOLDER'] = config.DOWNLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    app.config['CHUNK_SIZE'] = config.CHUNK_SIZE
    app.config['STORAGE_LIMIT'] = config.STORAGE_LIMIT
    app.config['TEMP_UPLOAD_FOLDER'] = config.TEMP_UPLOAD_FOLDER
    app.config['SUBTITLES_PER_PAGE'] = config.SUBTITLES_PER_PAGE
    
    # 确保目录存在
    if not os.path.exists(app.config['DOWNLOAD_FOLDER']):
        os.makedirs(app.config['DOWNLOAD_FOLDER'])
    
    if not os.path.exists(app.config['TEMP_UPLOAD_FOLDER']):
        os.makedirs(app.config['TEMP_UPLOAD_FOLDER'])
    
    # 确保instance目录存在 - 这是SQLite数据库存放的地方
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
    
    # 初始化数据库
    db.init_app(app)
    with app.app_context():
        db.create_all()
    
    # 注册蓝图
    register_blueprints(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)