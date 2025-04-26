#!/bin/bash

# 确保脚本以root权限运行
if [ "$(id -u)" -ne 0 ]; then
    echo "请使用sudo运行此脚本"
    exit 1
fi

# 设置变量
SERVICE_NAME="youtubedl"
APP_DIR="/opt/youtubedl"
SERVICE_USER="youtubedl"

echo "=== 正在卸载YouTube下载服务 ==="

# 停止并禁用服务
echo "停止并禁用服务"
systemctl stop $SERVICE_NAME
systemctl disable $SERVICE_NAME

# 删除服务文件
echo "删除服务文件"
rm -f /etc/systemd/system/${SERVICE_NAME}.service

# 重载systemd配置
echo "重载systemd配置"
systemctl daemon-reload
systemctl reset-failed

# 询问是否删除应用文件
read -p "是否删除应用文件和数据? (y/n): " DELETE_FILES
if [ "$DELETE_FILES" = "y" ] || [ "$DELETE_FILES" = "Y" ]; then
    echo "删除应用文件: $APP_DIR"
    rm -rf $APP_DIR
    
    # 询问是否删除服务用户
    read -p "是否删除服务用户 $SERVICE_USER? (y/n): " DELETE_USER
    if [ "$DELETE_USER" = "y" ] || [ "$DELETE_USER" = "Y" ]; then
        echo "删除服务用户: $SERVICE_USER"
        userdel $SERVICE_USER
    fi
else
    echo "保留应用文件: $APP_DIR"
fi

echo "=== 卸载完成 ==="