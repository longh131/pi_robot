#!/bin/bash

echo "开始安装系统依赖..."
sudo apt-get update

sudo apt-get install -y espeak libespeak1 #安装底层语音库
sudo apt-get install libportaudio2  # 系统级音频库
sudo apt-get install mpv -y  # 处理流式音频播放
sudo apt-get install libcamera-tools -y  # 相机工具
sudo apt-get install python3-libcamera -y

sudo apt install alsa-utils # 安装音频录制工具
sudo apt install ffmpeg # 安装视频处理工具

# 安装 smbus 库 用于 I2C 通信 电量监控
# 安装 i2c-tools 工具 用于 I2C 通信 电量监控
sudo apt-get install python3-smbus i2c-tools

# 安装 FRP 服务端 远端控制
wget https://github.com/fatedier/frp/releases/download/v0.51.0/frp_0.51.0_linux_arm64.tar.gz
tar -xzvf frp_0.51.0_linux_arm64.tar.gz
cd frp_0.51.0_linux_arm64
./frpc -c frpc.ini

# 安装 pigpio 服务 用于 GPIO 控制
sudo pigpiod
sudo systemctl enable pigpiod

echo "开始安装 Python 依赖..."
pip install -r requirements.txt

echo "环境部署完成！"
