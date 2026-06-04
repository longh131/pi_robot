# src/plugins/remote/plugin.py
import threading
import json
import os
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.core.base_plugin import BasePlugin
from src.core.state import RobotState

try:
    from flask import Flask, render_template, jsonify, request, g, Response
    from jose import JWTError, jwt
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("[RemotePlugin] flask 或 python-jose 未安装")


# JWT 配置
JWT_SECRET_KEY = "pi_robot_remote_control_secret_key_2026"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

# 认证文件路径
AUTH_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'remote_auth.json')

# HTML 页面已分离到 static/index.html


class RemotePlugin(BasePlugin):
    """远程控制插件 - Flask + HTTP API（简化版）"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        super().__init__("remote")
        self.host = host
        self.port = port
        self._app = None
        self._server_thread = None
        self._running = False
        self._available = FLASK_AVAILABLE
        # 心跳相关
        self._last_heartbeat_time = 0
        self._heartbeat_check_thread = None
        self._heartbeat_timeout = 10  # 心跳超时时间（秒）
    
    def _load_auth_data(self) -> Dict[str, Any]:
        """加载认证文件"""
        try:
            with open(AUTH_FILE_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[RemotePlugin] 加载认证文件失败: {e}")
            return {}
    
    def _verify_password(self, plain_password: str, password_hash: str) -> bool:
        """验证密码哈希（SHA256）"""
        computed_hash = hashlib.sha256(plain_password.encode()).hexdigest()
        return computed_hash == password_hash
    
    def _create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """创建JWT token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    
    def _verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            username = payload.get("sub")
            if username is None:
                return None
            return payload
        except JWTError:
            return None
    
    def on_load(self) -> None:
        """加载插件，创建 Flask 应用"""
        if not self._available:
            print("[RemotePlugin] Flask 未安装，远程控制不可用")
            return
        
        template_folder = os.path.join(os.path.dirname(__file__), 'static')
        self._app = Flask(__name__, template_folder=template_folder)
        
        # 关闭 Werkzeug 请求日志
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        self._setup_routes()
        print(f"[RemotePlugin] Web 服务器已创建 (http://{self.host}:{self.port})")
    
    def _setup_routes(self) -> None:
        """设置 Flask 路由"""
        
        @self._app.route('/')
        def index():
            return render_template('index.html')
        
        @self._app.route('/api/login', methods=['POST'])
        def api_login():
            """用户登录 - JWT认证"""
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return jsonify({"error": "用户名或密码为空"}), 400
            
            auth_data = self._load_auth_data()
            user = auth_data.get(username)
            
            if not user or not self._verify_password(password, user.get('password_hash', '')):
                return jsonify({"error": "用户名或密码错误"}), 401
            
            access_token = self._create_access_token(data={"sub": username, "role": user.get('role')})
            return jsonify({"access_token": access_token, "token_type": "bearer", "username": username})
        
        @self._app.route('/api/config', methods=['GET'])
        def api_config():
            """获取机器人配置（无需认证）"""
            from src.common.config_loader import ConfigLoader
            motor_speed = float(ConfigLoader.get("MOTOR_SPEED", "0.5")) * 100
            return jsonify({"motor_speed": int(motor_speed)})
        
        @self._app.route('/api/media', methods=['GET'])
        def api_media_list():
            """获取媒体文件列表（需要JWT认证）"""
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({"error": "未授权访问"}), 401
            
            token = auth_header.split(' ')[1]
            payload = self._verify_token(token)
            if not payload:
                return jsonify({"error": "无效或过期的token"}), 401
            
            import os
            media_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'media')
            music_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'music')
            
            videos = []
            photos = []
            music = []
            
            if os.path.exists(media_dir):
                for filename in os.listdir(media_dir):
                    filepath = os.path.join(media_dir, filename)
                    if os.path.isfile(filepath):
                        if filename.endswith('.h264') or filename.endswith('.mp4'):
                            videos.append(filename)
                        elif filename.endswith('.jpg') or filename.endswith('.png'):
                            photos.append(filename)
                        elif filename.endswith('.mp3') or filename.endswith('.wav'):
                            music.append(filename)
            
            if os.path.exists(music_dir):
                for filename in os.listdir(music_dir):
                    filepath = os.path.join(music_dir, filename)
                    if os.path.isfile(filepath) and (filename.endswith('.mp3') or filename.endswith('.wav')):
                        if not music.__contains__(filename):
                            music.append(filename)
            
            return jsonify({
                "videos": sorted(videos, reverse=True),
                "photos": sorted(photos, reverse=True),
                "music": sorted(music, reverse=True)
            })
        
        @self._app.route('/api/media/file')
        def api_media_file():
            """获取媒体文件内容（需要JWT认证）"""
            token = request.args.get('token')
            filename = request.args.get('filename')
            
            if not token:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
            
            if not token:
                return jsonify({"error": "未授权访问"}), 401
            
            payload = self._verify_token(token)
            if not payload:
                return jsonify({"error": "无效或过期的token"}), 401
            
            if not filename:
                return jsonify({"error": "文件名不能为空"}), 400
            
            import os
            media_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'media')
            music_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'music')
            
            filepath = os.path.join(media_dir, filename)
            if not os.path.exists(filepath):
                filepath = os.path.join(music_dir, filename)
            
            if not os.path.exists(filepath):
                return jsonify({"error": "文件不存在"}), 404
            
            if not os.path.isfile(filepath):
                return jsonify({"error": "不是有效文件"}), 400
            
            # 根据文件扩展名设置正确的 Content-Type
            if filename.endswith('.jpg') or filename.endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif filename.endswith('.png'):
                content_type = 'image/png'
            elif filename.endswith('.mp3'):
                content_type = 'audio/mpeg'
            elif filename.endswith('.wav'):
                content_type = 'audio/wav'
            elif filename.endswith('.mp4'):
                content_type = 'video/mp4'
            elif filename.endswith('.h264'):
                content_type = 'video/h264'
            else:
                content_type = 'application/octet-stream'
            
            with open(filepath, 'rb') as f:
                content = f.read()
            
            return Response(content, content_type=content_type)
        
        @self._app.route('/api/logout', methods=['POST'])
        def api_logout():
            """用户退出 - 断开远程控制并返回IDLE状态"""
            if self._brain:
                self._brain.remote_disconnect()
            return jsonify({"status": "ok", "message": "已退出登录"})
        
        @self._app.route('/api/connect', methods=['POST'])
        def api_connect():
            """尝试进入远程控制状态（需要JWT认证）"""
            # 验证JWT token
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({"error": "未授权访问"}), 401
            
            token = auth_header.split(' ')[1]
            payload = self._verify_token(token)
            if not payload:
                return jsonify({"error": "无效或过期的token"}), 401
            
            if not self._brain:
                return jsonify({"error": "Brain 未就绪"}), 500
            
            success = self._brain.remote_connect()
            if success:
                # 初始化心跳时间为当前时间，给前端缓冲时间发送第一个心跳
                self._last_heartbeat_time = time.time()
                return jsonify({"status": "ok", "state": self._brain.get_state()})
            else:
                return jsonify({"error": "机器人正在工作中，请稍后再试"}), 403
        
        @self._app.route('/api/disconnect', methods=['POST'])
        def api_disconnect():
            """断开远程控制（需要JWT认证）"""
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({"error": "未授权访问"}), 401
            
            token = auth_header.split(' ')[1]
            payload = self._verify_token(token)
            if not payload:
                return jsonify({"error": "无效或过期的token"}), 401
            
            if self._brain:
                self._brain.remote_disconnect()
            return jsonify({"status": "ok"})
        
        @self._app.route('/api/state', methods=['GET'])
        def api_state():
            """获取当前状态（公开接口）"""
            if not self._brain:
                return jsonify({"state": "unknown"})
            return jsonify({"state": self._brain.get_state()})
        
        @self._app.route('/api/command', methods=['POST'])
        def api_command():
            """执行命令（需要JWT认证）"""
            # 验证JWT token
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({"error": "未授权访问"}), 401
            
            token = auth_header.split(' ')[1]
            payload = self._verify_token(token)
            if not payload:
                return jsonify({"error": "无效或过期的token"}), 401
            
            if not self._brain:
                return jsonify({"error": "Brain 未就绪"}), 500
            
            # 只有 REMOTE 状态才执行命令
            if self._brain.get_state() != "remote":
                return jsonify({"error": "非远程控制状态"}), 403
            
            data = request.get_json()
            command = data.get('command', '')
            params = data.get('params', {})
            
            print(f"[RemotePlugin] 收到命令: {command}, 参数: {params}")
            
            command_map = {
                'forward': 'MOTOR_FORWARD',
                'backward': 'MOTOR_BACKWARD',
                'left': 'MOTOR_LEFT',
                'right': 'MOTOR_RIGHT',
                'stop': 'MOTOR_STOP',
                'speed_up': 'MOTOR_SPEED_UP',
                'speed_down': 'MOTOR_SPEED_DOWN',
                'set_speed': 'MOTOR_SET_SPEED',
                'get_status': 'MOTOR_GET_STATUS',
                'start_record': 'START_RECORDING',
                'stop_record': 'STOP_RECORDING',
                'is_recording': 'IS_RECORDING',
                'take_photo': 'CAPTURE',
            }
            
            if command in command_map:
                intent = command_map[command]
                print(f"[RemotePlugin] 意图: {intent}, 参数: {params}")
                print(f"[RemotePlugin] self._brain: {self._brain}")
                print(f"[RemotePlugin] Brain插件列表: {list(self._brain.plugins.keys()) if self._brain else 'None'}")
                result = self._brain._route_intent(intent, params)
                print(f"[RemotePlugin] 路由结果: {result}")
                if result and result.get('status') == 'ok':
                    return jsonify(result)
                else:
                    return jsonify({"status": "error", "message": "命令执行失败"})
            else:
                return jsonify({"status": "error", "message": f"未知命令: {command}"})
        
        @self._app.route('/api/heartbeat', methods=['POST'])
        def api_heartbeat():
            """心跳接口（需要JWT认证）"""
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({"error": "未授权访问"}), 401
            
            token = auth_header.split(' ')[1]
            payload = self._verify_token(token)
            if not payload:
                return jsonify({"error": "无效或过期的token"}), 401
            
            # 更新最后心跳时间
            self._last_heartbeat_time = time.time()
            return jsonify({"status": "ok"})
        
        @self._app.route('/api/video_feed')
        def api_video_feed():
            """MJPEG视频流接口（需要JWT认证）"""
            # 从URL参数或Authorization header获取token
            token = request.args.get('token')
            if not token:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
            
            if not token:
                return jsonify({"error": "未授权访问"}), 401
            
            payload = self._verify_token(token)
            if not payload:
                return jsonify({"error": "无效或过期的token"}), 401
            
            def generate():
                """生成MJPEG视频流（使用全局camera插件）"""
                while self._running:
                    # 获取全局camera插件
                    camera = self._brain.get_plugin("camera") if self._brain else None
                    
                    if camera:
                        frame = camera.get_frame()
                        if frame:
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    
                    time.sleep(0.03)  # ~30fps
            
            return Response(
                generate(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
    
    def _start_heartbeat_check(self) -> None:
        """启动心跳检查线程"""
        if self._heartbeat_check_thread and self._heartbeat_check_thread.is_alive():
            return
        
        self._heartbeat_check_thread = threading.Thread(
            target=self._heartbeat_check_loop,
            daemon=True
        )
        self._heartbeat_check_thread.start()
    
    def _heartbeat_check_loop(self) -> None:
        """心跳检查循环"""
        while self._running:
            try:
                # 检查心跳超时（仅在REMOTE状态下）
                if self._brain and self._brain.get_state() == "remote":
                    current_time = time.time()
                    if current_time - self._last_heartbeat_time > self._heartbeat_timeout:
                        print(f"[RemotePlugin] 心跳超时，自动断开远程控制")
                        self._brain.remote_disconnect()
                time.sleep(5)  # 每5秒检查一次
            except Exception as e:
                print(f"[RemotePlugin] 心跳检查异常: {e}")
                time.sleep(5)
    
    def on_unload(self) -> None:
        """卸载插件"""
        self.stop()
        print("[RemotePlugin] 已卸载")
    
    def start(self) -> None:
        """启动 Web 服务器"""
        if not self._available or self._running:
            return
        
        self._running = True
        self._server_thread = threading.Thread(
            target=self._run_server,
            daemon=True
        )
        self._server_thread.start()
        # 启动心跳检查线程
        self._start_heartbeat_check()
        print(f"[RemotePlugin] Web 服务器已启动: http://{self.host}:{self.port}")
    
    def stop(self) -> None:
        """停止 Web 服务器"""
        self._running = False
        
        # 停止 Flask 服务器
        if hasattr(self, '_server') and self._server:
            try:
                self._server.shutdown()
                print("[RemotePlugin] Flask 服务器已关闭")
            except Exception as e:
                print(f"[RemotePlugin] 关闭服务器失败: {e}")
        
        # 等待服务器线程结束
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=2)
            print("[RemotePlugin] 服务器线程已退出")
        
        print("[RemotePlugin] Web 服务器已停止")
    
    def _run_server(self) -> None:
        """运行 Flask 服务器（多线程模式）"""
        try:
            from werkzeug.serving import make_server
            # 使用多线程模式，避免视频流阻塞其他请求
            self._server = make_server(self.host, self.port, self._app, threaded=True)
            self._server.serve_forever()
        except Exception as e:
            print(f"[RemotePlugin] 服务器异常: {e}")
    
    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "REMOTE_START":
            self.start()
            return {"status": "ok"}
        elif intent == "REMOTE_STOP":
            self.stop()
            return {"status": "ok"}
        return {"status": "ignored"}
    
    def get_supported_intents(self) -> list:
        return ["REMOTE_START", "REMOTE_STOP"]
    
    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        """状态变化时通知前端（由前端轮询，无需处理）"""
        pass
