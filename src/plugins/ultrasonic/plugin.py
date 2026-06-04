# src/plugins/ultrasonic/plugin.py
import threading
import time
from typing import Any, Dict

from src.core.base_plugin import BasePlugin
from src.core.state import RobotState
from src.common.config_loader import ConfigLoader

try:
    import lgpio
    LGPIO_AVAILABLE = True
except ImportError:
    LGPIO_AVAILABLE = False
    print("[UltrasonicPlugin] lgpio 未安装，将使用模拟模式")


class UltrasonicPlugin(BasePlugin):
    """超声波避障插件 - HC-SR04，检测到障碍物时自动停止电机"""

    def __init__(self):
        super().__init__("ultrasonic")
        self._available = LGPIO_AVAILABLE

        # 从 .env 读取引脚和安全距离
        self._trig_pin = int(ConfigLoader.get("ULTRASONIC_TRIG", "24"))
        self._echo_pin = int(ConfigLoader.get("ULTRASONIC_ECHO", "25"))
        self._safe_distance_cm = float(ConfigLoader.get("ULTRASONIC_SAFE_DISTANCE", "60"))

        self._h = None
        self._lock = threading.Lock()  # 保护 lgpio 读写
        self._running = False
        self._poll_thread: threading.Thread = None

        # 触发中标志位：只有距离真正恢复安全才重置
        self._obstacle_triggered = False

    def on_load(self) -> None:
        """初始化 lgpio，RPi5 用 gpiochip4"""
        print(f"[UltrasonicPlugin] lgpio可用: {self._available}")
        if not self._available:
            print("[UltrasonicPlugin] 依赖未安装，避障不可用")
            return

        # RPi5 上 gpiozero 占用 gpiochip0，超声波用 gpiochip4
        for chip in (4, 0):
            try:
                self._h = lgpio.gpiochip_open(chip)
                lgpio.gpio_claim_output(self._h, self._trig_pin)
                lgpio.gpio_claim_input(self._h, self._echo_pin)
                lgpio.gpio_write(self._h, self._trig_pin, 0)
                time.sleep(0.1)
                print(f"[UltrasonicPlugin] 传感器初始化成功 gpiochip{chip} "
                      f"(TRIG={self._trig_pin}, ECHO={self._echo_pin}, "
                      f"安全距离={self._safe_distance_cm}cm)")
                break
            except Exception as e:
                print(f"[UltrasonicPlugin] gpiochip{chip} 失败: {e}")
                self._h = None

        if self._h is None:
            print("[UltrasonicPlugin] 所有 gpiochip 均失败，避障不可用")
            self._available = False

    def on_unload(self) -> None:
        """释放资源"""
        self.stop()
        if self._h is not None:
            try:
                lgpio.gpiochip_close(self._h)
            except Exception:
                pass
        print("[UltrasonicPlugin] 已卸载")

    def start(self) -> None:
        """启动轮询线程"""
        if self._running:
            return
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True
        )
        self._poll_thread.start()
        print("[UltrasonicPlugin] 避障轮询已启动")

    def stop(self) -> None:
        """停止轮询线程"""
        self._running = False
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2)
        print("[UltrasonicPlugin] 避障轮询已停止")

    def _single_measure(self) -> float:
        """单次测量（厘米），失败返回 -1，调用前需持有锁"""
        try:
            # 60ms 稳定间隔，符合 HC-SR04 数据手册要求
            lgpio.gpio_write(self._h, self._trig_pin, 0)
            time.sleep(0.06)
            lgpio.gpio_write(self._h, self._trig_pin, 1)
            time.sleep(0.00001)
            lgpio.gpio_write(self._h, self._trig_pin, 0)

            # 等待 ECHO 高电平开始（超时 30ms）
            timeout = time.time() + 0.03
            while lgpio.gpio_read(self._h, self._echo_pin) == 0:
                if time.time() > timeout:
                    return -1
            start = time.time()

            # 等待 ECHO 高电平结束（超时 30ms）
            timeout = time.time() + 0.03
            while lgpio.gpio_read(self._h, self._echo_pin) == 1:
                if time.time() > timeout:
                    return -1
            stop = time.time()

            return round(((stop - start) * 34300) / 2, 1)
        except Exception as e:
            print(f"[UltrasonicPlugin] 单次测量失败: {e}")
            return -1

    def _get_distance_cm(self) -> float:
        """连续测3次取中位数，过滤噪声，失败返回 -1"""
        if not self._available or self._h is None:
            return -1
        with self._lock:
            samples = []
            for _ in range(3):
                d = self._single_measure()
                if d != -1:
                    samples.append(d)
            if not samples:
                return -1
            samples.sort()
            return samples[len(samples) // 2]

    def _get_motor_action(self) -> str:
        """获取当前电机动作"""
        if not self._brain:
            return "stop"
        motor = self._brain.get_plugin("motor")
        if motor:
            return motor.get_current_action()
        return "stop"

    def _poll_loop(self) -> None:
        """持续轮询，检测障碍物"""
        while self._running:
            try:
                distance = self._get_distance_cm()

                if distance != -1:
                    # print(f"[UltrasonicPlugin] 距离={distance:.1f}cm")  # 调试用
                    if distance < self._safe_distance_cm:
                        if not self._obstacle_triggered:
                            action = self._get_motor_action()
                            if action in ("forward", "left", "right"):
                                self._obstacle_triggered = True
                                print(f"[UltrasonicPlugin] 检测到障碍物！距离={distance:.1f}cm，执行制动")
                                self._brain._route_intent("MOTOR_STOP", {})
                    else:
                        self._obstacle_triggered = False

                time.sleep(0.5)
            except Exception as e:
                print(f"[UltrasonicPlugin] 轮询异常: {e}")
                time.sleep(0.5)

    def get_distance(self) -> float:
        """对外暴露的距离读取接口（厘米）"""
        return self._get_distance_cm()

    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "ULTRASONIC_START":
            self.start()
            return {"status": "ok"}
        elif intent == "ULTRASONIC_STOP":
            self.stop()
            return {"status": "ok"}
        elif intent == "ULTRASONIC_DISTANCE":
            distance = self._get_distance_cm()
            return {"status": "ok", "distance_cm": distance}
        return {"status": "ignored"}

    def get_supported_intents(self) -> list:
        return ["ULTRASONIC_START", "ULTRASONIC_STOP", "ULTRASONIC_DISTANCE"]

    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        pass