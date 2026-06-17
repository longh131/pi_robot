# src/core/brain.py（完整版，集成所有插件）
import time
import threading
from typing import Dict, Optional, Any
from pathlib import Path
import sys
import json
from loguru import logger

# 动态添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.state import RobotState
from src.core.state_machine import StateMachine
from src.core.command_queue import CommandQueue, Command, CommandType
from src.core.base_plugin import BasePlugin
from src.core.interrupt import trigger_interrupt, reset_interrupt, is_interrupted
from src.core.intent_handler import IntentHandler
from src.core.intent_mapping import get_command_type


class RobotBrain:
    """机器人核心大脑 - 状态机 + 指令队列 + 插件管理"""
    
    def __init__(self):
        logger.info("--- 初始化机器人大脑 ---")
        
        # 加载配置
        self._load_config()
        
        # 状态机
        self.sm = StateMachine()
        self.sm.add_listener(self._on_state_change)
        
        # 指令队列
        self.cmd_queue = CommandQueue()
        
        # 插件管理
        self.plugins: Dict[str, BasePlugin] = {}
        
        # 状态回调（供外部监听）
        self._state_callbacks = []
        
        # 超时管理
        self._awake_start_time: float = 0
        self._idle_check_interval: float = 0.5
        self._running = False
        self._main_thread: Optional[threading.Thread] = None
        
        # 意图处理器
        self.intent_handler = IntentHandler()
    
    def _get_command_type_for_intent(self, intent: str) -> CommandType:
        """获取意图对应的指令类型"""
        return get_command_type(intent)
    
    def _load_config(self) -> None:
        """从 robot_profile.json 加载配置"""
        try:
            profile_path = ROOT_DIR / "data" / "robot_profile.json"
            with open(profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                robot_cfg = data.get("robot", {})
                personality_cfg = data.get("personality", {})
                self.exit_words = robot_cfg.get("exit_words", ["退出", "再见", "拜拜", "结束"])
                # awake_timeout 配置单位为分钟，转换为秒
                awake_timeout_minutes = robot_cfg.get("awake_timeout", 10)
                self.awake_timeout = awake_timeout_minutes * 60
                self.emergency_stop_words = robot_cfg.get("emergency_stop_words", ["停止", "停", "住手"])
                # 问候语和告别语
                self.greetings = personality_cfg.get("greeting", ["你好！我是小派。"])
                self.farewells = personality_cfg.get("farewell", ["再见！"])
                logger.info(f"[Brain] 加载配置: 退出词={self.exit_words}, 超时={self.awake_timeout}秒")
        except Exception as e: # 捕获所有异常，包括配置文件不存在，默认以下配置
            logger.warning(f"[Brain] 加载配置失败: {e}")
            self.exit_words = ["退出", "再见", "拜拜", "结束"]
            self.awake_timeout = 10 * 60
            self.emergency_stop_words = ["停止", "停", "住手"]
            self.greetings = ["你好！我是小派。"]
            self.farewells = ["再见！"]
    
    # ========== 插件管理 ==========
    
    def register_plugin(self, name: str, plugin: BasePlugin) -> None:
        """注册插件"""
        logger.info(f"[Brain] 注册插件: {name}")
        
        if name in self.plugins:
            print(f"[Brain] 插件 {name} 已存在，将被覆盖")
        
        plugin.set_brain(self)
        plugin.on_load()
        self.plugins[name] = plugin
        print(f"[Brain] 插件已注册: {name}")
    
    def unregister_plugin(self, name: str) -> None:
        """注销插件"""
        if name in self.plugins:
            self.plugins[name].on_unload()
            del self.plugins[name]
            print(f"[Brain] 插件已注销: {name}")
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """获取插件实例"""
        return self.plugins.get(name)
    
    # ========== 状态监听 ==========
    
    def add_state_callback(self, callback) -> None:
        """添加状态变化回调"""
        self._state_callbacks.append(callback)
    
    def _on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        """状态变化时的内部处理"""
        print(f"[Brain] 状态变化: {old_state.value} -> {new_state.value}")
        
        # 进入唤醒状态时记录开始时间并播放问候语
        if new_state == RobotState.AWAKE and old_state == RobotState.IDLE:
            self._awake_start_time = time.time()
            self._play_greeting()
        
        # 进入休眠状态时播放告别语
        if new_state == RobotState.IDLE and old_state == RobotState.AWAKE:
            self._play_farewell()
        
        # 通知所有插件
        for plugin in self.plugins.values():
            try:
                plugin.on_state_change(old_state, new_state)
            except Exception as e:
                print(f"[Brain] 插件 {plugin.name} 状态回调异常: {e}")
        
        # 通知外部回调
        for callback in self._state_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                print(f"[Brain] 状态回调异常: {e}")
    
    def _play_greeting(self):
        """播放随机问候语"""
        import random
        greeting = random.choice(self.greetings)
        print(f"[Brain] 播放问候语: {greeting}")
        tts_plugin = self.get_plugin("tts")
        if tts_plugin:
            tts_plugin.speak(greeting)
    
    def _play_farewell(self):
        """播放随机告别语"""
        import random
        farewell = random.choice(self.farewells)
        print(f"[Brain] 播放告别语: {farewell}")
        tts_plugin = self.get_plugin("tts")
        if tts_plugin:
            tts_plugin.speak(farewell)
    
    # ========== 核心接口 ==========
    
    def start(self) -> None:
        """启动大脑"""
        if self._running:
            return
        
        self._running = True
        self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self._main_thread.start()
        logger.info("[Brain] 大脑已启动")
        print("[Brain] 大脑已启动")
        
        # 自动启动唤醒插件
        wake_plugin = self.get_plugin("wake")
        if wake_plugin:
            wake_plugin.start()
        
        # 自动启动远程插件
        remote_plugin = self.get_plugin("remote")
        if remote_plugin:
            remote_plugin.start()
        
        # 自动启动动作插件（跳舞、跟随等）
        actions_plugin = self.get_plugin("actions")
        if actions_plugin:
            actions_plugin.start()
    
    def stop(self) -> None:
        """停止大脑"""
        self._running = False
        if self._main_thread:
            self._main_thread.join(timeout=2)
        print("[Brain] 大脑已停止")
    
    def wake(self) -> bool:
        """唤醒机器人（从IDLE进入AWAKE）"""
        return self.sm.transition_to(RobotState.AWAKE)
    
    def sleep(self) -> bool:
        """休眠机器人（回到IDLE）"""
        return self.sm.transition_to(RobotState.IDLE)
    
    def remote_connect(self) -> bool:
        """远程连接请求"""
        if self.sm.can_transition_to(RobotState.REMOTE):
            return self.sm.transition_to(RobotState.REMOTE)
        else:
            from src.core.state import StateTransition
            msg = StateTransition.get_error_message(self.sm.state, RobotState.REMOTE)
            if msg:
                print(f"[Brain] 远程连接被拒绝: {msg}")
            return False
    
    def remote_disconnect(self) -> bool:
        """远程断开连接"""
        if self.sm.state == RobotState.REMOTE:
            return self.sm.transition_to(RobotState.IDLE)
        return False
    
    def get_state(self) -> str:
        """获取当前状态字符串"""
        return self.sm.state.value
    
    def is_idle(self) -> bool:
        return self.sm.state == RobotState.IDLE
    
    def is_awake(self) -> bool:
        return self.sm.state == RobotState.AWAKE
    
    def is_remote(self) -> bool:
        return self.sm.state == RobotState.REMOTE
    
    def trigger_emergency_stop(self) -> None:
        """触发紧急停止（打断当前操作，但保持AWAKE状态）"""
        logger.info("[Brain] 触发紧急停止")
        trigger_interrupt()
        self.cmd_queue.clear()
        
        motor_plugin = self.get_plugin("motor")
        if motor_plugin:
            motor_plugin.execute("MOTOR_STOP", {})
        
        ultrasonic_plugin = self.get_plugin("ultrasonic")
        if ultrasonic_plugin:
            ultrasonic_plugin.stop()
        
        for plugin in self.plugins.values():
            try:
                if hasattr(plugin, 'on_emergency_stop'):
                    plugin.on_emergency_stop()
            except Exception as e:
                logger.error(f"[Brain] 插件 {plugin.name} 紧急停止回调异常: {e}")
        time.sleep(0.1)
        reset_interrupt()
    
    def _default_command_callback(self, cmd):
        """默认指令执行回调"""
        result = self._route_intent(cmd.intent, cmd.params)
        if result:
            print(f"[Brain] 指令执行结果: {result}")
            self._speak(result)

    def submit_command(self, intent: str, params: Dict[str, Any],
                       command_type: CommandType = CommandType.QUEUED,
                       resources: set = None,
                       callback: callable = None) -> bool:
        """提交指令到队列"""
        if self.sm.state != RobotState.AWAKE:
            print(f"[Brain] 当前状态 {self.sm.state.value} 不能接收指令")
            return False
        
        # 如果没有提供回调，使用默认回调
        if callback is None:
            callback = self._default_command_callback
        
        cmd = Command(
            intent=intent,
            params=params,
            command_type=command_type,
            resources=resources or set(),
            callback=callback
        )
        
        return self.cmd_queue.submit(cmd)
    
    # ========== 指令路由 ==========
    
    def _route_intent(self, intent: str, params: Dict[str, Any]) -> Any:
        """将意图路由到对应的插件"""
        for plugin in self.plugins.values():
            if intent in plugin.get_supported_intents():
                return plugin.execute(intent, params)
        
        print(f"[Brain] 未找到处理意图 {intent} 的插件")
        return None
    
    # ========== 主循环 ==========
    
    def _main_loop(self) -> None:
        """主循环"""
        print("[Brain] 主循环已启动")
        
        while self._running:
            # 超时检测：AWAKE状态超过配置秒数无交互自动回到IDLE
            if self.sm.state == RobotState.AWAKE:
                # 检查TTS是否正在播放（播放中不应进入休眠）
                tts_plugin = self.get_plugin("tts")
                tts_running = getattr(tts_plugin, '_running', False) if tts_plugin else False
                
                if not tts_running:
                    elapsed = time.time() - self._awake_start_time
                    if elapsed > self.awake_timeout:
                        print(f"[Brain] AWAKE超时{self.awake_timeout}秒，自动休眠")
                        self.sm.transition_to(RobotState.IDLE)
            
            time.sleep(self._idle_check_interval)
    
    # ========== 外部语音接口 ==========
    
    def on_asr_result(self, text: str) -> None:
        """语音识别结果回调"""
        if self.sm.state != RobotState.AWAKE:
            print(f"[Brain] 当前状态 {self.sm.state.value} 不处理语音")
            return
        
        # 重置超时计时器
        self._awake_start_time = time.time()
        
        # 检测紧急停止词（最高优先级，打断但不退出AWAKE）
        for word in self.emergency_stop_words:
            if word in text:
                print(f"[Brain] 检测到紧急停止词: {word}")
                self.trigger_emergency_stop()
                return
        
        # 检测退出词
        for word in self.exit_words:
            if word in text:
                print(f"[Brain] 检测到退出词: {word}")
                self.sleep()
                return
        
        print(f"[Brain] 收到ASR结果: {text}")
        
        # 意图匹配：先本地关键词匹配，再LLM
        intent, params = self.intent_handler.match_intent(text)
        
        if intent != "NONE":
            # 本地指令，直接执行（无TTS播报）
            command_type = self._get_command_type_for_intent(intent)
            category = self.intent_handler.get_intent_category(intent)
            print(f"[Brain] ✓ 本地匹配成功")
            print(f"[Brain]   意图: {intent}")
            print(f"[Brain]   类别: {category}")
            print(f"[Brain]   指令类型: {command_type.name}")
            print(f"[Brain]   参数: {params}")
            self.submit_command(intent, params, command_type)
        else:
            # 未匹配到本地意图，走LLM处理
            print(f"[Brain] ✗ 未匹配到本地意图，进入LLM处理")
            self.submit_command("CHAT", {"text": text}, CommandType.CONCURRENT)
    
    def on_asr_stream_result(self, text: str, event_type: str) -> None:
        """流式语音识别结果回调
        Args:
            text: 识别到的文字
            event_type: 事件类型 ('partial' | 'sentence_end' | 'sentence_begin' | 'stream_end')
        """
        if self.sm.state != RobotState.AWAKE:
            return
        
        if event_type == "partial":
            # 实时部分结果，仅打印
            print(f"\r[Brain] 实时识别: {text}", end="")
            # 重置超时计时器
            self._awake_start_time = time.time()
            
        elif event_type == "sentence_begin":
            # 句子开始，重置状态
            print("\n[Brain] 检测到语音开始")
            
        elif event_type == "sentence_end":
            # 句子结束，进行意图匹配和处理
            print(f"\n[Brain] 收到完整句子: {text}")
            
            # 检测紧急停止词（最高优先级，打断但不退出AWAKE）
            for word in self.emergency_stop_words:
                if word in text:
                    print(f"[Brain] 检测到紧急停止词: {word}")
                    self.trigger_emergency_stop()
                    return
            
            # 检测退出词
            for word in self.exit_words:
                if word in text:
                    print(f"[Brain] 检测到退出词: {word}")
                    self.sleep()
                    return
            
            # 意图匹配：先本地关键词匹配，再LLM
            intent, params = self.intent_handler.match_intent(text)
            
            if intent != "NONE":
                # 本地指令，直接执行（无TTS播报）
                command_type = self._get_command_type_for_intent(intent)
                category = self.intent_handler.get_intent_category(intent)
                print(f"[Brain] ✓ 本地匹配成功")
                print(f"[Brain]   意图: {intent}")
                print(f"[Brain]   类别: {category}")
                print(f"[Brain]   指令类型: {command_type.name}")
                print(f"[Brain]   参数: {params}")
                self.submit_command(intent, params, command_type)
            else:
                # 未匹配到本地意图，走LLM处理
                print(f"[Brain] ✗ 未匹配到本地意图，进入LLM处理")
                # 调用LLM插件获取响应
                llm_plugin = self.get_plugin("llm")
                if llm_plugin:
                    import asyncio
                    response = asyncio.run(llm_plugin.chat(text))
                    
                    # 解析LLM响应（支持结构化意图或普通文本）
                    parsed = llm_plugin.parse_intent_response(response)
                    
                    if parsed["type"] == "intent":
                        # LLM识别到意图指令
                        intent = parsed["intent"]
                        params = parsed["params"]
                        response_text = parsed.get("response", "")
                        
                        print(f"[Brain] ✓ LLM识别到意图指令")
                        print(f"[Brain]   意图: {intent}")
                        print(f"[Brain]   参数: {params}")
                        print(f"[Brain]   执行指令...")
                        
                        # 打印对话回复（如果有）
                        if response_text:
                            print(f"[LLM] 回复: {response_text}")
                            # TTS播报回复
                            self._speak(response_text)
                        
                        # 获取指令类型并执行（使用LLM回复TTS，屏蔽本地默认播报）
                        command_type = self._get_command_type_for_intent(intent)
                        category = self.intent_handler.get_intent_category(intent)
                        print(f"[Brain]   类别: {category if category else 'LLM_INTENT'}")
                        print(f"[Brain]   指令类型: {command_type.name if command_type else 'UNKNOWN'}")
                        
                        # 提交指令执行（callback=None 避免本地TTS重复播报）
                        self.submit_command(intent, params, command_type, callback=None)
                    else:
                        # 普通文本回复
                        print(f"[LLM] 回复: {parsed['content']}")
                        # TTS播报回复
                        self._speak(parsed['content'])
                else:
                    print("[Brain] LLM插件未注册")
            
            # 重置超时计时器，等待下一次语音
            self._awake_start_time = time.time()
            
        elif event_type == "stream_end":
            # 流结束
            print("\n[Brain] ASR流结束")

    def _speak(self, text: str):
        """调用TTS播放文本"""
        tts_plugin = self.get_plugin("tts")
        if tts_plugin:
            tts_plugin.speak(text)
        else:
            print("[Brain] TTS插件未注册")


# ========== 测试代码 ==========
if __name__ == "__main__":
    from src.plugins.buzzer.plugin import BuzzerPlugin
    from src.plugins.led.plugin import LEDPlugin
    from src.plugins.voice.wake_plugin import WakePlugin
    from src.plugins.voice.asr_plugin import ASRPlugin
    from src.plugins.voice.llm_plugin import LLMPlugin
    from src.plugins.voice.tts_plugin import TTSPlugin
    from src.plugins.remote.plugin import RemotePlugin
    from src.plugins.camera.plugin import CameraPlugin
    from src.plugins.motor.plugin import MotorPlugin
    from src.plugins.ultrasonic.plugin import UltrasonicPlugin
    from src.plugins.system.plugin import SystemPlugin
    from src.plugins.actions.plugin import ActionsPlugin
    
    brain = RobotBrain()
    
    # 注册插件
    brain.register_plugin("buzzer", BuzzerPlugin())
    brain.register_plugin("led", LEDPlugin())
    brain.register_plugin("wake", WakePlugin())
    brain.register_plugin("asr", ASRPlugin())
    brain.register_plugin("llm", LLMPlugin())
    brain.register_plugin("tts", TTSPlugin())
    brain.register_plugin("remote", RemotePlugin())
    brain.register_plugin("camera", CameraPlugin())
    brain.register_plugin("motor", MotorPlugin())
    brain.register_plugin("ultrasonic", UltrasonicPlugin())
    brain.register_plugin("system", SystemPlugin())
    brain.register_plugin("actions", ActionsPlugin())
    
    # 设置 ASR-TTS 联动（ASR 可以打断 TTS）
    asr_plugin = brain.get_plugin("asr")
    tts_plugin = brain.get_plugin("tts")
    if asr_plugin and tts_plugin:
        asr_plugin.set_tts_plugin(tts_plugin)
        tts_plugin.set_asr_plugin(asr_plugin)
        print("[Brain] ASR-TTS 双向联动已设置")
    
    # 设置 LED-TTS 联动（TTS 播报时显示呼吸灯效果）
    led_plugin = brain.get_plugin("led")
    if led_plugin and tts_plugin:
        # 创建回调函数，将 TTS 事件传递给 LED
        def tts_callback(event_type):
            if event_type == "start":
                led_plugin.on_tts_start()
            elif event_type == "end":
                led_plugin.on_tts_end()
        
        tts_plugin.add_callback(tts_callback)
        print("[Brain] LED-TTS 联动已设置")
    
    # 启动大脑（会自动启动 wake 和 remote 插件）
    brain.start()
    # 启动避障插件
    ultrasonic_plugin = brain.get_plugin("ultrasonic")
    if ultrasonic_plugin:
        ultrasonic_plugin.start()
    
    # 启动ASR插件并设置回调
    asr_plugin = brain.get_plugin("asr")
    if asr_plugin:
        asr_plugin.set_callback(brain.on_asr_stream_result)
        print("\n" + "="*50)
        print("小派机器人已启动")
        print("远程控制: http://<树莓派IP>:5000")
        print("语音模式: 喊'小派'唤醒后开始语音识别")
        print("按 Ctrl+C 退出")
        print("="*50 + "\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在关闭...")
        if asr_plugin:
            asr_plugin.stop_listening()
        brain.stop()