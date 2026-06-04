# src/core/intent_handler.py
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
import json
from loguru import logger

from src.core.intent_keywords import KEYWORD_PRIORITY, INTENT_ENUM, INTENT_CATEGORIES


class IntentHandler:
    """意图处理器 - 按优先级匹配本地意图关键词"""
    
    def __init__(self):
        self._nicknames = self._load_nicknames()
        logger.info(f"[IntentHandler] 初始化意图处理器，加载昵称: {self._nicknames}")
    
    def _load_nicknames(self) -> list:
        """从配置文件加载昵称"""
        try:
            root_dir = Path(__file__).parent.parent.parent
            config_path = root_dir / "data" / "robot_profile.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("robot", {}).get("nickname", [])
        except Exception as e:
            logger.warning(f"[IntentHandler] 加载昵称配置失败: {e}")
            return ["小派", "派派"]
    
    def has_nickname(self, text: str) -> bool:
        """检查文本是否包含昵称"""
        for nickname in self._nicknames:
            if nickname in text:
                return True
        return False
    
    def extract_after_nickname(self, text: str) -> str:
        """提取昵称后面的内容"""
        for nickname in self._nicknames:
            if nickname in text:
                index = text.find(nickname) + len(nickname)
                return text[index:].strip()
        return text
    
    def match_intent(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        根据文本匹配意图（需要先喊昵称）
        
        Args:
            text: 用户输入的文本
        
        Returns:
            (intent, params): 意图名称和参数
        """
        if not text or not isinstance(text, str):
            return "NONE", {}
        
        text = text.strip()
        
        # 检查是否包含昵称
        if not self.has_nickname(text):
            logger.info(f"[IntentHandler] 未检测到昵称，走LLM处理")
            return "NONE", {}
        
        # 提取昵称后面的内容进行意图匹配
        content = self.extract_after_nickname(text)
        
        # 按优先级顺序匹配
        for keywords_dict in KEYWORD_PRIORITY:
            for intent, keywords in keywords_dict.items():
                for keyword in keywords:
                    if keyword in content:
                        logger.info(f"[IntentHandler] 匹配到意图: {intent} (关键词: {keyword})")
                        return intent, {"matched_keyword": keyword, "nickname_detected": True}
        
        # 未匹配到任何本地意图
        logger.info(f"[IntentHandler] 未匹配到本地意图，走LLM处理")
        return "NONE", {"nickname_detected": True}
    
    def is_valid_intent(self, intent: str) -> bool:
        """检查意图是否在枚举列表中"""
        return intent in INTENT_ENUM
    
    def get_intent_category(self, intent: str) -> str:
        """获取意图所属类别"""
        for category, intents in INTENT_CATEGORIES.items():
            if intent in intents:
                return category
        return "CHAT"
    
    def parse_llm_output(self, llm_output: str) -> Tuple[str, Dict[str, Any]]:
        """
        解析LLM结构化输出
        
        Args:
            llm_output: LLM返回的JSON格式字符串
        
        Returns:
            (intent, params): 意图名称和参数
        """
        try:
            import json
            data = json.loads(llm_output)
            intent = data.get("intent", "NONE")
            params = data.get("params", {})
            
            if self.is_valid_intent(intent):
                logger.info(f"[IntentHandler] LLM输出解析成功: {intent}")
                return intent, params
            else:
                logger.warning(f"[IntentHandler] LLM返回无效意图: {intent}")
                return "NONE", {}
        except json.JSONDecodeError:
            logger.warning(f"[IntentHandler] LLM输出不是有效JSON: {llm_output}")
            return "NONE", {}
        except Exception as e:
            logger.error(f"[IntentHandler] 解析LLM输出异常: {e}")
            return "NONE", {}
