"""
Main routes for YouTube Downloader Flask Application
"""

from flask import Blueprint, render_template, request, jsonify, send_from_directory, url_for, abort, current_app
from models import db, SubtitleContent, TaskRequest
from datetime import datetime, UTC
import threading
import os
from utils import process_video_task, has_new_tasks

main = Blueprint('main', __name__)

@main.route('/')
def index():
    """主页，显示下载表单和任务列表"""
    # 获取最近的10个任务
    recent_tasks = SubtitleContent.query.order_by(SubtitleContent.created_at.desc()).limit(10).all()
    return render_template('index.html', recent_tasks=recent_tasks)

@main.route('/submit', methods=['POST'])
def submit_task():
    """提交新的下载任务请求"""
    youtube_url = request.form.get('youtube_url')
    
    if not youtube_url:
        return jsonify({'status': 'error', 'message': '请提供YouTube URL'}), 400
    
    # 创建新任务请求
    new_task_request = TaskRequest(youtube_url=youtube_url)
    db.session.add(new_task_request)
    
    # 创建一个对应的下载任务记录（处于等待状态）
    new_task = SubtitleContent(youtube_url=youtube_url)
    db.session.add(new_task)
    db.session.commit()
    
    # 关联下载任务ID到任务请求
    new_task_request.result_task_id = new_task.id
    db.session.commit()
    
    # 设置全局有新任务标志
    global has_new_tasks
    has_new_tasks = True
    
    return jsonify({
        'status': 'success', 
        'message': '任务已提交',
        'task_id': new_task.id
    })

@main.route('/task/<int:task_id>')
def get_task(task_id):
    """获取任务状态"""
    task = SubtitleContent.query.get_or_404(task_id)
    return jsonify(task.to_dict())

@main.route('/download/<path:filename>')
def download_file(filename):
    """提供文件下载"""
    return send_from_directory(current_app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

@main.route('/subtitles')
def subtitle_list():
    """分页显示字幕列表"""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['SUBTITLES_PER_PAGE']
    
    # 查询已完成的任务（有字幕文件的）
    tasks = SubtitleContent.query.filter(
        SubtitleContent.status == 'completed',
        SubtitleContent.subtitle_filename.isnot(None)
    ).order_by(SubtitleContent.completed_at.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('subtitles/list.html', tasks=tasks)