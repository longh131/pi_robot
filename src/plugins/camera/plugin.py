import threading
import time
from typing import Any, Dict
import os
from datetime import datetime
import subprocess

from src.core.base_plugin import BasePlugin
from src.core.state import RobotState

# picamera2 导入（树莓派专用）
try:
    from picamera2 import Picamera2
    import cv2
    import numpy as np
    PICAMERA2_AVAILABLE = True
except ImportError as e:
    PICAMERA2_AVAILABLE = False
    print(f"[CameraPlugin] 缺少依赖库: {e}")
    print("[CameraPlugin] 请运行: sudo apt install libcamera-tools && pip install picamera2 opencv-python")


class CameraPlugin(BasePlugin):
    """摄像头插件 - 使用 picamera2，提供MJPEG视频流、拍照和录像功能"""
    
    def __init__(self):
        super().__init__("camera")
        self._running = False
        self._picamera = None
        self._frame = None
        self._frame_lock = threading.Lock()
        self._capture_thread = None
        self._available = PICAMERA2_AVAILABLE
        
        # 录像相关
        self._recording = False
        self._recording_path = None
        self._audio_recording = False
        self._audio_process = None
        self._audio_path = None
        
        # 媒体目录
        self._media_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'media')
        os.makedirs(self._media_dir, exist_ok=True)

    def on_load(self) -> None:
        """初始化摄像头"""
        print(f"[CameraPlugin] picamera2可用: {self._available}")
        if not self._available:
            print("[CameraPlugin] 依赖未安装，摄像头不可用")
            return
        
        try:
            self._picamera = Picamera2()
            # 配置为预览模式（高帧率）
            preview_config = self._picamera.create_preview_configuration(main={"size": (640, 480)})
            self._picamera.configure(preview_config)
            self._picamera.start()
            time.sleep(2)  # 摄像头预热
            print("[CameraPlugin] 摄像头初始化成功")
        except Exception as e:
            print(f"[CameraPlugin] 摄像头初始化失败: {e}")
            self._picamera = None

    def on_unload(self) -> None:
        """释放资源"""
        self.stop()
        self.stop_recording()
        if self._picamera:
            try:
                self._picamera.stop()
                print("[CameraPlugin] 摄像头已停止")
            except Exception as e:
                print(f"[CameraPlugin] 停止摄像头失败: {e}")
        print("[CameraPlugin] 已卸载")
    
    def start(self) -> None:
        """启动视频捕获线程"""
        print(f"[CameraPlugin] start() - available:{self._available}, running:{self._running}, picamera:{self._picamera}")
        if not self._available or self._running:
            return
        
        if not self._picamera:
            print("[CameraPlugin] 摄像头未初始化")
            return
        
        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )
        self._capture_thread.start()
        print("[CameraPlugin] 视频捕获已启动")

    def stop(self) -> None:
        """停止视频捕获"""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        print("[CameraPlugin] 视频捕获已停止")
    
    def _capture_loop(self) -> None:
        """视频捕获循环"""
        while self._running:
            try:
                # 使用 picamera2 捕获帧
                frame = self._picamera.capture_array()
                if frame is not None:
                    # picamera2 返回的是 RGB 格式，需要转换为 BGR（OpenCV格式）
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    with self._frame_lock:
                        self._frame = frame_bgr.copy()
                time.sleep(0.03)  # ~30fps
            except Exception as e:
                print(f"[CameraPlugin] 捕获异常: {e}")
                time.sleep(0.1)

    def get_frame(self) -> bytes:
        """获取当前帧（JPEG格式）"""
        with self._frame_lock:
            if self._frame is None:
                return b''
            
            # 转换为JPEG格式
            ret, jpeg = cv2.imencode('.jpg', self._frame)
            if ret:
                return jpeg.tobytes()
            return b''

    def get_frame_size(self) -> tuple:
        """获取帧尺寸"""
        return (640, 480)

    def start_recording(self) -> bool:
        """开始录像（包含音频）"""
        if not self._available or not self._picamera:
            return False
        
        if self._recording:
            return False
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._recording_path = os.path.join(self._media_dir, f"video_{timestamp}.mp4")
            h264_path = os.path.join(self._media_dir, f"video_{timestamp}.h264")
            self._audio_path = os.path.join(self._media_dir, f"audio_{timestamp}.wav")
            
            # 切换到视频配置
            video_config = self._picamera.create_video_configuration()
            self._picamera.stop()
            self._picamera.configure(video_config)
            self._picamera.start()
            
            # 启动音频录制
            try:
                from src.common.config_loader import ConfigLoader
                audio_device = ConfigLoader.get("AUDIO_DEVICE", "plughw:2,0")
                audio_rate = ConfigLoader.get("AUDIO_RATE", "44100")
                audio_channels = ConfigLoader.get("AUDIO_CHANNELS", "1")
                
                self._audio_process = subprocess.Popen([
                    'arecord',
                    '-D', audio_device,
                    '-f', 'S16_LE',
                    '-r', audio_rate,
                    '-c', audio_channels,
                    self._audio_path
                ])
                self._audio_recording = True
                print(f"[CameraPlugin] 开始音频录制: {self._audio_path}, 设备: {audio_device}")
            except Exception as e:
                print(f"[CameraPlugin] 音频录制启动失败: {e}")
                self._audio_recording = False
            
            self._recording = True
            
            # 启动视频录制
            self._picamera.start_and_record_video(h264_path)
            print(f"[CameraPlugin] 开始录像: {h264_path}")
            return True
        except Exception as e:
            print(f"[CameraPlugin] 录像启动失败: {e}")
            self._recording = False
            return False

    def stop_recording(self) -> str:
        """停止录像并合并音视频"""
        if not self._recording:
            return "没有在录像"
        
        try:
            # 停止视频录制
            self._picamera.stop_recording()
            
            # 停止音频录制
            if self._audio_recording and self._audio_process:
                self._audio_process.terminate()
                self._audio_process.wait()
                self._audio_recording = False
                print(f"[CameraPlugin] 停止音频录制")
            
            self._recording = False
            
            # 切换回预览模式
            preview_config = self._picamera.create_preview_configuration(main={"size": (640, 480)})
            self._picamera.stop()
            self._picamera.configure(preview_config)
            self._picamera.start()
            
            # 合并音视频
            h264_path = self._recording_path.replace('.mp4', '.h264')
            if os.path.exists(h264_path):
                try:
                    # 使用 ffmpeg 合并音视频
                    if self._audio_recording and os.path.exists(self._audio_path):
                        subprocess.run([
                            'ffmpeg',
                            '-y',
                            '-i', h264_path,
                            '-i', self._audio_path,
                            '-c:v', 'copy',
                            '-c:a', 'aac',
                            '-strict', 'experimental',
                            self._recording_path
                        ], check=True)
                        print(f"[CameraPlugin] 音视频合并完成: {self._recording_path}")
                    else:
                        # 只有视频，直接转换为 mp4
                        subprocess.run([
                            'ffmpeg',
                            '-y',
                            '-i', h264_path,
                            '-c:v', 'copy',
                            self._recording_path
                        ], check=True)
                        print(f"[CameraPlugin] 视频转换完成: {self._recording_path}")
                    
                    # 删除临时文件
                    os.remove(h264_path)
                    if os.path.exists(self._audio_path):
                        os.remove(self._audio_path)
                except Exception as e:
                    print(f"[CameraPlugin] 音视频合并失败: {e}")
                    # 如果合并失败，返回原始 h264 文件
                    self._recording_path = h264_path
            
            print(f"[CameraPlugin] 停止录像: {self._recording_path}")
            filename = os.path.basename(self._recording_path)
            return f"ok:{filename}"
        except Exception as e:
            print(f"[CameraPlugin] 停止录像失败: {e}")
            self._recording = False
            return str(e)

    def take_photo(self) -> str:
        """拍照"""
        if not self._available or not self._picamera:
            return "camera_not_ready"
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'photo_{timestamp}.jpg'
            photo_path = os.path.join(self._media_dir, filename)
            
            # 使用 still 配置拍照
            still_config = self._picamera.create_still_configuration()
            self._picamera.switch_mode_and_capture_file(still_config, photo_path)
            
            print(f"[CameraPlugin] 拍照成功: {photo_path}")
            return f"ok:{filename}"
        except Exception as e:
            print(f"[CameraPlugin] 拍照失败: {e}")
            return str(e)

    def is_recording(self) -> bool:
        """检查是否正在录像"""
        return self._recording

    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "CAMERA_START":
            self.start()
            return {"status": "ok"}
        elif intent == "CAMERA_STOP":
            self.stop()
            return {"status": "ok"}
        elif intent == "CAPTURE":
            result = self.take_photo()
            if result.startswith("ok:"):
                return {"status": "ok", "filename": result[3:]}
            return {"status": "error", "message": result}
        elif intent == "START_RECORDING":
            success = self.start_recording()
            return {"status": "ok" if success else "error"}
        elif intent == "STOP_RECORDING":
            result = self.stop_recording()
            if result.startswith("ok:"):
                return {"status": "ok", "filename": result[3:]}
            return {"status": "error", "message": result}
        elif intent == "IS_RECORDING":
            return {"status": "ok", "recording": self.is_recording()}
        return {"status": "ignored"}

    def get_supported_intents(self) -> list:
        return ["CAMERA_START", "CAMERA_STOP", "CAPTURE", "START_RECORDING", "STOP_RECORDING", "IS_RECORDING"]
    
    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        """状态变化时处理"""
        # 远程控制状态时自动启动摄像头
        if new_state == RobotState.REMOTE:
            self.start()
        # 退出远程状态时停止摄像头（节省资源）
        elif old_state == RobotState.REMOTE and new_state != RobotState.REMOTE:
            self.stop()