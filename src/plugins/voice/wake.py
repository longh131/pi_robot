import json
import os
import sys
import time
import numpy as np
import sounddevice as sd
import sherpa_onnx
from pathlib import Path

# 动态添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
# 动态获取项目根目录 (pi/)
BASE_DIR = str(ROOT_DIR)
PROFILE_PATH = os.path.join(BASE_DIR, "data/robot_profile.json")
MODEL_DIR = os.path.join(BASE_DIR, "models/asr/streaming_model")
SAMPLE_RATE = 16000

class WakeEngine:
    def __init__(self):
        self.wake_words = self._load_wake_words()
        self.recognizer = self._init_recognizer()

    def _load_wake_words(self) -> list:
        try:
            with open(PROFILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("robot", {}).get("wake_words", [])
        except Exception as e:
            print(f"Error loading profile at {PROFILE_PATH}: {e}")
            return []

    def _init_recognizer(self):
        try:
            # 适配你列表中的 int8 文件名
            recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                tokens=os.path.join(MODEL_DIR, "tokens.txt"),
                encoder=os.path.join(MODEL_DIR, "encoder-epoch-99-avg-1.onnx"),
                decoder=os.path.join(MODEL_DIR, "decoder-epoch-99-avg-1.onnx"),
                joiner=os.path.join(MODEL_DIR, "joiner-epoch-99-avg-1.onnx"),
                num_threads=4, # 树莓派5B性能强劲，可适当增加线程
                sample_rate=SAMPLE_RATE,
                feature_dim=80,
            )
            return recognizer
        except Exception as e:
            print(f"Recognizer init failed: {e}")
            sys.exit(1)

    def listen_and_wake(self, stop_check=None) -> bool:
        if not self.wake_words:
            return False

        stream = self.recognizer.create_stream()

        def audio_callback(indata, frames, time, status):
            samples = indata.reshape(-1).astype(np.float32)
            stream.accept_waveform(SAMPLE_RATE, samples)

        try:
            with sd.InputStream(channels=1, dtype='float32', samplerate=SAMPLE_RATE, callback=audio_callback):
                while True:
                    # 检查是否需要停止（状态改变时）
                    if stop_check and stop_check():
                        self.recognizer.reset(stream)
                        return False
                    
                    if self.recognizer.is_ready(stream):
                        self.recognizer.decode_stream(stream)
                    
                    text = self.recognizer.get_result(stream).strip()
                    if text:
                        for word in self.wake_words:
                            if word in text:
                                self.recognizer.reset(stream)
                                return True
                    time.sleep(0.01)
        except Exception as e:
            print(f"Audio stream error: {e}")
            return False
