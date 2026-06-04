# src/plugins/led/plugin.py
import time
import threading
from typing import Any, Dict

from src.core.base_plugin import BasePlugin
from src.core.state import RobotState

try:
    from gpiozero import PWMLED
    LED_AVAILABLE = True
except ImportError:
    LED_AVAILABLE = False
    print("[LEDPlugin] gpiozero 未安装，LED 不可用")


class LEDPlugin(BasePlugin):
    """
    LED 状态灯插件 (GPIO 16)
    
    状态映射:
    - IDLE: 呼吸闪烁 (0.8秒周期)
    - AWAKE: 常亮 (80%亮度)
    - REMOTE: 快速闪烁 (0.2秒间隔)
    - TTS: 慢呼吸 (1.2秒周期，更柔和)
    """
    
    def __init__(self, pin: int = 16):
        super().__init__("led")
        self.pin = pin
        self._led = None
        self._available = LED_AVAILABLE
        self._blink_thread = None
        self._stop_blink = False
        self._current_state = RobotState.IDLE  # 记录当前状态，用于 TTS 结束后恢复
    
    def on_load(self) -> None:
        """加载插件，初始化 LED"""
        if not self._available:
            print("[LEDPlugin] LED 不可用（gpiozero未安装）")
            return
        
        try:
            self._led = PWMLED(self.pin)
            print(f"[LEDPlugin] LED 已初始化 (GPIO {self.pin})")
            self._set_idle_pattern()  # 默认 IDLE 模式
        except Exception as e:
            print(f"[LEDPlugin] LED 初始化失败: {e}")
            self._available = False
    
    def on_unload(self) -> None:
        """卸载插件，释放资源"""
        self._stop_blinking()
        if self._led:
            self._led.off()
            self._led.close()
            print("[LEDPlugin] LED 已关闭")
    
    def _stop_blinking(self) -> None:
        """停止闪烁线程"""
        self._stop_blink = True
        if self._blink_thread and self._blink_thread.is_alive():
            self._blink_thread.join(timeout=0.5)
        self._stop_blink = False
        self._blink_thread = None
    
    def _set_breathing(self, speed: float = 0.02) -> None:
        """呼吸闪烁效果（IDLE 状态）"""
        self._stop_blinking()
        
        def breathe():
            while not self._stop_blink and self._led:
                # 渐亮
                for i in range(0, 101, 5):
                    if self._stop_blink:
                        break
                    self._led.value = i / 100.0
                    time.sleep(speed)
                # 渐灭
                for i in range(100, -1, -5):
                    if self._stop_blink:
                        break
                    self._led.value = i / 100.0
                    time.sleep(speed)
        
        self._blink_thread = threading.Thread(target=breathe, daemon=True)
        self._blink_thread.start()
    
    def _set_blink(self, interval: float = 0.2) -> None:
        """快速闪烁效果（REMOTE 状态）"""
        self._stop_blinking()
        
        def blink():
            while not self._stop_blink and self._led:
                self._led.on()
                time.sleep(interval)
                if self._stop_blink:
                    break
                self._led.off()
                time.sleep(interval)
        
        self._blink_thread = threading.Thread(target=blink, daemon=True)
        self._blink_thread.start()
    
    def _set_constant(self, brightness: float = 0.8) -> None:
        """常亮效果（AWAKE 状态）"""
        self._stop_blinking()
        if self._led:
            self._led.value = brightness
    
    def _set_idle_pattern(self) -> None:
        """IDLE 状态 - 呼吸闪烁"""
        self._set_breathing(speed=0.02)
    
    def _set_awake_pattern(self) -> None:
        """AWAKE 状态 - 常亮"""
        self._set_constant(brightness=0.8)
    
    def _set_remote_pattern(self) -> None:
        """REMOTE 状态 - 快速闪烁"""
        self._set_blink(interval=0.2)
    
    def _set_tts_pattern(self) -> None:
        """TTS 播报状态 - 慢呼吸 (1.2秒周期，更柔和)"""
        self._stop_blinking()
        
        def tts_breathe():
            while not self._stop_blink and self._led:
                # 渐亮（更柔和，最高60%亮度）
                for i in range(0, 61, 3):
                    if self._stop_blink:
                        break
                    self._led.value = i / 100.0
                    time.sleep(0.02)
                # 渐灭
                for i in range(60, -1, -3):
                    if self._stop_blink:
                        break
                    self._led.value = i / 100.0
                    time.sleep(0.02)
        
        self._blink_thread = threading.Thread(target=tts_breathe, daemon=True)
        self._blink_thread.start()
    
    def on_tts_start(self) -> None:
        """TTS 播报开始时调用"""
        if self._available:
            self._set_tts_pattern()
    
    def on_tts_end(self) -> None:
        """TTS 播报结束时调用，恢复到当前状态对应的模式"""
        if self._available:
            if self._current_state == RobotState.IDLE:
                self._set_idle_pattern()
            elif self._current_state == RobotState.AWAKE:
                self._set_awake_pattern()
            elif self._current_state == RobotState.REMOTE:
                self._set_remote_pattern()
    
    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        """执行指令"""
        if intent == "LED_ON":
            self._set_constant(0.8)
            return {"status": "ok"}
        elif intent == "LED_OFF":
            self._led.off()
            return {"status": "ok"}
        elif intent == "LED_BLINK":
            interval = params.get("interval", 0.2)
            self._set_blink(interval)
            return {"status": "ok"}
        
        return {"status": "ignored"}
    
    def get_supported_intents(self) -> list:
        return ["LED_ON", "LED_OFF", "LED_BLINK"]
    
    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        """状态变化时更新 LED 模式"""
        # 更新当前状态记录
        self._current_state = new_state
        
        if new_state == RobotState.IDLE:
            self._set_idle_pattern()
        elif new_state == RobotState.AWAKE:
            self._set_awake_pattern()
        elif new_state == RobotState.REMOTE:
            self._set_remote_pattern()