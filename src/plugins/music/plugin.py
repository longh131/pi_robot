from typing import Any, Dict, List, Optional
from src.core.base_plugin import BasePlugin
import os
import threading
import time
import random


class MusicPlugin(BasePlugin):
    def __init__(self):
        super().__init__("music")
        self._music_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'music')
        self._current_index = -1
        self._is_playing = False
        self._is_paused = False
        self._pygame_initialized = False
        self._player_thread = None
        self._stop_event = threading.Event()
        self._music_list = []

    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "PLAY_MUSIC":
            return self._play_music(params)
        elif intent == "PAUSE_MUSIC":
            return self._pause_music()
        elif intent == "STOP_MUSIC":
            return self._stop_music()
        elif intent == "NEXT_SONG":
            return self._next_song()
        elif intent == "PREV_SONG":
            return self._prev_song()
        elif intent == "RESUME_MUSIC":
            return self._resume_music()
        elif intent == "LIST_MUSIC":
            return self._list_music()
        return None

    def get_supported_intents(self) -> list:
        return ["PLAY_MUSIC", "PAUSE_MUSIC", "STOP_MUSIC", "NEXT_SONG", "PREV_SONG", "RESUME_MUSIC", "LIST_MUSIC"]

    def _init_pygame(self):
        if not self._pygame_initialized:
            try:
                import pygame
                pygame.mixer.init()
                self._pygame_initialized = True
            except Exception as e:
                print(f"[MusicPlugin] 初始化pygame失败: {e}")
                return False
        return True

    def _load_music_list(self) -> List[str]:
        music_files = []
        if os.path.exists(self._music_dir):
            for filename in os.listdir(self._music_dir):
                filepath = os.path.join(self._music_dir, filename)
                if os.path.isfile(filepath) and (filename.endswith('.mp3') or filename.endswith('.wav')):
                    music_files.append(filename)
        self._music_list = sorted(music_files)
        return self._music_list

    def _play_music(self, params: Dict[str, Any]) -> str:
        if not self._init_pygame():
            return "音乐播放初始化失败"
        
        music_list = self._load_music_list()
        if not music_list:
            return "音乐目录为空"
        
        song_name = params.get('song_name', '')
        
        if song_name:
            found = False
            for i, filename in enumerate(music_list):
                if song_name in filename:
                    self._current_index = i
                    found = True
                    break
            if not found:
                return f"未找到歌曲: {song_name}"
        else:
            if self._current_index < 0 or self._current_index >= len(music_list):
                self._current_index = random.randint(0, len(music_list) - 1)
        
        if self._is_playing:
            self._stop_music()
        
        self._is_playing = True
        self._is_paused = False
        self._stop_event.clear()
        
        filepath = os.path.join(self._music_dir, music_list[self._current_index])
        
        try:
            import pygame
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            self._player_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self._player_thread.start()
            
            return f"正在播放: {music_list[self._current_index]}"
        except Exception as e:
            print(f"[MusicPlugin] 播放音乐失败: {e}")
            self._is_playing = False
            return "播放音乐失败"

    def _playback_loop(self):
        import pygame
        while self._is_playing and not self._stop_event.is_set():
            if not pygame.mixer.music.get_busy() and not self._is_paused:
                self._next_song()
            time.sleep(0.5)

    def _pause_music(self) -> str:
        if not self._is_playing:
            return "没有正在播放的音乐"
        
        try:
            import pygame
            pygame.mixer.music.pause()
            self._is_paused = True
            return "音乐已暂停"
        except Exception as e:
            print(f"[MusicPlugin] 暂停音乐失败: {e}")
            return "暂停音乐失败"

    def _resume_music(self) -> str:
        if not self._is_playing or not self._is_paused:
            return "音乐未暂停"
        
        try:
            import pygame
            pygame.mixer.music.unpause()
            self._is_paused = False
            return "音乐已继续播放"
        except Exception as e:
            print(f"[MusicPlugin] 继续播放失败: {e}")
            return "继续播放失败"

    def _stop_music(self) -> str:
        self._is_playing = False
        self._is_paused = False
        self._stop_event.set()
        
        try:
            import pygame
            pygame.mixer.music.stop()
            return "音乐已停止"
        except Exception as e:
            print(f"[MusicPlugin] 停止音乐失败: {e}")
            return "停止音乐失败"

    def _next_song(self) -> str:
        music_list = self._load_music_list()
        if not music_list:
            return "音乐目录为空"
        
        self._current_index = random.randint(0, len(music_list) - 1)
        
        self._is_paused = False
        filepath = os.path.join(self._music_dir, music_list[self._current_index])
        
        try:
            import pygame
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            return f"下一首: {music_list[self._current_index]}"
        except Exception as e:
            print(f"[MusicPlugin] 切歌失败: {e}")
            return "切歌失败"

    def _prev_song(self) -> str:
        music_list = self._load_music_list()
        if not music_list:
            return "音乐目录为空"
        
        if self._current_index <= 0:
            self._current_index = len(music_list) - 1
        else:
            self._current_index -= 1
        
        self._is_paused = False
        filepath = os.path.join(self._music_dir, music_list[self._current_index])
        
        try:
            import pygame
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            return f"上一首: {music_list[self._current_index]}"
        except Exception as e:
            print(f"[MusicPlugin] 切歌失败: {e}")
            return "切歌失败"

    def _list_music(self) -> str:
        music_list = self._load_music_list()
        if not music_list:
            return "音乐目录为空"
        
        message = "可用音乐:"
        for i, filename in enumerate(music_list[:10], 1):
            message += f"{i}. {filename}；"
        if len(music_list) > 10:
            message += f"还有{len(music_list) - 10}首..."
        return message.rstrip('；')