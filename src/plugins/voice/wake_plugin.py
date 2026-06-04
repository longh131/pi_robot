# src/plugins/voice/wake_plugin.py
import threading
import time
from typing import Any, Dict

from src.core.base_plugin import BasePlugin
from src.core.state import RobotState
from src.plugins.voice.wake import WakeEngine


class WakePlugin(BasePlugin):
    """唤醒词插件 - 包装原有 WakeEngine"""
    
    def __init__(self, check_interval: float = 0.05):
        super().__init__("wake")
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._engine = None
        self._buzzer = None
        self._should_stop = False  # 用于中断 listen_and_wake
    
    def on_load(self) -> None:
        """初始化唤醒引擎"""
        try:
            self._engine = WakeEngine()
            print("[WakePlugin] 唤醒引擎已初始化")
        except Exception as e:
            print(f"[WakePlugin] 唤醒引擎初始化失败: {e}")
    
    def set_brain(self, brain) -> None:
        """设置 Brain 引用并缓存 buzzer"""
        super().set_brain(brain)
        if brain:
            self._buzzer = brain.get_plugin("buzzer")
            if self._buzzer:
                print("[WakePlugin] buzzer 插件已缓存")
            else:
                print("[WakePlugin] 警告: buzzer 插件未找到")
    
    def on_unload(self) -> None:
        """停止检测线程"""
        self.stop()
    
    def start(self) -> None:
        """启动唤醒检测线程"""
        if self._running:
            return
        
        # 等待 buzzer 就绪（最多等待 1 秒）
        wait_count = 0
        while self._buzzer is None and wait_count < 20:
            time.sleep(0.05)
            wait_count += 1
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[WakePlugin] 唤醒检测已启动")
    
    def stop(self) -> None:
        """停止唤醒检测"""
        self._running = False
        
        # 设置停止标志，中断当前监听
        self._should_stop = True
        
        if self._thread:
            self._thread.join(timeout=1)
        
        # 确保音频流被释放
        if self._engine and hasattr(self._engine, 'cleanup') and callable(self._engine.cleanup):
            try:
                self._engine.cleanup()
                print("[WakePlugin] 音频引擎已清理")
            except Exception as e:
                print(f"[WakePlugin] 清理音频引擎失败: {e}")
        
        print("[WakePlugin] 唤醒检测已停止")
    
    def _run(self) -> None:
        """检测循环"""
        while self._running:
            if not self._brain:
                time.sleep(self.check_interval)
                continue
            
            current_state = self._brain.get_state()
            
            # IDLE 状态：正常检测唤醒
            if current_state == "idle":
                try:
                    # 重置停止标志
                    self._should_stop = False
                    # 传入 stop_check 回调，允许状态变化时中断
                    if self._engine and self._engine.listen_and_wake(stop_check=lambda: self._should_stop):
                        print("[WakePlugin] 检测到唤醒词")
                        self._brain.wake()
                except Exception as e:
                    print(f"[WakePlugin] 检测异常: {e}")
            
            # REMOTE 状态：继续检测，但只触发蜂鸣器
            elif current_state == "remote":
                try:
                    # 重置停止标志
                    self._should_stop = False
                    # 传入 stop_check 回调，允许状态变化时中断
                    if self._engine and self._engine.listen_and_wake(stop_check=lambda: self._should_stop):
                        print("[WakePlugin] REMOTE状态下检测到唤醒词，拒绝")
                        self._on_wake_rejected()
                        # 短暂等待，让状态有足够时间同步
                        time.sleep(0.2)
                except Exception as e:
                    print(f"[WakePlugin] 检测异常: {e}")
            
            # AWAKE 状态：不检测唤醒词
            time.sleep(self.check_interval)
    
    def _on_wake_rejected(self) -> None:
        """唤醒被拒绝时的反馈（蜂鸣器三声）"""
        if self._buzzer:
            self._buzzer.beep(times=3, duration=0.1, frequency=2000)
    
    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "WAKE_START":
            self.start()
            return {"status": "ok"}
        elif intent == "WAKE_STOP":
            self.stop()
            return {"status": "ok"}
        return {"status": "ignored"}
    
    def get_supported_intents(self) -> list:
        return ["WAKE_START", "WAKE_STOP"]
    
    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        """状态变化时处理"""
        if not self._brain:
            return
        
        # 状态变化时设置停止标志，中断当前的监听循环
        self._should_stop = True
        
        # 如果进入 IDLE 状态且未运行，则启动检测
        if new_state == RobotState.IDLE and not self._running:
            self.start()