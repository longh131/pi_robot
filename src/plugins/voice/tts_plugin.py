# src/plugins/voice/tts_plugin.py
import os
import sys
import io
import base64
import dashscope
import time
import requests
from dotenv import load_dotenv
from pathlib import Path
import pygame
import soundfile as sf
import numpy as np

ROOT_DIR = Path(__file__).parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 加载环境变量
load_dotenv(os.path.join(ROOT_DIR, '.env'))

from src.core.base_plugin import BasePlugin
from src.core.state import RobotState


class TTSPlugin(BasePlugin):
    def __init__(self):
        super().__init__("tts")

        # TTS 配置
        self.model = os.getenv("TTS_MODEL", "qwen3-tts-flash")
        self.voice = os.getenv("TTS_VOICE", "Cherry")

        # DashScope 配置
        dashscope.base_http_api_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

        # 初始化 pygame 播放器
        pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=512)

        # 播放状态
        self._running = False

        # 回调函数列表
        self._callbacks = []

        # ASR插件引用
        self._asr_plugin = None

        print(f"[TTSPlugin] 初始化完成，模型: {self.model}, 声音: {self.voice}")

    def set_asr_plugin(self, asr_plugin):
        """设置ASR插件引用"""
        self._asr_plugin = asr_plugin
        print(f"[TTSPlugin] ASR插件已设置")

    def add_callback(self, callback):
        """添加 TTS 状态变化回调"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def _notify_callbacks(self, event_type):
        """通知所有回调函数"""
        for callback in self._callbacks:
            try:
                callback(event_type)
            except Exception as e:
                print(f"[TTSPlugin] 回调执行失败: {e}")

    def execute(self, intent: str, params: dict):
        """执行TTS指令"""
        text = params.get("text", "")
        if text:
            self.speak(text)

    def get_supported_intents(self):
        return ["SPEAK"]

    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        self.stop()

    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        if new_state == RobotState.IDLE:
            self.stop()

    def _generate_and_play_stream(self, text):
        """流式生成并播放音频"""
        if not dashscope.api_key:
            print("[TTSPlugin] 警告: DASHSCOPE_API_KEY 未设置")
            return

        try:
            responses = dashscope.MultiModalConversation.call(
                model=self.model,
                text=text,
                voice=self.voice,
                stream=True
            )

            audio_buffer = bytearray()
            chunk_count = 0  # 音频片段计数器

            for response in responses:
                if not self._running:
                    print("[TTSPlugin] 检测到停止信号，退出流式播放")
                    break

                if response.output and 'audio' in response.output:
                    audio_info = response.output['audio']
                    if isinstance(audio_info, dict):
                        audio_data = audio_info.get('data')
                    else:
                        audio_data = audio_info

                    if audio_data:
                        if isinstance(audio_data, str):
                            audio_data = base64.b64decode(audio_data)

                        audio_buffer.extend(audio_data)

                        if len(audio_buffer) > 1024 * 256:
                            chunk_count += 1
                            if self._running:
                                self._play_audio_chunk(bytes(audio_buffer), chunk_count)
                            audio_buffer = bytearray()

            if self._running and len(audio_buffer) > 0:
                chunk_count += 1
                self._play_audio_chunk(bytes(audio_buffer), chunk_count)

        except Exception as e:
            print(f"[TTSPlugin] 流式播放失败: {e}")
            import traceback
            traceback.print_exc()

    def _play_audio_chunk(self, audio_bytes, chunk_index=0):
        """播放音频片段（直接处理原始PCM数据）"""
        try:
            if not self._running:
                return

            pcm_data = np.frombuffer(audio_bytes, dtype=np.int16).copy()
            
            # 修复：第一个片段开头可能有异常采样值，用静音替换
            if chunk_index == 1 and len(pcm_data) > 10:
                # 检测开头是否有突变（第一个采样值超过阈值）
                if abs(pcm_data[0]) > 10000:
                    # 找到稳定区域（连续5个采样值都小于5000）
                    stable_idx = 0
                    consecutive_good = 0
                    for i in range(min(2000, len(pcm_data))):
                        if abs(pcm_data[i]) < 5000:
                            consecutive_good += 1
                            if consecutive_good >= 5:
                                stable_idx = i - 4
                                break
                        else:
                            consecutive_good = 0
                    
                    if stable_idx > 0:
                        print(f"[TTSPlugin] 静音替换开头异常采样: {stable_idx}个")
                        pcm_data[:stable_idx] = 0
            
            sound = pygame.mixer.Sound(pcm_data)
            sound.play()

            while pygame.mixer.get_busy() and self._running:
                time.sleep(0.01)

        except Exception as e:
            print(f"[TTSPlugin] 播放音频片段失败: {e}")

    def speak(self, text: str):
        """播放文本（流式）"""
        if not text.strip():
            return

        print(f"[TTSPlugin] 开始播放: {text}")

        # 清理可能的残留音频
        pygame.mixer.stop()
        print("[TTSPlugin] 已清理残留音频")
        time.sleep(0.02)

        self._running = True

        if self._asr_plugin:
            setattr(self._asr_plugin, '_interrupted_this_cycle', False)

        self._notify_callbacks("start")

        try:
            self._generate_and_play_stream(text)

            if self._running:
                print("[TTSPlugin] 播放完成")
            else:
                print("[TTSPlugin] 播放被停止")

        except Exception as e:
            print(f"[TTSPlugin] 播放异常: {e}")
        finally:
            self._running = False
            self._notify_callbacks("end")

    def stop(self):
        """停止播放"""
        if not self._running:
            return

        self._running = False

        try:
            pygame.mixer.stop()
        except:
            pass
