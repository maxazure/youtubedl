#!/bin/bash

# 确保脚本以root权限运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请使用sudo运行此脚本"
    exit 1
fi

# 设置变量
APP_DIR="/opt/youtubedl"
SERVICE_NAME="youtubedl"
SERVICE_USER="youtubedl"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_DIR="${APP_DIR}/venv"

# 默认端口设置
DEFAULT_PORT=5000
APP_PORT=${1:-$DEFAULT_PORT}

echo "=== 正在安装YouTube下载服务 (端口: $APP_PORT) ==="

# 创建服务用户（如果不存在）
if ! id -u $SERVICE_USER > /dev/null 2>&1; then
    echo "创建服务用户: $SERVICE_USER"
    useradd --system --shell /bin/false --home-dir $APP_DIR $SERVICE_USER
fi

# 创建应用目录
echo "创建应用目录: $APP_DIR"
mkdir -p $APP_DIR
mkdir -p $APP_DIR/download
mkdir -p $APP_DIR/temp
mkdir -p $APP_DIR/temp_uploads
mkdir -p $APP_DIR/instance

# 复制应用文件
echo "复制应用文件到: $APP_DIR"
cp -r ./* $APP_DIR/

# 设置权限
echo "设置目录权限"
chown -R $SERVICE_USER:$SERVICE_USER $APP_DIR

# 安装依赖
echo "安装系统依赖"
apt-get update
apt-get install -y python3 python3-pip python3-venv ffmpeg

# 创建Python虚拟环境
echo "创建Python虚拟环境"
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# 安装Python依赖
echo "安装Python依赖"
pip install --upgrade pip
pip install -r $APP_DIR/requirements.txt

# 初始化数据库
echo "初始化数据库"
cd $APP_DIR
python init_db.py

# 创建systemd服务文件
echo "创建systemd服务文件: $SERVICE_FILE"
cat > $SERVICE_FILE << EOF
[Unit]
Description=YouTube Content Extractor Service
After=network.target

[Service]
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python $APP_DIR/app.py
Restart=always
RestartSec=5
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="YOUTUBEDL_PORT=$APP_PORT"
Environment="YOUTUBEDL_DEBUG=False"

[Install]
WantedBy=multi-user.target
EOF

# 重载systemd配置
echo "重载systemd配置"
systemctl daemon-reload

# 启用并启动服务
echo "启用并启动服务"
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo "服务状态:"
systemctl status $SERVICE_NAME

echo "=== 安装完成 ==="
echo "服务已安装并启动，您可以使用以下命令管理服务:"
echo "  systemctl start $SERVICE_NAME    # 启动服务"
echo "  systemctl stop $SERVICE_NAME     # 停止服务"
echo "  systemctl restart $SERVICE_NAME  # 重启服务"
echo "  systemctl status $SERVICE_NAME   # 查看服务状态"
echo "  journalctl -u $SERVICE_NAME      # 查看服务日志"
echo ""
echo "应用安装在: $APP_DIR"
echo "服务使用用户: $SERVICE_USER"
echo "服务运行在端口: $APP_PORT"