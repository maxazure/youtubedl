"""
Configuration settings for YouTube Downloader Flask Application
"""

import os

# Base directory of the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Server configuration
PORT = int(os.environ.get('YOUTUBEDL_PORT', 5000))
HOST = os.environ.get('YOUTUBEDL_HOST', '0.0.0.0')
DEBUG = os.environ.get('YOUTUBEDL_DEBUG', 'False').lower() in ('true', '1', 't')

# Database configuration
# 使用绝对路径指向数据库文件
SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "youtube_tasks.db")}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# File storage configuration
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'download')
TEMP_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'temp_uploads')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB
STORAGE_LIMIT = 50 * 1024 * 1024 * 1024  # 50GB

# Pagination settings
SUBTITLES_PER_PAGE = 40