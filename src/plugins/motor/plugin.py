import threading
import time
from typing import Any, Dict

from src.core.base_plugin import BasePlugin
from src.core.state import RobotState
from src.common.config_loader import ConfigLoader

try:
    from gpiozero import DigitalOutputDevice, PWMOutputDevice
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    print("[MotorPlugin] gpiozero 未安装，将使用模拟模式")


class MotorPlugin(BasePlugin):
    """电机控制插件 - 支持前进/后退/左转/右转/停止及加减速"""
    
    def __init__(self):
        super().__init__("motor")
        self._running = False
        self._available = GPIOZERO_AVAILABLE
        
        # 速度控制（0-100）
        self._speed = int(float(ConfigLoader.get("MOTOR_SPEED", "0.5")) * 100)
        self._max_speed = 100
        self._min_speed = 0
        self._speed_step = 10
        
        # GPIO 引脚定义（从配置读取）
        self._left_forward_pin = int(ConfigLoader.get("MOTOR_LEFT_FORWARD", "17"))
        self._left_backward_pin = int(ConfigLoader.get("MOTOR_LEFT_BACKWARD", "18"))
        self._right_forward_pin = int(ConfigLoader.get("MOTOR_RIGHT_FORWARD", "27"))
        self._right_backward_pin = int(ConfigLoader.get("MOTOR_RIGHT_BACKWARD", "22"))
        self._left_pwm_pin = int(ConfigLoader.get("MOTOR_LEFT_PWM", "19"))
        self._right_pwm_pin = int(ConfigLoader.get("MOTOR_RIGHT_PWM", "26"))
        
        print(f"[MotorPlugin] 引脚配置: left_forward={self._left_forward_pin}, left_backward={self._left_backward_pin}, right_forward={self._right_forward_pin}, right_backward={self._right_backward_pin}, left_pwm={self._left_pwm_pin}, right_pwm={self._right_pwm_pin}")
        
        # GPIO设备
        self._left_forward = None
        self._left_backward = None
        self._right_forward = None
        self._right_backward = None
        self._left_pwm = None
        self._right_pwm = None
        
        # 当前运动状态
        self._current_action = "stop"
        
        # 模拟模式下的状态
        self._simulated_action = "stop"
        self._simulated_speed = self._speed

    def on_load(self) -> None:
        """初始化电机控制"""
        print(f"[MotorPlugin] gpiozero可用: {self._available}")
        
        if self._available:
            try:
                # 初始化数字输出设备
                self._left_forward = DigitalOutputDevice(self._left_forward_pin)
                self._left_backward = DigitalOutputDevice(self._left_backward_pin)
                self._right_forward = DigitalOutputDevice(self._right_forward_pin)
                self._right_backward = DigitalOutputDevice(self._right_backward_pin)
                
                # 初始化 PWM 设备
                self._left_pwm = PWMOutputDevice(self._left_pwm_pin, initial_value=0)
                self._right_pwm = PWMOutputDevice(self._right_pwm_pin, initial_value=0)
                
                # 确保电机停止
                self._stop_motors()
                print("[MotorPlugin] 电机控制初始化成功")
            except Exception as e:
                print(f"[MotorPlugin] GPIO初始化失败: {e}")
                print("[MotorPlugin] 可能原因: 非树莓派硬件环境, 需要root权限, 或GPIO未启用")
                print("[MotorPlugin] 切换到模拟模式运行")
                self._available = False
                # 清理已初始化的设备
                self._cleanup_devices()
        
        if not self._available:
            print("[MotorPlugin] 运行在模拟模式 - 所有电机命令将被记录但不会实际执行")

    def _cleanup_devices(self):
        """清理 GPIO 设备"""
        devices = [
            self._left_forward, 
            self._left_backward, 
            self._right_forward, 
            self._right_backward,
            self._left_pwm,
            self._right_pwm
        ]
        for device in devices:
            if device:
                try:
                    device.close()
                except:
                    pass

    def on_unload(self) -> None:
        """释放资源"""
        self.stop()
        self._cleanup_devices()
        print("[MotorPlugin] 已卸载")

    def start(self) -> None:
        """启动电机控制"""
        self._running = True
        print("[MotorPlugin] 电机控制已启动")

    def stop(self) -> None:
        """停止电机控制"""
        self._running = False
        self._stop_motors()
        print("[MotorPlugin] 电机控制已停止")

    def _set_speed(self, speed: int) -> None:
        """设置速度（内部方法）"""
        old_speed = self._speed
        self._speed = max(self._min_speed, min(self._max_speed, speed))
        self._simulated_speed = self._speed
        
        if self._available and self._left_pwm and self._right_pwm:
            # 将 0-100 转换为 0-1 的占空比
            pwm_value = self._speed / 100.0
            self._left_pwm.value = pwm_value
            self._right_pwm.value = pwm_value
        
        print(f"[MotorPlugin] 速度: {old_speed}% -> {self._speed}%")

    def _stop_motors(self) -> None:
        """停止所有电机"""
        self._current_action = "stop"
        self._simulated_action = "stop"
        
        if self._available:
            if self._left_forward:
                self._left_forward.off()
            if self._left_backward:
                self._left_backward.off()
            if self._right_forward:
                self._right_forward.off()
            if self._right_backward:
                self._right_backward.off()
            if self._left_pwm:
                self._left_pwm.value = 0
            if self._right_pwm:
                self._right_pwm.value = 0

    def _move_forward(self) -> None:
        """前进"""
        if not self._running:
            return
        
        self._current_action = "forward"
        self._simulated_action = "forward"
        
        current_speed = self._speed / 100.0
        
        if self._available:
            self._left_forward.off()
            self._left_backward.on()
            self._left_pwm.value = current_speed
            
            self._right_forward.on()
            self._right_backward.off()
            self._right_pwm.value = current_speed
        
        print(f"[MotorPlugin] 前进 (速度: {self._speed}%)")

    def _move_backward(self) -> None:
        """后退"""
        if not self._running:
            return
        
        self._current_action = "backward"
        self._simulated_action = "backward"
        
        current_speed = self._speed / 100.0
        
        if self._available:
            self._left_forward.on()
            self._left_backward.off()
            self._left_pwm.value = current_speed
            
            self._right_forward.off()
            self._right_backward.on()
            self._right_pwm.value = current_speed
        
        print(f"[MotorPlugin] 后退 (速度: {self._speed}%)")

    def _turn_left(self) -> None:
        """左转"""
        if not self._running:
            return
        
        self._current_action = "left"
        self._simulated_action = "left"
        
        current_speed = self._speed / 100.0
        
        if self._available:
            self._left_forward.on()
            self._left_backward.off()
            self._left_pwm.value = current_speed * 0.8
            
            self._right_forward.on()
            self._right_backward.off()
            self._right_pwm.value = current_speed
        
        print(f"[MotorPlugin] 左转 (速度: {self._speed}%)")

    def _turn_right(self) -> None:
        """右转"""
        if not self._running:
            return
        
        self._current_action = "right"
        self._simulated_action = "right"
        
        current_speed = self._speed / 100.0
        
        if self._available:
            self._left_forward.off()
            self._left_backward.on()
            self._left_pwm.value = current_speed
            
            self._right_forward.off()
            self._right_backward.on()
            self._right_pwm.value = current_speed * 0.8
        
        print(f"[MotorPlugin] 右转 (速度: {self._speed}%)")

    def get_speed(self) -> int:
        """获取当前速度"""
        return self._speed

    def get_current_action(self) -> str:
        """获取当前动作"""
        return self._current_action

    def _check_obstacle(self) -> bool:
        """检查是否有障碍物（距离小于安全距离）"""
        from src.common.config_loader import ConfigLoader
        safe_distance = int(ConfigLoader.get("ULTRASONIC_SAFE_DISTANCE", "60"))
        
        if hasattr(self, '_brain') and 'ultrasonic' in self._brain.plugins:
            result = self._brain._route_intent("ULTRASONIC_DISTANCE", {})
            if result and result.get('distance_cm') is not None:
                return result.get('distance_cm') < safe_distance
        return False
    
    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        # 如果插件未启动，先启动
        if not self._running:
            self.start()
        
        if intent == "MOTOR_FORWARD":
            if self._check_obstacle():
                return {"status": "blocked", "message": "前方有障碍物，无法前进"}
            self._move_forward()
            return {"status": "ok", "action": "forward", "speed": self._speed}
        
        elif intent == "MOTOR_BACKWARD":
            self._move_backward()
            return {"status": "ok", "action": "backward", "speed": self._speed}
        
        elif intent == "MOTOR_LEFT":
            if self._check_obstacle():
                return {"status": "blocked", "message": "前方有障碍物，无法左转"}
            self._turn_left()
            return {"status": "ok", "action": "left", "speed": self._speed}
        
        elif intent == "MOTOR_RIGHT":
            if self._check_obstacle():
                return {"status": "blocked", "message": "前方有障碍物，无法右转"}
            self._turn_right()
            return {"status": "ok", "action": "right", "speed": self._speed}
        
        elif intent == "MOTOR_STOP":
            self._stop_motors()
            return {"status": "ok", "action": "stop", "speed": self._speed}
        
        elif intent == "MOTOR_SPEED_UP":
            self._set_speed(self._speed + self._speed_step)
            return {"status": "ok", "speed": self._speed}
        
        elif intent == "MOTOR_SPEED_DOWN":
            self._set_speed(self._speed - self._speed_step)
            return {"status": "ok", "speed": self._speed}
        
        elif intent == "MOTOR_SET_SPEED":
            speed = params.get('speed', 50)
            self._set_speed(int(speed))
            return {"status": "ok", "speed": self._speed}
        
        elif intent == "MOTOR_GET_STATUS":
            return {
                "status": "ok", 
                "action": self._current_action, 
                "speed": self._speed,
                "available": self._available
            }
        
        return {"status": "ignored"}

    def get_supported_intents(self) -> list:
        return [
            "MOTOR_FORWARD", 
            "MOTOR_BACKWARD", 
            "MOTOR_LEFT", 
            "MOTOR_RIGHT", 
            "MOTOR_STOP",
            "MOTOR_SPEED_UP",
            "MOTOR_SPEED_DOWN",
            "MOTOR_SET_SPEED",
            "MOTOR_GET_STATUS"
        ]
    
    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        """状态变化时处理"""
        if old_state == RobotState.REMOTE and new_state != RobotState.REMOTE:
            self._stop_motors()
            print("[MotorPlugin] 退出远程控制，已停止电机")