from typing import Any, Dict
from datetime import datetime
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from src.core.base_plugin import BasePlugin


class QueryPlugin(BasePlugin):
    def __init__(self):
        super().__init__("query")
        # 加载 .env 文件
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        load_dotenv(env_path)
        
        self.weather_api_key = os.getenv("QATHER_API_KEY", "")
        self.weather_id = os.getenv("QATHER_ID", "")
        self.news_api_key = os.getenv("TIANAPI_API_KEY", "")
        
        # 调试打印
        print(f"[QueryPlugin] .env 路径: {env_path}")
        print(f"[QueryPlugin] .env 文件存在: {env_path.exists()}")
        print(f"[QueryPlugin] weather_api_key: {self.weather_api_key[:10] + '...' if self.weather_api_key else '未配置'}")
        print(f"[QueryPlugin] news_api_key: {self.news_api_key[:10] + '...' if self.news_api_key else '未配置'}")

    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        if intent == "TIME_QUERY":
            return self._query_time()
        elif intent == "DATE_QUERY":
            return self._query_date()
        elif intent == "WEATHER_QUERY":
            return self._query_weather(params)
        elif intent == "NEWS_QUERY":
            return self._query_news(params)
        return None

    def get_supported_intents(self) -> list:
        return ["TIME_QUERY", "DATE_QUERY", "WEATHER_QUERY", "NEWS_QUERY"]

    def _query_time(self) -> str:
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        if 5 <= hour < 12:
            time_period = "上午"
        elif 12 <= hour < 14:
            time_period = "中午"
        elif 14 <= hour < 18:
            time_period = "下午"
        elif 18 <= hour < 22:
            time_period = "晚上"
        else:
            time_period = "深夜"
        
        message = f"现在是{time_period}{hour}点{minute}分。"
        print(f"【时间查询】{message}")
        return message

    def _query_date(self) -> str:
        now = datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekdays[now.weekday()]
        
        message = f"今天是{now.year}年{now.month}月{now.day}日，{weekday}。"
        print(f"【日期查询】{message}")
        return message

    def _query_weather(self, params: Dict[str, Any]) -> str:
        city = params.get('city', '') or params.get('location', '') or 'Beijing'
        
        try:
            # 使用 wttr.in 免费天气服务（无需API Key）
            # 城市名支持中文和英文
            url = f"https://wttr.in/{city}?format=j1"
            print(f"【天气查询】请求URL: {url}")
            response = requests.get(url, timeout=10)
            print(f"【天气查询】状态码: {response.status_code}")
            print(f"【天气查询】响应内容: {response.text[:300]}")
            
            try:
                data = response.json()
            except Exception as e:
                print(f"【天气查询】JSON解析失败: {e}")
                return "天气查询失败"
            
            print(f"【天气查询】data: {data}")
            
            if response.status_code == 200 and data.get('current_condition'):
                condition = data['current_condition'][0]
                temp = condition['temp_C']
                feels_like = condition['FeelsLikeC']
                text = condition['weatherDesc'][0]['value']
                humidity = condition['humidity']
                city_name = data.get('nearest_area', [{}])[0].get('areaName', [{}])[0].get('value', city)
                
                message = f"{city_name}当前温度{temp}度，体感温度{feels_like}度，{text}，湿度{humidity}%。"
                print(f"【天气查询】{message}")
                return message
            else:
                message = f"天气查询失败，无法获取{city}的天气信息。"
                print(f"【天气查询】{message}")
                return message
        except Exception as e:
            print(f"[QueryPlugin] 天气查询失败: {e}")
            return "天气查询失败"

    def _query_news(self, params: Dict[str, Any]) -> str:
        category = params.get('category', '头条')
        
        if not self.news_api_key:
            message = f"新闻查询功能未配置API密钥。"
            print(f"【新闻查询】{message}")
            return message
        
        try:
            url = f"https://apis.tianapi.com/toutiaohot/index?key={self.news_api_key}"
            print(f"【新闻查询】请求URL: {url}")
            response = requests.get(url, timeout=5)
            print(f"【新闻查询】状态码: {response.status_code}")
            print(f"【新闻查询】响应内容: {response.text[:200]}")
            
            try:
                data = response.json()
            except Exception as e:
                print(f"【新闻查询】JSON解析失败: {e}")
                return "新闻查询失败"
            
            print(f"【新闻查询】data: {data}")
            
            if data.get('code') == 200:
                news_list = data['result'].get('list', data['result'].get('newslist', []))
                news_text = "。".join([n.get('word', n.get('title', '')) for n in news_list[:3]])
                message = f"今日头条：{news_text}。"
                print(f"【新闻查询】{message}")
                return message
            else:
                message = f"新闻查询失败，错误码: {data.get('code')}。"
                print(f"【新闻查询】{message}")
                return message
        except Exception as e:
            print(f"[QueryPlugin] 新闻查询失败: {e}")
            return "新闻查询失败"