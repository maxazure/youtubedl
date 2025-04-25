"""
YouTube 下载任务客户端处理程序

这个程序在客户端运行，负责:
1. 定期检查服务器是否有新的下载任务
2. 认领并处理任务（下载音频和生成字幕）
3. 将结果上传回服务器

该客户端需要访问GPU来运行whisper进行音频转录。
"""

import os
import sys
import time
import json
import uuid
import socket
import requests
import argparse
from datetime import datetime
import youtube_content_extractor
import logging
import shutil
import tempfile

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('task_loader.log')
    ]
)
logger = logging.getLogger('task_loader')

class YouTubeTaskLoader:
    def __init__(self, server_url, check_interval=10, download_dir=None):
        """
        初始化下载任务处理程序
        
        参数:
            server_url: API服务器地址，例如 http://localhost:5000
            check_interval: 检查新任务的间隔时间（秒）
            download_dir: 下载文件的保存目录（仅用于暂存，将在任务完成后清理）
        """
        self.server_url = server_url.rstrip('/')
        self.check_interval = check_interval
        
        # 生成唯一的客户端ID
        hostname = socket.gethostname()
        self.client_id = f"{hostname}-{uuid.uuid4()}"
        
        # 设置临时下载目录 - 默认在程序同级目录下的temp文件夹
        if download_dir:
            self.temp_dir = os.path.join(download_dir, 'temp')
        else:
            # 使用程序同级目录作为默认临时目录，而不是系统临时目录
            self.temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
        
        # 确保临时目录存在
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
        
        logger.info(f"任务处理程序已启动 - 客户端ID: {self.client_id}")
        logger.info(f"服务器地址: {self.server_url}")
        logger.info(f"临时目录: {self.temp_dir}")
    
    def cleanup(self):
        """清理临时文件夹"""
        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"已清理临时目录: {self.temp_dir}")
            # 重新创建临时目录
            os.makedirs(self.temp_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"清理临时目录时出错: {str(e)}")
    
    def check_new_tasks(self):
        """检查服务器是否有新的任务"""
        try:
            response = requests.get(
                f"{self.server_url}/api/tasks/new",
                params={"client_id": self.client_id}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('has_new_tasks', False)
            else:
                logger.error(f"检查新任务失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"检查新任务出错: {str(e)}")
            return False
    
    def get_pending_tasks(self):
        """获取待处理的任务列表"""
        try:
            response = requests.get(
                f"{self.server_url}/api/tasks/pending",
                params={"client_id": self.client_id}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('tasks', [])
            else:
                logger.error(f"获取待处理任务失败: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"获取待处理任务出错: {str(e)}")
            return []
    
    def claim_task(self, task_id):
        """认领任务"""
        try:
            response = requests.post(
                f"{self.server_url}/api/tasks/claim",
                json={"task_id": task_id, "client_id": self.client_id}
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(f"任务认领成功: {task_id}")
                return True, data.get('task', {})
            else:
                logger.error(f"任务认领失败: {response.status_code} - {response.text}")
                return False, {}
        except Exception as e:
            logger.error(f"任务认领出错: {str(e)}")
            return False, {}
    
    def upload_file_in_chunks(self, file_path):
        """以分块方式上传大文件"""
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            logger.info(f"开始分块上传文件: {file_name} (大小: {file_size / (1024*1024):.2f} MB)")
            
            # 初始化上传
            init_response = requests.post(
                f"{self.server_url}/api/file/init_upload",
                json={
                    "filename": file_name,
                    "file_size": file_size,
                    "file_type": os.path.splitext(file_name)[1][1:]  # 文件类型（不含点）
                }
            )
            
            if init_response.status_code != 200:
                logger.error(f"初始化文件上传失败: {init_response.status_code} - {init_response.text}")
                return False, None
            
            init_data = init_response.json()
            upload_id = init_data.get('upload_id')
            chunk_size = init_data.get('chunk_size')
            total_chunks = init_data.get('total_chunks')
            
            logger.info(f"文件上传初始化成功，上传ID: {upload_id}, 共分 {total_chunks} 块")
            
            # 分块上传
            with open(file_path, 'rb') as f:
                for chunk_index in range(total_chunks):
                    chunk_data = f.read(chunk_size)
                    
                    # 准备上传表单
                    files = {'file': (f'chunk_{chunk_index}', chunk_data)}
                    data = {
                        'upload_id': upload_id,
                        'chunk_index': chunk_index
                    }
                    
                    # 上传分块
                    chunk_response = requests.post(
                        f"{self.server_url}/api/file/upload_chunk",
                        files=files,
                        data=data
                    )
                    
                    if chunk_response.status_code != 200:
                        logger.error(f"上传分块 {chunk_index} 失败: {chunk_response.status_code} - {chunk_response.text}")
                        return False, None
                    
                    chunk_data = chunk_response.json()
                    if chunk_data.get('complete', False):
                        logger.info(f"文件上传完成: {file_name}")
                        return True, file_name
                    
                    # 进度日志
                    if chunk_index % 5 == 0 or chunk_index == total_chunks - 1:
                        logger.info(f"上传进度: {chunk_index + 1}/{total_chunks} ({(chunk_index + 1) / total_chunks * 100:.1f}%)")
            
            # 如果没有在上面返回，可能是出了问题
            logger.error("文件上传未完成，但所有块已处理")
            return False, None
            
        except Exception as e:
            logger.error(f"分块上传文件出错: {str(e)}")
            return False, None
    
    def upload_file(self, file_path):
        """上传文件到服务器，对于大文件使用分块上传"""
        # 检查文件大小，大于10MB的文件使用分块上传
        file_size = os.path.getsize(file_path)
        if file_size > 10 * 1024 * 1024:  # 10MB
            return self.upload_file_in_chunks(file_path)
        
        # 小文件使用普通上传
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                response = requests.post(
                    f"{self.server_url}/api/file/upload",
                    files=files
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"文件上传成功: {file_path}")
                    return True, data.get('filename')
                else:
                    logger.error(f"文件上传失败: {response.status_code} - {response.text}")
                    return False, None
        except Exception as e:
            logger.error(f"文件上传出错: {str(e)}")
            return False, None
    
    def report_task_completion(self, task_id, result):
        """上报任务完成状态"""
        try:
            # 上传音频文件
            audio_upload_success, audio_filename = self.upload_file(result['audio_path'])
            
            # 上传字幕文件
            subtitle_upload_success, subtitle_filename = self.upload_file(result['subtitle_path'])
            
            # 报告任务完成状态
            data = {
                "task_id": task_id,
                "client_id": self.client_id,
                "title": result['title'],
                "description": result['description'],
                "error_message": None
            }
            
            if audio_upload_success:
                data["audio_filename"] = audio_filename
            
            if subtitle_upload_success:
                data["subtitle_filename"] = subtitle_filename
            
            response = requests.post(
                f"{self.server_url}/api/tasks/complete",
                json=data
            )
            
            if response.status_code == 200:
                logger.info(f"任务完成状态上报成功: {task_id}")
                return True
            else:
                logger.error(f"任务完成状态上报失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"任务完成状态上报出错: {str(e)}")
            return False
    
    def report_task_error(self, task_id, error_message):
        """上报任务失败状态"""
        try:
            data = {
                "task_id": task_id,
                "client_id": self.client_id,
                "error_message": error_message
            }
            
            response = requests.post(
                f"{self.server_url}/api/tasks/complete",
                json=data
            )
            
            if response.status_code == 200:
                logger.info(f"任务失败状态上报成功: {task_id}")
                return True
            else:
                logger.error(f"任务失败状态上报失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"任务失败状态上报出错: {str(e)}")
            return False
    
    def process_task(self, task):
        """处理单个任务"""
        task_id = task['id']
        youtube_url = task['youtube_url']
        
        logger.info(f"开始处理任务 {task_id}: {youtube_url}")
        
        try:
            # 认领任务
            claim_success, claimed_task = self.claim_task(task_id)
            if not claim_success:
                logger.error(f"认领任务失败，跳过处理: {task_id}")
                return False
            
            # 修改DOWNLOAD_DIR环境变量，让youtube_content_extractor使用临时目录
            original_download_dir = youtube_content_extractor.DOWNLOAD_DIR
            youtube_content_extractor.DOWNLOAD_DIR = self.temp_dir
            
            # 为处理设置超时机制
            import threading
            import traceback
            
            # 结果容器和错误标志
            result_container = {'result': None, 'error': None}
            processing_complete = threading.Event()
            
            def process_with_timeout():
                try:
                    # 调用 youtube_content_extractor 处理下载和转录
                    result_container['result'] = youtube_content_extractor.process_youtube_video(youtube_url)
                    processing_complete.set()
                except Exception as e:
                    result_container['error'] = f"处理异常: {str(e)}\n{traceback.format_exc()}"
                    processing_complete.set()
            
            # 创建处理线程
            processing_thread = threading.Thread(target=process_with_timeout)
            processing_thread.daemon = True
            
            try:
                logger.info(f"开始下载和转录: {youtube_url}")
                processing_thread.start()
                
                # 等待处理完成，设置超时时间（例如30分钟）
                timeout_seconds = 30 * 60  # 30分钟超时
                if not processing_complete.wait(timeout_seconds):
                    raise TimeoutError(f"处理超时（{timeout_seconds}秒）")
                
                # 检查是否有错误
                if result_container['error']:
                    raise Exception(result_container['error'])
                
                # 获取处理结果
                result = result_container['result']
                
                if not result:
                    raise Exception("处理返回空结果")
                
                if not result.get('audio_path') or not result.get('subtitle_path'):
                    # 检查是否至少有音频文件
                    if result.get('audio_path') and not result.get('subtitle_path'):
                        logger.warning("没有生成字幕文件，但音频文件已下载。尝试手动生成简单字幕文件。")
                        
                        # 创建一个简单的字幕文件
                        audio_path = result.get('audio_path')
                        simple_subtitle_path = os.path.splitext(audio_path)[0] + ".txt"
                        
                        with open(simple_subtitle_path, 'w', encoding='utf-8') as f:
                            f.write(f"[自动生成] 该视频的转录失败，但音频已成功下载。\n")
                            f.write(f"视频标题: {result.get('title', '未知')}\n")
                            f.write(f"下载时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        
                        result['subtitle_path'] = simple_subtitle_path
                    else:
                        raise Exception("处理结果不完整，缺少音频或字幕文件路径")
            finally:
                # 恢复原始下载目录设置
                youtube_content_extractor.DOWNLOAD_DIR = original_download_dir
                
            # 获取当前日期，格式为 YYYYMMDD
            current_date = datetime.now().strftime('%Y%m%d')
            
            # 重命名文件，添加任务ID和日期前缀
            new_audio_filename = f"{task_id}_{current_date}{os.path.splitext(os.path.basename(result['audio_path']))[1]}"
            new_subtitle_filename = f"{task_id}_{current_date}{os.path.splitext(os.path.basename(result['subtitle_path']))[1]}"
            
            # 创建新的临时文件路径
            new_audio_path = os.path.join(self.temp_dir, new_audio_filename)
            new_subtitle_path = os.path.join(self.temp_dir, new_subtitle_filename)
            
            # 重命名文件
            shutil.copy(result['audio_path'], new_audio_path)
            shutil.copy(result['subtitle_path'], new_subtitle_path)
            
            # 更新结果中的文件路径
            result['audio_path'] = new_audio_path
            result['subtitle_path'] = new_subtitle_path
            
            # 上报任务完成
            completion_success = self.report_task_completion(task_id, result)
            
            # 清理临时文件
            self.cleanup()
            
            if completion_success:
                logger.info(f"任务处理完成: {task_id}")
                return True
            else:
                logger.error(f"任务完成状态上报失败: {task_id}")
                return False
                
        except TimeoutError as e:
            error_message = f"任务处理超时: {str(e)}"
            logger.error(error_message)
            self.report_task_error(task_id, error_message)
            
            # 检查是否有部分结果可用（例如仅音频）
            audio_files = [f for f in os.listdir(self.temp_dir) if f.endswith('.mp3')]
            if audio_files:
                try:
                    # 找到与当前任务相关的音频文件
                    audio_file = audio_files[0]  # 假设只有一个音频文件
                    audio_path = os.path.join(self.temp_dir, audio_file)
                    
                    # 创建一个简单的字幕文件
                    simple_subtitle_path = os.path.splitext(audio_path)[0] + ".txt"
                    with open(simple_subtitle_path, 'w', encoding='utf-8') as f:
                        f.write(f"[自动生成] 该视频转录过程超时，但音频已成功下载。\n")
                        f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    
                    # 获取当前日期，格式为 YYYYMMDD
                    current_date = datetime.now().strftime('%Y%m%d')
                    
                    # 重命名文件，添加任务ID和日期前缀
                    new_audio_filename = f"{task_id}_{current_date}.mp3"
                    new_subtitle_filename = f"{task_id}_{current_date}.txt"
                    
                    new_audio_path = os.path.join(self.temp_dir, new_audio_filename)
                    new_subtitle_path = os.path.join(self.temp_dir, new_subtitle_filename)
                    
                    # 重命名文件
                    shutil.copy(audio_path, new_audio_path)
                    shutil.copy(simple_subtitle_path, new_subtitle_path)
                    
                    # 构建部分结果
                    partial_result = {
                        'title': f"[部分结果] 任务 {task_id} - {datetime.now().strftime('%Y-%m-%d')}",
                        'description': "转录过程超时，仅提供音频文件。",
                        'audio_path': new_audio_path,
                        'subtitle_path': new_subtitle_path
                    }
                    
                    # 上报部分完成
                    logger.info(f"转录失败但上传部分结果(音频): {task_id}")
                    self.report_task_completion(task_id, partial_result)
                except Exception as partial_error:
                    logger.error(f"尝试保存部分结果时出错: {str(partial_error)}")
            
            # 清理临时文件
            self.cleanup()
            return False
            
        except Exception as e:
            error_message = f"处理任务出错: {str(e)}"
            logger.error(error_message)
            # 记录详细堆栈跟踪
            logger.error(traceback.format_exc())
            self.report_task_error(task_id, error_message)
            
            # 检查是否有部分结果可用（例如仅音频）
            try:
                audio_files = [f for f in os.listdir(self.temp_dir) if f.endswith('.mp3')]
                if audio_files:
                    # 找到与当前任务相关的音频文件
                    audio_file = audio_files[0]  # 假设只有一个音频文件
                    audio_path = os.path.join(self.temp_dir, audio_file)
                    
                    # 创建一个简单的字幕文件
                    simple_subtitle_path = os.path.splitext(audio_path)[0] + ".txt"
                    with open(simple_subtitle_path, 'w', encoding='utf-8') as f:
                        f.write(f"[自动生成] 该视频转录失败，但音频已成功下载。\n")
                        f.write(f"错误信息: {str(e)}\n")
                        f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    
                    # 获取当前日期，格式为 YYYYMMDD
                    current_date = datetime.now().strftime('%Y%m%d')
                    
                    # 重命名文件，添加任务ID和日期前缀
                    new_audio_filename = f"{task_id}_{current_date}.mp3"
                    new_subtitle_filename = f"{task_id}_{current_date}.txt"
                    
                    new_audio_path = os.path.join(self.temp_dir, new_audio_filename)
                    new_subtitle_path = os.path.join(self.temp_dir, new_subtitle_filename)
                    
                    # 重命名文件
                    shutil.copy(audio_path, new_audio_path)
                    shutil.copy(simple_subtitle_path, new_subtitle_path)
                    
                    # 构建部分结果
                    partial_result = {
                        'title': f"[部分结果] 任务 {task_id} - {datetime.now().strftime('%Y-%m-%d')}",
                        'description': "转录过程出错，仅提供音频文件。",
                        'audio_path': new_audio_path,
                        'subtitle_path': new_subtitle_path
                    }
                    
                    # 上报部分完成
                    logger.info(f"转录失败但上传部分结果(音频): {task_id}")
                    self.report_task_completion(task_id, partial_result)
            except Exception as partial_error:
                logger.error(f"尝试保存部分结果时出错: {str(partial_error)}")
            
            # 清理临时文件
            self.cleanup()
            return False
    
    def run(self):
        """主循环，持续检查并处理任务"""
        logger.info("开始监控新任务...")
        
        while True:
            try:
                # 检查是否有新任务
                has_new_tasks = self.check_new_tasks()
                
                if has_new_tasks:
                    logger.info("检测到新任务，正在获取详情...")
                    pending_tasks = self.get_pending_tasks()
                    
                    if pending_tasks:
                        for task in pending_tasks:
                            self.process_task(task)
                    else:
                        logger.info("没有找到待处理的任务")
                
                # 等待下一次检查
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("收到终止信号，正在停止...")
                self.cleanup()
                break
            except Exception as e:
                logger.error(f"主循环出错: {str(e)}")
                # 短暂等待后继续
                time.sleep(5)

def main():
    parser = argparse.ArgumentParser(description='YouTube下载任务客户端处理程序')
    parser.add_argument('--server', type=str, default='http://localhost:5000',
                        help='服务器地址 (默认: http://localhost:5000)')
    parser.add_argument('--interval', type=int, default=10,
                        help='检查新任务的间隔时间（秒）(默认: 10)')
    parser.add_argument('--temp-dir', type=str, default=None,
                        help='临时文件的保存目录 (默认: 程序同级目录下的temp文件夹)')
    
    args = parser.parse_args()
    
    task_loader = YouTubeTaskLoader(
        server_url=args.server,
        check_interval=args.interval,
        download_dir=args.temp_dir
    )
    
    task_loader.run()

if __name__ == '__main__':
    main()