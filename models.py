"""
Database models for YouTube Downloader Flask Application
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, UTC
from flask import url_for

db = SQLAlchemy()

class SubtitleContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    youtube_url = db.Column(db.String(255), nullable=False)
    audio_filename = db.Column(db.String(255))
    subtitle_filename = db.Column(db.String(255))
    status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed, expired
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'youtube_url': self.youtube_url,
            'audio_filename': self.audio_filename,
            'subtitle_filename': self.subtitle_filename,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else None,
            'error_message': self.error_message,
            'title': self.title,
            'description': self.description,
            'audio_url': url_for('main.download_file', filename=self.audio_filename) if self.audio_filename else None,
            'subtitle_url': url_for('main.download_file', filename=self.subtitle_filename) if self.subtitle_filename else None
        }

class TaskRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    youtube_url = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    processed_at = db.Column(db.DateTime)
    client_id = db.Column(db.String(100))  # 记录哪个客户端处理了这个任务
    result_task_id = db.Column(db.Integer, db.ForeignKey('subtitle_content.id'), nullable=True)  # 关联到处理结果

    def to_dict(self):
        return {
            'id': self.id,
            'youtube_url': self.youtube_url,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'processed_at': self.processed_at.strftime('%Y-%m-%d %H:%M:%S') if self.processed_at else None,
            'client_id': self.client_id,
            'result_task_id': self.result_task_id
        }