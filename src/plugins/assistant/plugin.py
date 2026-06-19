from typing import Any, Dict, Optional
from src.core.base_plugin import BasePlugin
import json
import os
import threading
import time
from datetime import datetime, timedelta


class AssistantPlugin(BasePlugin):
    def __init__(self):
        super().__init__("assistant")
        self._reminders = []
        self._timers = {}
        self._timer_counter = 0
        self._data_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'reminders.json')
        self._load_reminders()

    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "REMINDER_SET":
            return self._set_reminder(params)
        elif intent == "REMINDER_QUERY":
            return self._query_reminders(params)
        elif intent == "REMINDER_DELETE":
            return self._delete_reminder(params)
        elif intent == "TIMER_SET":
            return self._set_timer(params)
        elif intent == "TIMER_STOP":
            return self._stop_timer(params)
        elif intent == "ALARM_SET":
            return self._set_alarm(params)
        return None

    def get_supported_intents(self) -> list:
        return ["REMINDER_SET", "REMINDER_QUERY", "REMINDER_DELETE", "TIMER_SET", "TIMER_STOP", "ALARM_SET"]

    def _load_reminders(self):
        try:
            if os.path.exists(self._data_file):
                with open(self._data_file, 'r', encoding='utf-8') as f:
                    self._reminders = json.load(f)
        except Exception as e:
            print(f"[AssistantPlugin] 加载提醒失败: {e}")
            self._reminders = []

    def _save_reminders(self):
        try:
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(self._reminders, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AssistantPlugin] 保存提醒失败: {e}")

    def _set_reminder(self, params: Dict[str, Any]) -> str:
        # 支持多种参数名
        content = params.get('content', '') or params.get('message', '') or params.get('event', '')
        time_str = params.get('time', '')
        
        # 支持 duration + unit 格式
        if not time_str and 'duration' in params:
            duration = params['duration']
            unit = params.get('unit', '秒')
            time_str = f"{duration}{unit}"
        
        if not content:
            return "请告诉我提醒内容"
        if not time_str:
            return "请告诉我提醒时间"
        
        try:
            now = datetime.now()
            
            if '秒' in time_str:
                seconds = int(time_str.replace('秒', '').strip())
                reminder_time = now + timedelta(seconds=seconds)
            elif '分钟' in time_str:
                minutes = int(time_str.replace('分钟', '').strip())
                reminder_time = now + timedelta(minutes=minutes)
            elif '小时' in time_str:
                hours = int(time_str.replace('小时', '').strip())
                reminder_time = now + timedelta(hours=hours)
            elif ':' in time_str:
                time_parts = time_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if reminder_time <= now:
                    reminder_time += timedelta(days=1)
            else:
                return "时间格式不正确，请说'5分钟后'或'14:30'"
            
            reminder = {
                'id': len(self._reminders) + 1,
                'content': content,
                'time': reminder_time.isoformat(),
                'status': 'pending',
                'created_at': now.isoformat()
            }
            self._reminders.append(reminder)
            self._save_reminders()
            
            delay = (reminder_time - now).total_seconds()
            if delay > 0:
                timer = threading.Timer(delay, self._trigger_reminder, args=[reminder])
                timer.start()
            
            return f"已设置提醒：{content}，时间是{reminder_time.strftime('%H:%M')}"
        except Exception as e:
            print(f"[AssistantPlugin] 设置提醒失败: {e}")
            return "设置提醒失败"

    def _trigger_reminder(self, reminder):
        reminder['status'] = 'triggered'
        self._save_reminders()
        if self._brain:
            self._brain._speak(f"提醒：{reminder['content']}")
        else:
            print(f"[AssistantPlugin] 提醒触发：{reminder['content']}")

    def _query_reminders(self, params: Dict[str, Any]) -> str:
        pending = [r for r in self._reminders if r['status'] == 'pending']
        if not pending:
            return "当前没有待办提醒"
        
        message = "待办提醒："
        for i, r in enumerate(pending[:5], 1):
            time_obj = datetime.fromisoformat(r['time'])
            message += f"{i}. {r['content']} ({time_obj.strftime('%H:%M')})；"
        return message.rstrip('；')

    def _delete_reminder(self, params: Dict[str, Any]) -> str:
        content = params.get('content', '')
        if not content:
            return "请告诉我要删除的提醒内容"
        
        before_count = len(self._reminders)
        self._reminders = [r for r in self._reminders if content not in r['content']]
        after_count = len(self._reminders)
        
        if before_count > after_count:
            self._save_reminders()
            return f"已删除{before_count - after_count}条提醒"
        else:
            return "未找到匹配的提醒"

    def _set_timer(self, params: Dict[str, Any]) -> str:
        duration_value = params.get('duration', '')
        if not duration_value:
            return "请告诉我计时时长"
        
        try:
            # 支持整数（秒）或字符串格式
            if isinstance(duration_value, int):
                seconds = duration_value
                duration_str = f"{seconds}秒"
            elif isinstance(duration_value, str):
                duration_str = duration_value
                if '分钟' in duration_str:
                    seconds = int(duration_str.replace('分钟', '').strip()) * 60
                elif '秒' in duration_str:
                    seconds = int(duration_str.replace('秒', '').strip())
                elif '小时' in duration_str:
                    seconds = int(duration_str.replace('小时', '').strip()) * 3600
                else:
                    return "时间格式不正确，请说'5分钟'或'30秒'"
            else:
                return "时间格式不正确，请说'5分钟'或'30秒'"
            
            if seconds <= 0:
                return "时间必须大于0"
            
            self._timer_counter += 1
            timer_id = self._timer_counter
            
            timer = threading.Timer(seconds, self._trigger_timer, args=[timer_id])
            timer.start()
            self._timers[timer_id] = {'timer': timer, 'duration': seconds}
            
            return f"已开始计时，时长{duration_str}"
        except Exception as e:
            print(f"[AssistantPlugin] 设置计时器失败: {e}")
            return "设置计时器失败"

    def _trigger_timer(self, timer_id):
        if timer_id in self._timers:
            del self._timers[timer_id]
            if self._brain:
                self._brain._speak("时间到")
            else:
                print("[AssistantPlugin] 计时器触发：时间到")

    def _stop_timer(self, params: Dict[str, Any]) -> str:
        if not self._timers:
            return "当前没有正在运行的计时器"
        
        for timer_info in self._timers.values():
            timer_info['timer'].cancel()
        self._timers.clear()
        
        return "已停止所有计时器"

    def _set_alarm(self, params: Dict[str, Any]) -> str:
        time_str = params.get('time', '')
        content = params.get('content', '')
        
        if not time_str:
            return "请告诉我闹钟时间"
        
        try:
            now = datetime.now()
            
            if ':' in time_str:
                time_parts = time_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if alarm_time <= now:
                    alarm_time += timedelta(days=1)
            else:
                return "时间格式不正确，请说'07:30'"
            
            reminder = {
                'id': len(self._reminders) + 1,
                'content': content if content else '闹钟',
                'time': alarm_time.isoformat(),
                'status': 'pending',
                'type': 'alarm',
                'created_at': now.isoformat()
            }
            self._reminders.append(reminder)
            self._save_reminders()
            
            delay = (alarm_time - now).total_seconds()
            if delay > 0:
                timer = threading.Timer(delay, self._trigger_alarm, args=[reminder])
                timer.start()
            
            return f"已设置闹钟：{alarm_time.strftime('%H:%M')}"
        except Exception as e:
            print(f"[AssistantPlugin] 设置闹钟失败: {e}")
            return "设置闹钟失败"

    def _trigger_alarm(self, reminder):
        reminder['status'] = 'triggered'
        self._save_reminders()
        if self._brain:
            self._brain._speak(f"闹钟响了！{reminder['content']}")
        else:
            print(f"[AssistantPlugin] 闹钟触发：{reminder['content']}")