# src/plugins/buzzer/plugin.py
import time
from typing import Any, Dict

from src.core.base_plugin import BasePlugin
from src.core.state import RobotState

try:
    from gpiozero import PWMOutputDevice
    BUZZER_AVAILABLE = True
except ImportError:
    BUZZER_AVAILABLE = False
    print("[BuzzerPlugin] gpiozero 未安装，蜂鸣器不可用")


class BuzzerPlugin(BasePlugin):
    """蜂鸣器插件 - 无源PWM蜂鸣器 (GPIO 12)"""
    
    def __init__(self, pin: int = 12, frequency: int = 2000):
        super().__init__("buzzer")
        self.pin = pin
        self.default_freq = frequency
        self._buzzer = None
        self._available = BUZZER_AVAILABLE
    
    def on_load(self) -> None:
        if not self._available:
            print("[BuzzerPlugin] 蜂鸣器不可用（gpiozero未安装）")
            return
        
        try:
            self._buzzer = PWMOutputDevice(self.pin, frequency=self.default_freq)
            print(f"[BuzzerPlugin] 蜂鸣器已初始化 (GPIO {self.pin})")
        except Exception as e:
            print(f"[BuzzerPlugin] 蜂鸣器初始化失败: {e}")
            self._available = False
    
    def on_unload(self) -> None:
        if self._buzzer:
            self._buzzer.off()
            self._buzzer.close()
            print("[BuzzerPlugin] 蜂鸣器已关闭")
    
    def beep(self, times: int = 1, duration: float = 0.1, frequency: int = None) -> None:
        """蜂鸣器响几声"""
        if not self._available or not self._buzzer:
            return
        
        freq = frequency or self.default_freq
        self._buzzer.frequency = freq
        
        for i in range(times):
            self._buzzer.value = 0.5
            time.sleep(duration)
            self._buzzer.off()
            if i < times - 1:
                time.sleep(duration)
    
    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "BEEP":
            times = params.get("times", 1)
            duration = params.get("duration", 0.1)
            frequency = params.get("frequency", None)
            self.beep(times, duration, frequency)
            return {"status": "ok", "action": "beep"}
        return {"status": "ignored"}
    
    def get_supported_intents(self) -> list:
        return ["BEEP"]
    
    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        pass