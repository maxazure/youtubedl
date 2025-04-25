"""
YouTube Content Extractor

这个 Python 模块用于从 YouTube 视频中提取音频和字幕内容。它可以自动下载视频音频，获取已有的中文字幕，
或者使用 AI 转录功能生成字幕。

功能特点:
- 从 YouTube 视频提取音频（MP3格式）
- 检查并下载 YouTube 视频的中文字幕（如果有）
- 使用 faster-whisper 进行高质量语音转录（当字幕不可用时）
- 生成带时间戳的文本转录
- 支持 GPU 加速转录（如果可用）

使用方法:

1. 命令行使用:
   python youtube_content_extractor.py
   程序会提示您输入 YouTube 视频链接，然后自动处理并生成音频和字幕文件。

2. 作为模块导入:
   import youtube_content_extractor
   
   # 处理单个视频
   result = youtube_content_extractor.process_youtube_video("https://www.youtube.com/watch?v=视频ID")
   
   # 使用返回的结果
   print(f"视频标题: {result['title']}")
   print(f"视频简介: {result['description']}")
   print(f"音频文件: {result['audio_path']}")
   print(f"字幕文件: {result['subtitle_path']}")

API 参考:

process_youtube_video(youtube_url)
    主要函数，处理 YouTube 视频并提取内容。
    
    参数:
        youtube_url (str): YouTube 视频 URL
    
    返回:
        包含以下键的字典:
        - title: 视频原始标题
        - description: 视频描述/简介
        - audio_path: 下载的音频文件的完整路径（MP3 格式）
        - subtitle_path: 生成的字幕文件的完整路径（文本格式，带时间戳）

其他有用的函数:
- get_video_info(youtube_url): 获取视频的基本信息（标题、描述）
- download_audio(youtube_url, output_path): 仅下载视频的音频部分
- transcribe_audio(audio_path, model_name, use_gpu, num_threads): 使用 faster-whisper 转录音频文件

文件存储位置:
- 音频文件存储在 DOWNLOAD_DIR 目录下 (默认为 './download/')
- 字幕文件也存储在 DOWNLOAD_DIR 目录下
"""

import os
import sys
import subprocess
import yt_dlp
import traceback
import logging
from faster_whisper import WhisperModel
from datetime import datetime

# 配置详细的日志记录器
logger = logging.getLogger('youtube_extractor')
logger.setLevel(logging.DEBUG)

# 创建文件处理器，记录到文件
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extractor_debug.log')
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# 创建控制台处理器，显示在控制台
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 创建格式器并添加到处理器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器到日志记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 设置下载目录常量
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download')

def get_video_title(youtube_url):
    """Extract video title from YouTube URL"""
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        title = info.get('title', 'unknown_video')
        
        # 只保留汉字、英文和数字
        import re
        title = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', title)
        
        # Trim title to 25 characters max
        if len(title) > 25:
            title = title[:25]
        
        # Ensure we have a valid, non-empty filename
        title = title.strip()
        if not title:
            title = "untitled_video"
            
        return title

def get_video_info(youtube_url):
    """Get video information including title and description"""
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        title = info.get('title', 'unknown_video')
        description = info.get('description', '')
        
        return {
            'title': title,
            'description': description,
            'raw_info': info
        }

def check_and_download_subtitles(youtube_url, output_file):
    """
    Check if Chinese subtitles are available for the video and download them if found
    
    Returns:
        bool: True if subtitles were downloaded, False otherwise
    """
    print('检查是否有中文字幕...')
    
    # 确保输出文件包含完整路径
    output_file_path = os.path.join(DOWNLOAD_DIR, output_file)
    
    # 确保下载目录存在
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': False,
        'subtitleslangs': ['zh-CN', 'zh-Hans', 'zh', 'chi', 'zh-Hant', 'zh-TW', 'en'],
        'outtmpl': os.path.splitext(output_file_path)[0],
        'quiet': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        
        # Check if Chinese subtitles are available
        subtitles = info.get('subtitles', {})
        auto_subtitles = info.get('automatic_captions', {})
        
        # Look for various Chinese subtitle formats
        chinese_subtitle_keys = ['zh-CN', 'zh-Hans', 'zh', 'chi']
        
        for key in chinese_subtitle_keys:
            if key in subtitles:
                print(f'找到中文字幕，正在下载...')
                
                # Set options to download the subtitles only
                download_opts = {
                    'skip_download': True,
                    'writesubtitles': True,
                    'subtitleslangs': [key],
                    'subtitlesformat': 'vtt',
                    'outtmpl': os.path.splitext(output_file_path)[0],
                    'quiet': False,
                }
                
                with yt_dlp.YoutubeDL(download_opts) as download_ydl:
                    download_ydl.download([youtube_url])
                
                # Find and rename the subtitle file
                subtitle_path = f"{os.path.splitext(output_file_path)[0]}.{key}.vtt"
                if os.path.exists(subtitle_path):
                    # Convert VTT to plaintext
                    text_content = convert_vtt_to_text(subtitle_path)
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        f.write(text_content)
                    
                    # Remove the VTT file
                    os.remove(subtitle_path)
                    print(f'已保存字幕到：{output_file_path}')
                    return True, output_file_path
        
        print('没有找到可用的中文字幕')
        return False, None

def convert_vtt_to_text(vtt_file):
    """Convert VTT subtitle file to plaintext with timestamps"""
    import re
    
    with open(vtt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove WebVTT header
    if content.startswith('WEBVTT'):
        content = re.sub(r'^WEBVTT.*?\n\n', '', content, flags=re.DOTALL)
    
    # Process subtitle blocks
    lines = content.split('\n')
    result = []
    timestamp_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})')
    
    i = 0
    while i < len(lines):
        match = timestamp_pattern.search(lines[i])
        if match:
            start_time = match.group(1)
            end_time = match.group(2)
            
            # Skip the line with timestamp
            i += 1
            
            # Collect all subsequent text lines until the next timestamp or empty line
            text_lines = []
            while i < len(lines) and not timestamp_pattern.search(lines[i]) and lines[i].strip():
                text_lines.append(lines[i])
                i += 1
            
            # Add the timestamp and text to the result
            text = ' '.join(text_lines).strip()
            if text:
                result.append(f"[{start_time}] - [{end_time}] {text}\n")
        else:
            i += 1
    
    return '\n'.join(result)

def download_audio(youtube_url, output_path='audio.mp3'):
    """Download audio from YouTube URL and save to specified path"""
    # 确保下载目录存在
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    # 提取文件名（不含扩展名）和新的完整路径
    filename = os.path.basename(os.path.splitext(output_path)[0])
    output_path = os.path.join(DOWNLOAD_DIR, filename)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,  # 只提供不带扩展名的路径
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    
    # 返回生成的带扩展名的文件路径
    return f"{output_path}.mp3"

def transcribe_audio(audio_path, model_name='large-v3', use_gpu=True, num_threads=4):
    """
    Transcribe audio using faster-whisper model with improved quality and performance
    
    Parameters:
        audio_path: Path to audio file
        model_name: Model quality ('tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3')
        use_gpu: Whether to use GPU acceleration if available
        num_threads: Number of CPU threads to use when GPU is unavailable
    """
    logger.info(f'开始使用 faster-whisper {model_name} 模型转录音频: {audio_path}')
    
    # Configure device based on availability
    import torch
    compute_type = "float16" if use_gpu and torch.cuda.is_available() else "int8"
    device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
    
    logger.debug(f'转录配置: device={device}, compute_type={compute_type}, model={model_name}')
    
    try:
        if device == "cuda":
            logger.info('使用GPU加速转录')
            print('使用GPU加速转录')
            
            # 记录GPU状态
            try:
                gpu_info = torch.cuda.get_device_properties(0)
                logger.debug(f'GPU信息: {gpu_info.name}, 总内存: {gpu_info.total_memory / 1024 / 1024 / 1024:.2f}GB')
                
                # 记录当前GPU内存使用情况
                reserved = torch.cuda.memory_reserved(0) / 1024 / 1024 / 1024
                allocated = torch.cuda.memory_allocated(0) / 1024 / 1024 / 1024
                logger.debug(f'当前GPU内存使用: 已分配 {allocated:.2f}GB, 已保留 {reserved:.2f}GB')
            except Exception as e:
                logger.warning(f'无法获取GPU信息: {str(e)}')
            
            # Initialize the model with GPU settings
            logger.debug('初始化WhisperModel(GPU模式)...')
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            logger.debug('WhisperModel初始化完成(GPU模式)')
        else:
            logger.info(f'使用CPU转录，线程数: {num_threads}')
            print(f'使用CPU转录，线程数: {num_threads}')
            
            # Initialize the model with CPU settings
            logger.debug('初始化WhisperModel(CPU模式)...')
            model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=num_threads)
            logger.debug('WhisperModel初始化完成(CPU模式)')
        
        # 记录音频文件信息
        try:
            import os
            audio_size = os.path.getsize(audio_path) / (1024 * 1024)
            logger.debug(f'音频文件大小: {audio_size:.2f}MB')
        except Exception as e:
            logger.warning(f'无法获取音频文件信息: {str(e)}')
        
        # Transcribe the audio file
        logger.info('开始转录...')
        logger.debug('调用model.transcribe()...')
        segments, info = model.transcribe(audio_path, beam_size=5)
        logger.debug(f'转录完成，语言检测结果: {info.language}, 语言置信度: {info.language_probability}')
        
        # Collect all segments to form the result
        result = {
            "text": "",
            "segments": []
        }
        
        segment_count = 0
        
        logger.debug('处理转录段落...')
        for segment in segments:
            segment_count += 1
            result["text"] += segment.text + " "
            result["segments"].append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            })
        
        # Trim the final resulting text
        result["text"] = result["text"].strip()
        logger.info(f'转录完成，共生成 {segment_count} 个段落')
        
        # Log a preview of the transcription
        if result["text"]:
            preview_length = min(100, len(result["text"]))
            logger.debug(f'转录文本预览: {result["text"][:preview_length]}...')
        
        return result
        
    except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
        error_msg = str(e)
        logger.error(f"CUDA/运行时错误: {error_msg}")
        logger.error(traceback.format_exc())
        
        # Check if error is CUDA out of memory
        if "CUDA out of memory" in error_msg or "CUDA error" in error_msg:
            logger.warning("GPU内存不足，将切换到CPU模式")
            
            # If we failed with GPU, try again with CPU
            if device == "cuda":
                logger.info(f'重试: 使用CPU转录，线程数: {num_threads}')
                
                try:
                    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=num_threads)
                    logger.debug('CPU模式模型初始化完成，开始转录...')
                    
                    # Transcribe the audio file
                    segments, info = model.transcribe(audio_path, beam_size=5)
                    logger.debug(f'CPU模式转录完成，语言: {info.language}')
                    
                    # Collect all segments to form the result
                    result = {
                        "text": "",
                        "segments": []
                    }
                    
                    for segment in segments:
                        result["text"] += segment.text + " "
                        result["segments"].append({
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text.strip()
                        })
                    
                    # Trim the final resulting text
                    result["text"] = result["text"].strip()
                    logger.info('CPU模式转录成功')
                    
                    return result
                except Exception as cpu_e:
                    logger.error(f"CPU模式转录也失败: {str(cpu_e)}")
                    logger.error(traceback.format_exc())
                    raise
        
        # Re-raise the exception with more info
        raise Exception(f"转录失败: {error_msg}") from e
    
    except Exception as e:
        logger.error(f"转录过程中出现未知错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise Exception(f"转录过程中未知错误: {str(e)}") from e

def save_transcription(result, filename):
    """Save transcription to a text file with timestamps in format [HH:MM:SS.mmm]"""
    # 确保文件名包含完整路径
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    
    # 确保下载目录存在
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        # Process each segment with its timestamp
        for segment in result["segments"]:
            # Format timestamps as [HH:MM:SS.mmm]
            start_time = format_timestamp(segment["start"])
            end_time = format_timestamp(segment["end"])
            
            # Write timestamp range and text
            f.write(f"[{start_time}] - [{end_time}] {segment['text']}\n\n")
    
    print(f'带时间戳的转录已保存到: {filepath}')
    return filepath

def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS.mmm format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds_remainder = seconds % 60
    milliseconds = int((seconds_remainder % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds_remainder):02d}.{milliseconds:03d}"

def process_youtube_video(youtube_url):
    """
    Process a YouTube video: extract info, download audio, generate transcription
    
    Parameters:
        youtube_url: URL of the YouTube video
        
    Returns:
        dict: A dictionary containing:
            - title: Video title
            - description: Video description
            - audio_path: Path to the downloaded audio file
            - subtitle_path: Path to the generated subtitle file
    """
    logger.info(f"开始处理YouTube视频: {youtube_url}")
    
    # 确保下载目录存在
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        logger.debug(f"创建下载目录: {DOWNLOAD_DIR}")
    
    try:
        # Get video info first
        logger.info("正在获取视频信息...")
        video_info = get_video_info(youtube_url)
        raw_title = video_info['title']
        description = video_info['description']
        logger.info(f"获取到视频信息 - 标题: {raw_title}")
        logger.debug(f"视频描述: {description[:100]}..." if len(description) > 100 else description)
        
        # Get sanitized video title for filenames
        video_title = get_video_title(youtube_url)
        subtitle_file = f"{video_title}.txt"
        logger.debug(f"生成的文件名: {video_title}")
        
        result = {
            'title': raw_title,
            'description': description,
            'audio_path': None,
            'subtitle_path': None
        }
        
        # First check if Chinese subtitles are available
        logger.info("检查是否有中文字幕...")
        subtitles_downloaded, subtitle_path = check_and_download_subtitles(youtube_url, subtitle_file)
        if subtitles_downloaded:
            logger.info(f"成功下载中文字幕到: {subtitle_path}")
            result['subtitle_path'] = subtitle_path
            
            # 如果没有下载音频，也需要下载音频文件
            logger.info("下载音频文件...")
            audio_file = f"{video_title}"
            audio_path = download_audio(youtube_url, audio_file)
            logger.info(f"音频下载完成: {audio_path}")
            result['audio_path'] = audio_path
            
            return result

        # No subtitles found, proceed with audio download and transcription
        logger.info("没有找到中文字幕，将进行音频下载和转录")
        
        # 使用视频标题作为音频文件名
        audio_file = f"{video_title}"
        logger.info(f"开始下载音频: {youtube_url} -> {audio_file}")
        audio_path = download_audio(youtube_url, audio_file)
        logger.info(f"音频下载完成: {audio_path}")
        result['audio_path'] = audio_path

        logger.info("开始转录过程...")
        try:
            # 首先尝试使用大模型
            logger.info("尝试使用 large-v3 模型转录")
            try:
                transcription_result = transcribe_audio(audio_path, model_name='large-v3')
                logger.info("large-v3 模型转录成功")
            except Exception as e1:
                logger.warning(f"large-v3 模型转录失败: {str(e1)}")
                logger.info("尝试使用 medium 模型转录")
                
                try:
                    transcription_result = transcribe_audio(audio_path, model_name='medium')
                    logger.info("medium 模型转录成功")
                except Exception as e2:
                    logger.warning(f"medium 模型转录失败: {str(e2)}")
                    logger.info("尝试使用 small 模型转录")
                    
                    try:
                        transcription_result = transcribe_audio(audio_path, model_name='small')
                        logger.info("small 模型转录成功")
                    except Exception as e3:
                        logger.warning(f"small 模型转录失败: {str(e3)}")
                        logger.info("最后尝试使用 base 模型转录")
                        
                        # 最后尝试最小的模型
                        transcription_result = transcribe_audio(audio_path, model_name='base')
                        logger.info("base 模型转录成功")
            
            logger.info("转录完成，保存转录结果...")
            
            # Save transcription to file
            subtitle_path = save_transcription(transcription_result, subtitle_file)
            logger.info(f"转录结果已保存到: {subtitle_path}")
            result['subtitle_path'] = subtitle_path
            
            # Print a preview of the transcription
            preview_length = min(150, len(transcription_result["text"]))
            preview_text = transcription_result["text"][:preview_length] + "..." if len(transcription_result["text"]) > preview_length else transcription_result["text"]
            logger.info(f"转录文本预览: {preview_text}")
            
            return result
            
        except Exception as e:
            error_message = f"转录过程中出现错误: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            
            # 创建一个简单的字幕文件，即使转录失败也能返回一些结果
            logger.info("生成简单的错误信息字幕文件...")
            simple_subtitle_path = os.path.join(DOWNLOAD_DIR, subtitle_file)
            with open(simple_subtitle_path, 'w', encoding='utf-8') as f:
                f.write(f"[自动生成] 该视频转录失败，但音频已成功下载。\n")
                f.write(f"错误信息: {str(e)}\n")
                f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"视频标题: {raw_title}\n")
                
            result['subtitle_path'] = simple_subtitle_path
            logger.info(f"生成简单字幕文件: {simple_subtitle_path}")
            
            return result
            
    except Exception as e:
        # 捕获整个处理过程中的任何错误
        logger.error(f"处理视频时发生意外错误: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 重新抛出异常以便上层函数处理
        raise Exception(f"处理YouTube视频失败: {str(e)}")

def main():
    youtube_url = input('请输入YouTube视频链接: ').strip()
    result = process_youtube_video(youtube_url)
    
    print("\n处理结果:")
    print(f"标题: {result['title']}")
    print(f"音频文件: {result['audio_path']}")
    print(f"字幕文件: {result['subtitle_path']}")

if __name__ == '__main__':
    main()
