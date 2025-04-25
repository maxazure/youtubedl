"""
API routes for YouTube Downloader Flask Application
"""

from flask import Blueprint, request, jsonify, current_app
from models import db, SubtitleContent, TaskRequest
from datetime import datetime, UTC, timedelta
import os
import json
import math
import uuid
import shutil
from werkzeug.utils import secure_filename
from utils import has_new_tasks, check_storage_limit

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/tasks/new', methods=['GET'])
def check_new_tasks():
    """检查是否有新任务，供客户端调用"""
    global has_new_tasks
    
    client_id = request.args.get('client_id')
    if not client_id:
        return jsonify({'error': '缺少client_id参数'}), 400
    
    # 检查是否有未处理完成的任务
    active_tasks = TaskRequest.query.filter(
        TaskRequest.status.in_(['pending', 'processing'])
    ).count()
    
    # 如果有活跃的任务，确保标志为True
    if active_tasks > 0:
        has_new_tasks = True
    
    return jsonify({
        'has_new_tasks': has_new_tasks
    })

@api.route('/tasks/pending', methods=['GET'])
def get_pending_tasks():
    """获取待处理的任务列表，供客户端调用"""
    global has_new_tasks
    
    client_id = request.args.get('client_id')
    if not client_id:
        return jsonify({'error': '缺少client_id参数'}), 400
    
    # 获取所有待处理的任务请求
    pending_tasks = TaskRequest.query.filter_by(status='pending').order_by(TaskRequest.created_at).all()
    
    # 如果没有待处理任务，则重置全局标志
    if not pending_tasks:
        has_new_tasks = False
    
    return jsonify({
        'tasks': [task.to_dict() for task in pending_tasks]
    })

@api.route('/tasks/add', methods=['POST'])
def add_task():
    """通过API添加新的下载任务"""
    global has_new_tasks
    
    youtube_url = request.json.get('youtube_url')
    
    if not youtube_url:
        return jsonify({'error': '缺少必要参数'}), 400
    
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
    has_new_tasks = True
    
    return jsonify({
        'status': 'success',
        'message': '任务已通过API添加',
        'task_id': new_task.id
    })

@api.route('/tasks/claim', methods=['POST'])
def claim_task():
    """客户端认领任务"""
    task_id = request.json.get('task_id')
    client_id = request.json.get('client_id')
    
    if not task_id or not client_id:
        return jsonify({'error': '缺少必要参数'}), 400
    
    task = TaskRequest.query.get_or_404(task_id)
    
    # 确保任务仍然是待处理状态
    if task.status != 'pending':
        return jsonify({'error': '任务已被其他客户端认领或已完成'}), 409
    
    # 更新任务状态
    task.status = 'processing'
    task.client_id = client_id
    
    # 更新下载任务状态
    if task.result_task_id:
        download_task = SubtitleContent.query.get(task.result_task_id)
        if download_task:
            download_task.status = 'processing'
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': '任务认领成功',
        'task': task.to_dict()
    })

@api.route('/tasks/complete', methods=['POST'])
def complete_task():
    """客户端完成任务上报"""
    task_id = request.json.get('task_id')
    client_id = request.json.get('client_id')
    title = request.json.get('title', '')
    description = request.json.get('description', '')
    audio_filename = request.json.get('audio_filename')
    subtitle_filename = request.json.get('subtitle_filename')
    error_message = request.json.get('error_message')
    
    if not task_id or not client_id:
        return jsonify({'error': '缺少必要参数'}), 400
    
    task = TaskRequest.query.get_or_404(task_id)
    
    # 确保是正确的客户端上报
    if task.client_id != client_id:
        return jsonify({'error': '无权限更新此任务'}), 403
    
    # 更新任务状态
    task.status = 'completed' if not error_message else 'failed'
    task.processed_at = datetime.now(UTC)
    
    # 更新下载任务记录
    if task.result_task_id:
        download_task = SubtitleContent.query.get(task.result_task_id)
        if download_task:
            download_task.status = 'completed' if not error_message else 'failed'
            download_task.completed_at = datetime.now(UTC)
            download_task.title = title
            download_task.description = description
            download_task.audio_filename = audio_filename
            download_task.subtitle_filename = subtitle_filename
            download_task.error_message = error_message
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': '任务完成状态更新成功'
    })

@api.route('/file/upload', methods=['POST'])
def upload_file():
    """客户端上传处理后的文件"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件被上传'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
    # 保存文件
    filename = file.filename
    file.save(os.path.join(current_app.config['DOWNLOAD_FOLDER'], filename))
    
    return jsonify({
        'status': 'success',
        'message': '文件上传成功',
        'filename': filename
    })

# 文件分块上传相关API
@api.route('/file/init_upload', methods=['POST'])
def init_upload():
    """初始化一个分块上传会话"""
    filename = request.json.get('filename')
    file_size = request.json.get('file_size')
    file_type = request.json.get('file_type')
    
    if not filename or not file_size:
        return jsonify({'error': '缺少必要参数'}), 400
    
    # 检查存储空间是否足够
    if check_storage_limit(current_app, int(file_size)):
        return jsonify({'error': '服务器存储空间不足'}), 507
    
    # 安全处理文件名
    safe_filename = secure_filename(filename)
    
    # 创建一个唯一的上传ID
    upload_id = str(uuid.uuid4())
    
    # 为这个上传创建一个临时目录
    upload_dir = os.path.join(current_app.config['TEMP_UPLOAD_FOLDER'], upload_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存上传会话信息
    session_info = {
        'filename': safe_filename,
        'file_size': file_size,
        'file_type': file_type,
        'upload_id': upload_id,
        'chunks_received': 0,
        'total_chunks': math.ceil(int(file_size) / current_app.config['CHUNK_SIZE']),
        'created_at': datetime.now(UTC).isoformat()
    }
    
    with open(os.path.join(upload_dir, 'session.json'), 'w') as f:
        json.dump(session_info, f)
    
    return jsonify({
        'status': 'success',
        'upload_id': upload_id,
        'chunk_size': current_app.config['CHUNK_SIZE'],
        'total_chunks': session_info['total_chunks']
    })

@api.route('/file/upload_chunk', methods=['POST'])
def upload_chunk():
    """上传一个文件分块"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件块被上传'}), 400
    
    upload_id = request.form.get('upload_id')
    chunk_index = request.form.get('chunk_index')
    
    if not upload_id or chunk_index is None:
        return jsonify({'error': '缺少必要参数'}), 400
    
    chunk_index = int(chunk_index)
    
    # 检查上传会话是否存在
    upload_dir = os.path.join(current_app.config['TEMP_UPLOAD_FOLDER'], upload_id)
    session_file = os.path.join(upload_dir, 'session.json')
    
    if not os.path.exists(session_file):
        return jsonify({'error': '上传会话不存在或已过期'}), 404
    
    # 读取会话信息
    with open(session_file, 'r') as f:
        session_info = json.load(f)
    
    # 保存分块
    chunk = request.files['file']
    chunk_file = os.path.join(upload_dir, f'chunk_{chunk_index}')
    chunk.save(chunk_file)
    
    # 更新会话信息
    session_info['chunks_received'] += 1
    
    with open(session_file, 'w') as f:
        json.dump(session_info, f)
    
    # 检查是否所有分块都已接收
    if session_info['chunks_received'] >= session_info['total_chunks']:
        # 合并所有分块
        try:
            final_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], session_info['filename'])
            with open(final_path, 'wb') as outfile:
                for i in range(session_info['total_chunks']):
                    chunk_file = os.path.join(upload_dir, f'chunk_{i}')
                    if os.path.exists(chunk_file):
                        with open(chunk_file, 'rb') as infile:
                            outfile.write(infile.read())
            
            # 清理临时文件
            shutil.rmtree(upload_dir)
            
            return jsonify({
                'status': 'success',
                'message': '文件上传完成',
                'filename': session_info['filename'],
                'complete': True
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'合并文件时出错: {str(e)}'
            }), 500
    
    return jsonify({
        'status': 'success',
        'message': f'分块 {chunk_index} 上传成功',
        'chunks_received': session_info['chunks_received'],
        'total_chunks': session_info['total_chunks'],
        'complete': False
    })

@api.route('/file/cleanup_uploads', methods=['POST'])
def cleanup_uploads():
    """清理过期的上传会话"""
    # 设置过期时间（24小时）
    expiration_time = datetime.now(UTC) - timedelta(hours=24)
    
    cleaned_count = 0
    
    # 查找所有上传会话目录
    for upload_id in os.listdir(current_app.config['TEMP_UPLOAD_FOLDER']):
        upload_dir = os.path.join(current_app.config['TEMP_UPLOAD_FOLDER'], upload_id)
        session_file = os.path.join(upload_dir, 'session.json')
        
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r') as f:
                    session_info = json.load(f)
                
                created_at = datetime.fromisoformat(session_info['created_at'])
                
                # 如果会话已过期，则清理
                if created_at < expiration_time:
                    shutil.rmtree(upload_dir)
                    cleaned_count += 1
            except:
                # 如果无法读取会话文件，也清理
                shutil.rmtree(upload_dir)
                cleaned_count += 1
    
    return jsonify({
        'status': 'success',
        'message': f'已清理 {cleaned_count} 个过期上传会话'
    })

@api.route('/file/manage_storage', methods=['POST'])
def manage_storage():
    """管理存储空间，删除过期文件"""
    # 设置文件过期时间（30天）
    expiration_time = datetime.now(UTC) - timedelta(days=30)
    
    deleted_count = 0
    freed_space = 0
    
    # 查找已完成且过期的任务
    expired_tasks = SubtitleContent.query.filter(
        SubtitleContent.status == 'completed',
        SubtitleContent.completed_at < expiration_time
    ).all()
    
    for task in expired_tasks:
        # 删除关联的音频文件
        if task.audio_filename:
            file_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], task.audio_filename)
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                freed_space += file_size
                deleted_count += 1
        
        # 删除关联的字幕文件
        if task.subtitle_filename:
            file_path = os.path.join(current_app.config['DOWNLOAD_FOLDER'], task.subtitle_filename)
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                freed_space += file_size
                deleted_count += 1
        
        # 更新任务状态
        task.audio_filename = None
        task.subtitle_filename = None
        task.status = 'expired'
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': f'已删除 {deleted_count} 个过期文件，释放 {freed_space / (1024*1024):.2f} MB 空间'
    })