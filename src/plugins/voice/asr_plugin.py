# src/plugins/voice/asr_plugin.py
import os
import time
import numpy as np
import sounddevice as sd
import dashscope
from dotenv import load_dotenv
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.base_plugin import BasePlugin

load_dotenv(os.path.join(ROOT_DIR, '.env'))

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

# 音频参数
SAMPLE_RATE = 16000
CHANNELS = 1


class MyASRCallback(RecognitionCallback):
    """处理来自ASR服务器的实时事件"""
    def __init__(self, plugin: 'ASRPlugin'):
        super().__init__()
        self.plugin = plugin
        self._last_text = ""  # 保存最后识别到的文字

    def on_event(self, result: RecognitionResult):
        """处理识别事件"""
        sentence = result.get_sentence()
        if sentence:
            text = sentence.get('text', '')
            self._last_text = text  # 保存最后识别结果
            self.plugin._final_result = text  # 更新最终结果
            self.plugin._last_receive_time = time.time()  # 更新接收时间
            if self.plugin._callback:
                self.plugin._callback(text, "partial")
            print(f"\r[ASR] 实时识别: {text}", end="", flush=True)

    def on_complete(self):
        """识别完成"""
        print("\n[ASR] 识别完成（SDK回调）")
        # 注意：不发送sentence_end，因为start_listening中的循环会处理

    def on_error(self, result: RecognitionResult):
        """识别错误"""
        # 过滤常见的正常错误
        if result.message and "NO_VALID_AUDIO_ERROR" in result.message:
            # 无有效音频输入，属于正常边界情况，不打印错误
            return
        print(f"\n[ASR] 识别错误: {result.message}")
        # 不发送error回调，避免重复处理


class ASRPlugin(BasePlugin):
    def __init__(self):
        super().__init__("asr")
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.model = os.getenv("ASR_MODEL", "paraformer-realtime-v2")
        
        self._running = False
        self._recognition = None
        self._audio_stream = None
        self._callback = None
        self._final_result = ""
        self._is_completed = False
        self._tts_plugin = None  # TTS插件引用，用于打断

        print(f"[ASRPlugin] 初始化完成，模型: {self.model}")

    # 必须实现的 BasePlugin 抽象方法
    def execute(self, intent: str, params: dict):
        pass

    def get_supported_intents(self):
        return []

    def on_load(self) -> None:
        """插件加载时由 Brain 调用"""
        pass
        
    def on_unload(self) -> None:
        """插件卸载时由 Brain 调用"""
        self.stop_listening()

    def set_callback(self, callback):
        """设置识别结果的回调函数"""
        self._callback = callback

    def set_tts_plugin(self, tts_plugin):
        """设置TTS插件引用（用于打断）"""
        self._tts_plugin = tts_plugin

    def _interrupt_tts(self):
        """打断正在播放的TTS"""
        print(f"[ASRPlugin] _interrupt_tts 被调用")
        if self._tts_plugin:
            print("[ASRPlugin] TTS插件存在")
            # 检查TTS状态
            tts_running = getattr(self._tts_plugin, '_running', False)
            print(f"[ASRPlugin] TTS._running = {tts_running}")
            self._tts_plugin.stop()
            print("[ASRPlugin] TTS.stop() 已调用")
        else:
            print("[ASRPlugin] TTS插件未设置")

    def start_listening(self):
        """开始录音和识别"""
        if not self.api_key:
            print("[ASRPlugin] 错误: 未设置 DASHSCOPE_API_KEY")
            return

        self._running = True
        self._last_receive_time = time.time()
        print("[ASRPlugin] 开始监听麦克风...")
        
        # 打断正在播放的TTS
        self._interrupt_tts()
        
        # 启动音频流（只启动一次）
        if self._audio_stream is None:
            self._audio_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype='int16',
                blocksize=3200,
                callback=self._audio_callback
            )
            self._audio_stream.start()
        
        # 循环处理多次识别
        while self._running:
            try:
                # 重置状态
                self._final_result = ""
                self._is_completed = False
                self._last_text = ""
                self._interrupted_this_cycle = False  # 重置打断标志
                
                # 停止之前的Recognition实例（如果还在运行）
                if self._recognition:
                    try:
                        self._recognition.stop()
                    except:
                        pass
                
                # 创建新的识别实例
                callback = MyASRCallback(self)
                self._recognition = Recognition(
                    model=self.model,
                    format='pcm',
                    sample_rate=SAMPLE_RATE,
                    callback=callback
                )
                
                # 启动识别
                self._recognition.start()
                self._last_receive_time = time.time()
                print("\n[ASRPlugin] ASR服务已启动")
                
                # 等待识别完成或超时
                timeout = 10  # 最大等待时间（秒）
                while self._running and not self._is_completed:
                    elapsed = time.time() - self._last_receive_time
                    if self._final_result and elapsed > 1.5:  # 1.5秒无新结果则结束
                        break
                    elif elapsed > timeout:  # 超时退出
                        break
                    time.sleep(0.1)
                
                # 识别完成后，发送最终结果回调
                if self._running and self._final_result:
                    print(f"\n[ASRPlugin] 发送最终识别结果: {self._final_result}")
                    if self._callback:
                        self._callback(self._final_result, "sentence_end")
                
            except Exception as e:
                import traceback
                print(f"\n[ASRPlugin] 识别异常: {e}")
                print(f"[ASRPlugin] 错误详情: {traceback.format_exc()}")
                self._cleanup()
                break

    def stop_listening(self):
        """停止录音并关闭连接"""
        if not self._running and not self._recognition:
            return
            
        print("[ASRPlugin] 停止监听...")
        self._cleanup()
        print("[ASRPlugin] 监听已停止，连接已关闭。")

    def _cleanup(self):
        """清理资源"""
        self._running = False
        
        if self._audio_stream:
            try:
                self._audio_stream.stop()
                self._audio_stream.close()
            except:
                pass
            self._audio_stream = None
            
        if self._recognition:
            try:
                self._recognition.stop()
            except:
                pass
            self._recognition = None

    def _audio_callback(self, indata, frames, time_info, status):
        """音频流回调，持续发送音频数据"""
        if status:
            print(f"\n[ASRPlugin] 音频流状态: {status}")
            
        if self._running and self._recognition and not self._is_completed:
            # 检测音频输入并打断 TTS（只在刚开始有声音时打断一次）
            if not self._interrupted_this_cycle:
                # 检测是否有有效音频（音量大于阈值）
                audio_level = np.abs(indata).mean()
                if audio_level > 180:  # 提高阈值，过滤环境噪音
                    print(f"[ASRPlugin] 检测到语音(音量:{audio_level:.1f})，打断TTS")
                    self._interrupt_tts()
                    self._interrupted_this_cycle = True
            
            try:
                self._recognition.send_audio_frame(indata.tobytes())
            except Exception as e:
                print(f"[ASRPlugin] 发送音频帧异常: {e}")
            except Exception as e:
                error_str = str(e)
                # 过滤常见的正常结束错误
                if "Speech recognition has stopped" in error_str:
                    # 识别正常停止，无需打印错误
                    self._is_completed = True
                elif "NO_VALID_AUDIO" in error_str:
                    # 无有效音频输入，属于正常边界情况
                    self._is_completed = True
                elif "Unauthorized" in error_str:
                    print(f"\n[ASRPlugin] 认证错误，请检查 DASHSCOPE_API_KEY")
                    self._is_completed = True
                elif "connection" in error_str.lower():
                    print(f"\n[ASRPlugin] 连接已断开: {e}")
                    self._is_completed = True
                else:
                    print(f"\n[ASRPlugin] 音频发送异常: {e}")
                    self._is_completed = True

    def on_state_change(self, old_state: Any, new_state: Any) -> None:
        """状态变化时处理"""
        state_value = getattr(new_state, 'value', new_state)
        
        if state_value == "awake":
            print("[ASRPlugin] 检测到进入AWAKE状态，启动监听")
            self.start_listening()
        elif state_value == "idle":
            print("[ASRPlugin] 检测到进入IDLE状态，停止监听")
            self.stop_listening()