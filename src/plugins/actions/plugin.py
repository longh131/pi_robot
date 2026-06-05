from typing import Any, Dict
from src.core.base_plugin import BasePlugin
from threading import Thread, Lock
import time
import cv2

class ActionsPlugin(BasePlugin):
    def __init__(self):
        super().__init__("actions")
        self._running = False
        self._current_action = None
        self._speed = 0.5
        self._dance_active = False
        self._follow_active = False
        self._motion_lock = Lock()
        
        self._dance_thread = None
        self._follow_thread = None
        
        self._face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self._camera = None

    def on_load(self):
        """插件加载时调用"""
        pass

    def start(self):
        self._running = True

    def stop(self):
        self._running = False
        self._dance_active = False
        self._follow_active = False
        self._handle_stop()
        if self._camera:
            self._camera.release()

    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "MOVE_FORWARD":
            return self._handle_forward()
        elif intent == "MOVE_BACKWARD":
            return self._handle_backward()
        elif intent == "TURN_LEFT":
            return self._handle_left()
        elif intent == "TURN_RIGHT":
            return self._handle_right()
        elif intent == "STOP":
            return self._handle_stop()
        elif intent == "SPEED_UP":
            return self._handle_speed_up()
        elif intent == "SPEED_DOWN":
            return self._handle_speed_down()
        elif intent == "DANCE":
            return self._handle_dance()
        elif intent == "FOLLOW_ME":
            return self._handle_follow()
        return None

    def get_supported_intents(self) -> list:
        return ["MOVE_FORWARD", "MOVE_BACKWARD", "TURN_LEFT", "TURN_RIGHT", 
                "STOP", "SPEED_UP", "SPEED_DOWN", "DANCE", "FOLLOW_ME"]

    def _get_motor_plugin(self):
        """获取 motor 插件实例"""
        motor = self._brain.get_plugin("motor")
        return motor

    def _obstacle_detected(self) -> bool:
        ultrasonic = self._brain.get_plugin("ultrasonic")
        if ultrasonic and hasattr(ultrasonic, 'obstacle_detected'):
            return ultrasonic.obstacle_detected
        return False

    def _handle_forward(self) -> str:
        if self._obstacle_detected():
            return "前方有障碍物，无法前进"
        
        with self._motion_lock:
            self._current_action = "forward"
            self._dance_active = False
            self._follow_active = False
            motor = self._get_motor_plugin()
            if motor:
                motor.execute("MOTOR_FORWARD", {"speed": self._speed * 100})
        
        return "正在前进"

    def _handle_backward(self) -> str:
        with self._motion_lock:
            self._current_action = "backward"
            self._dance_active = False
            self._follow_active = False
            motor = self._get_motor_plugin()
            if motor:
                motor.execute("MOTOR_BACKWARD", {"speed": self._speed * 100})
        
        return "正在后退"

    def _handle_left(self) -> str:
        with self._motion_lock:
            self._current_action = "left"
            self._dance_active = False
            self._follow_active = False
            motor = self._get_motor_plugin()
            if motor:
                motor.execute("MOTOR_LEFT", {"speed": self._speed * 100})
        
        return "正在左转"

    def _handle_right(self) -> str:
        with self._motion_lock:
            self._current_action = "right"
            self._dance_active = False
            self._follow_active = False
            motor = self._get_motor_plugin()
            if motor:
                motor.execute("MOTOR_RIGHT", {"speed": self._speed * 100})
        
        return "正在右转"

    def _handle_stop(self) -> str:
        motor = self._get_motor_plugin()
        if motor:
            motor.execute("MOTOR_STOP", {})
        with self._motion_lock:
            self._current_action = "stop"
        return "已停止"

    def _handle_speed_up(self) -> str:
        with self._motion_lock:
            self._speed = min(1.0, self._speed + 0.1)
        return f"速度已调整为 {int(self._speed * 100)}%"

    def _handle_speed_down(self) -> str:
        with self._motion_lock:
            self._speed = max(0.1, self._speed - 0.1)
        return f"速度已调整为 {int(self._speed * 100)}%"

    def _handle_dance(self) -> str:
        if self._dance_active:
            return "正在跳舞中"
        
        self._dance_active = True
        self._follow_active = False
        self._current_action = "dance"
        
        self._dance_thread = Thread(target=self._dance_loop, daemon=True)
        self._dance_thread.start()
        
        return "开始跳舞"

    def _dance_loop(self):
        dance_sequence = [
            ("forward", 0.5), ("backward", 0.5),
            ("left", 0.3), ("right", 0.3),
            ("left", 0.3), ("right", 0.3),
            ("forward", 0.4), ("stop", 0.2),
            ("left", 0.6), ("right", 0.6),
            ("forward", 0.3), ("backward", 0.3),
        ]
        
        while self._dance_active and self._running:
            for action, duration in dance_sequence:
                if not self._dance_active:
                    break
                
                if action == "forward":
                    motor = self._get_motor_plugin()
                    if motor:
                        motor.execute("MOTOR_FORWARD", {"speed": self._speed * 80})
                elif action == "backward":
                    motor = self._get_motor_plugin()
                    if motor:
                        motor.execute("MOTOR_BACKWARD", {"speed": self._speed * 80})
                elif action == "left":
                    motor = self._get_motor_plugin()
                    if motor:
                        motor.execute("MOTOR_LEFT", {"speed": self._speed * 60})
                elif action == "right":
                    motor = self._get_motor_plugin()
                    if motor:
                        motor.execute("MOTOR_RIGHT", {"speed": self._speed * 60})
                elif action == "stop":
                    motor = self._get_motor_plugin()
                    if motor:
                        motor.execute("MOTOR_STOP", {})
                
                time.sleep(duration)
            
            time.sleep(0.5)

    def _handle_follow(self) -> str:
        if self._follow_active:
            return "正在跟随中"
        
        self._follow_active = True
        self._dance_active = False
        self._current_action = "follow"
        
        self._follow_thread = Thread(target=self._follow_loop, daemon=True)
        self._follow_thread.start()
        
        return "开始跟随你"

    def _follow_loop(self):
        try:
            self._camera = cv2.VideoCapture(0)
            if not self._camera.isOpened():
                print("[ActionsPlugin] 无法打开摄像头")
                self._follow_active = False
                return
            
            while self._follow_active and self._running:
                ret, frame = self._camera.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self._face_cascade.detectMultiScale(gray, 1.1, 4)
                
                if len(faces) > 0:
                    x, _, w, h = faces[0]
                    center_x = x + w // 2
                    frame_center = frame.shape[1] // 2
                    
                    deviation = center_x - frame_center
                    area = w * h
                    
                    motor = self._get_motor_plugin()
                    
                    if area < 5000:
                        if motor:
                            motor.execute("MOTOR_FORWARD", {"speed": self._speed * 60})
                    elif area > 20000:
                        if motor:
                            motor.execute("MOTOR_STOP", {})
                    else:
                        if deviation < -30:
                            if motor:
                                motor.execute("MOTOR_LEFT", {"speed": self._speed * 40})
                        elif deviation > 30:
                            if motor:
                                motor.execute("MOTOR_RIGHT", {"speed": self._speed * 40})
                        else:
                            if motor:
                                motor.execute("MOTOR_STOP", {})
                else:
                    motor = self._get_motor_plugin()
                    if motor:
                        motor.execute("MOTOR_STOP", {})
                
                time.sleep(0.05)
        except Exception as e:
            print(f"[ActionsPlugin] 跟随异常：{e}")
        finally:
            if self._camera:
                self._camera.release()
            motor = self._get_motor_plugin()
            if motor:
                motor.execute("STOP", {})