from typing import Any, Dict, Optional
from src.core.base_plugin import BasePlugin
import subprocess
import time


class SystemPlugin(BasePlugin):
    def __init__(self):
        super().__init__("system")
        self.start_time = time.time()

    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "SYSTEM_VOLUME_UP":
            return self._volume_up()
        elif intent == "SYSTEM_VOLUME_DOWN":
            return self._volume_down()
        elif intent == "SYSTEM_STOP":
            return self._system_stop()
        elif intent == "SYSTEM_STATUS":
            return self._handle_status()
        return None

    def get_supported_intents(self) -> list:
        return ["SYSTEM_VOLUME_UP", "SYSTEM_VOLUME_DOWN", "SYSTEM_STOP", "SYSTEM_STATUS"]

    def _volume_up(self) -> str:
        try:
            subprocess.run(['amixer', 'sset', "'Master'", '10%+'], 
                        capture_output=True, text=True, timeout=5)
            return "音量已增加"
        except Exception as e:
            print(f"[SystemPlugin] 音量调整失败: {e}")
            return "音量调整失败"

    def _volume_down(self) -> str:
        try:
            subprocess.run(['amixer', 'sset', "'Master'", '10%-'], 
                        capture_output=True, text=True, timeout=5)
            return "音量已降低"
        except Exception as e:
            print(f"[SystemPlugin] 音量调整失败: {e}")
            return "音量调整失败"

    def _system_stop(self) -> str:
        motor = self._brain.get_plugin("motor")
        if motor:
            motor.execute("STOP", {})
        ultrasonic = self._brain.get_plugin("ultrasonic")
        if ultrasonic:
            ultrasonic.execute("STOP", {})
        return "系统已紧急停止"

    def _get_uptime(self):
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}小时{minutes}分钟"
        except Exception:
            uptime = time.time() - self.start_time
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            return f"{hours}小时{minutes}分钟"

    def _get_cpu_usage(self):
        try:
            result = subprocess.run(['top', '-bn1', '-p', '1'], 
                                capture_output=True, text=True, timeout=5)
            lines = result.stdout.split('\n')
            for line in lines:
                if '%Cpu(s)' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        return f"{parts[1]}%"
            return "未知"
        except Exception:
            return "未知"

    def _get_memory_usage(self):
        try:
            result = subprocess.run(['free', '-h'], capture_output=True, text=True, timeout=5)
            lines = result.stdout.split('\n')
            for line in lines:
                if line.startswith('Mem:'):
                    parts = line.split()
                    if len(parts) >= 3:
                        return f"{parts[2]}/{parts[1]}"
            return "未知"
        except Exception:
            return "未知"

    def _handle_status(self) -> str:
        uptime = self._get_uptime()
        cpu_usage = self._get_cpu_usage()
        memory_usage = self._get_memory_usage()
        
        message = f"我已经工作了{uptime}，大脑用了{cpu_usage}，内存使用{memory_usage}。"
        print(f"【系统状态】{message}")
        return message