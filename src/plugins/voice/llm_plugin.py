import os
import time
import json
import asyncio
from openai import OpenAI
from src.core.base_plugin import BasePlugin
from src.core.intent_keywords import INTENT_ENUM, INTENT_ALIAS_MAP
from src.core.memory_manager import MemoryManager

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../../../data/robot_profile.json")


def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[LLMPlugin] 加载配置文件失败：{e}")
        return {}


class LLMPlugin(BasePlugin):
    def __init__(self):
        super().__init__("llm")
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1"
        self.model = "deepseek-chat"
        self._client = None
        self._fallback_index = 0
        
        # 加载配置
        config = load_config()
        conversation_config = config.get("conversation", {})
        personality_config = config.get("personality", {})
        
        # 短期记忆：对话历史（从配置读取最大长度）
        self._history = []
        self._max_history_length = conversation_config.get("max_history", 10)
        
        # 系统提示词（从配置读取）
        self._system_prompt = personality_config.get("system_prompt", "")
        
        # 兜底回复（从配置读取）
        self._fallback_responses = conversation_config.get("fallback_responses", [
            "我现在有点忙，稍后再为你服务吧。",
            "这个问题我需要思考一下。",
            "不好意思，我暂时无法回答这个问题。",
            "请再说一遍，我没听清楚。"
        ])
        
        # 支持的意图枚举（从 intent_keywords.py 读取）
        self._supported_intents = INTENT_ENUM
        
        # 初始化长期记忆管理器
        self._memory_manager = MemoryManager()
        print(f"[LLMPlugin] 长期记忆系统已初始化")
        
        # 初始化 OpenAI 兼容客户端
        if self.api_key:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        print(f"[LLMPlugin] 初始化完成，模型：{self.model}")
        print(f"[LLMPlugin] 最大历史长度：{self._max_history_length}")

    def execute(self, intent: str, params: dict):
        pass

    def get_supported_intents(self):
        return []

    def clear_history(self):
        """清空对话历史"""
        self._history = []

    def _trim_history(self):
        """裁剪历史，保持在最大长度内"""
        if len(self._history) > self._max_history_length:
            self._history = self._history[-self._max_history_length:]

    def get_fallback_response(self) -> str:
        """获取下一个兜底回复（循环使用）"""
        response = self._fallback_responses[self._fallback_index]
        self._fallback_index = (self._fallback_index + 1) % len(self._fallback_responses)
        return response

    def _build_messages(self, message: str) -> list:
        """构建包含历史和长期记忆的消息列表"""
        messages = []
        
        # 构建系统提示词（包含长期记忆上下文）
        memory_context = self._memory_manager.build_memory_context(message)
        system_prompt = self._system_prompt
        
        if memory_context:
            system_prompt = f"{memory_context}\n\n{self._system_prompt}"
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            # 默认系统提示词（精简版）
            intents_str = ",".join(self._supported_intents)
            default_prompt = f"""你是小派，一个智能机器人助手。

规则：
1. 如果是可执行指令，必须输出 JSON：{{"intent":"意图名","params":{{}},"response":"回复"}}
2. 意图必须从以下列表选择：{intents_str}
3. 如果是日常对话，直接回答，不要 JSON 格式。

示例：
- "前进" → {{"intent":"MOVE_FORWARD","params":{{}},"response":"好嘞，我来啦！(前进)"}}
- "跟着我" → {{"intent":"FOLLOW_ME","params":{{}},"response":"来啦来啦！(跟上)"}}
- "你好" → "你好！我是小派。"
            """.strip()
            messages.append({"role": "system", "content": default_prompt})
        
        # 添加短期历史（最近对话）
        for item in self._history:
            messages.append({"role": "user", "content": item["user"]})
            messages.append({"role": "assistant", "content": item["assistant"]})
        
        # 添加当前消息 + 格式提醒
        format_reminder = f"\n\n---\n请按以下格式响应：\n- 如果是指令：JSON 格式{{\"intent\":\"意图名\",\"params\":{{}},\"response\":\"回复\"}}\n- 如果是对话：直接回答"
        messages.append({"role": "user", "content": message + format_reminder})
        
        return messages

    async def chat(self, message: str, timeout: int = 30) -> str:
        """发送消息给 LLM 并获取响应（支持流式输出）"""
        if not self._client:
            print("[LLMPlugin] 错误：未设置 DEEPSEEK_API_KEY")
            return self.get_fallback_response()

        try:
            print(f"[LLMPlugin] 正在思考...")
            print(f"[LLMPlugin] 用户输入：{message}")
            start_time = time.time()
            
            # 构建消息（包含历史）
            messages = self._build_messages(message)
            print(f"[LLMPlugin] 消息构建完成，共 {len(messages)} 条消息")
            print(f"[LLMPlugin] 历史对话数：{len(self._history)}/{self._max_history_length}")
            
            # 流式调用 LLM
            print(f"[LLMPlugin] 调用 LLM API (model={self.model}, timeout={timeout}s)...")
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                timeout=timeout
            )
            
            full_response = ""
            chunk_count = 0
            for chunk in stream:
                # 超时检查
                if time.time() - start_time > timeout:
                    print(f"\n[LLMPlugin] LLM 响应超时 ({timeout}s)")
                    return self.get_fallback_response()
                
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    chunk_count += 1
                    print(content, end="", flush=True)
            
            print("\n")
            elapsed = time.time() - start_time
            print(f"[LLMPlugin] LLM 响应完成 (耗时：{elapsed:.2f}s, 数据块：{chunk_count}个)")
            print(f"[LLMPlugin] 响应长度：{len(full_response)} 字符")
            
            # 异步提取并保存事实（不阻塞响应）
            asyncio.create_task(self._extract_facts(message, full_response))
            
            # 保存到历史
            self._history.append({
                "user": message,
                "assistant": full_response
            })
            self._trim_history()
            print(f"[LLMPlugin] 已保存对话历史")
            
            return full_response.strip() if full_response else self.get_fallback_response()
            
        except Exception as e:
            print(f"\n[LLMPlugin] LLM 调用失败：{e}")
            import traceback
            print(f"[LLMPlugin] 错误详情：{traceback.format_exc()}")
            return self.get_fallback_response()

    def parse_intent_response(self, response: str) -> dict:
        """解析LLM响应，判断是否为结构化意图指令"""
        print(f"[LLMPlugin] 开始解析响应...")
        print(f"[LLMPlugin] 响应内容：{response[:100]}{'...' if len(response) > 100 else ''}")
        
        try:
            # 尝试解析 JSON
            response = response.strip()
            if response.startswith("{") and response.endswith("}"):
                print(f"[LLMPlugin] 检测到 JSON 格式，尝试解析...")
                data = json.loads(response)
                if "intent" in data:
                    intent = data["intent"]
                    print(f"[LLMPlugin] 识别到意图：{intent}")
                    
                    # 应用别名映射，纠正意图名称
                    if intent in INTENT_ALIAS_MAP:
                        print(f"[LLMPlugin] 意图别名纠正：{intent} → {INTENT_ALIAS_MAP[intent]}")
                        intent = INTENT_ALIAS_MAP[intent]
                    
                    params = data.get("params", {})
                    response_text = data.get("response", "")
                    print(f"[LLMPlugin] 参数：{params}")
                    print(f"[LLMPlugin] 回复：{response_text}")
                    
                    return {
                        "type": "intent",
                        "intent": intent,
                        "params": params,
                        "response": response_text
                    }
                else:
                    print(f"[LLMPlugin] JSON 中缺少 intent 字段")
            else:
                print(f"[LLMPlugin] 非 JSON 格式，视为普通文本")
        except json.JSONDecodeError as e:
            # JSON 解析失败，视为普通文本响应
            print(f"[LLMPlugin] JSON 解析失败：{e}")
        except Exception as e:
            print(f"[LLMPlugin] 解析意图响应失败：{e}")
            import traceback
            print(f"[LLMPlugin] 错误详情：{traceback.format_exc()}")
        
        return {
            "type": "text",
            "content": response
        }

    async def _extract_facts(self, user_msg: str, assistant_msg: str):
        """从对话中提取事实并保存到长期记忆"""
        try:
            print("[LLMPlugin] 开始提取对话事实...")
            
            # 构建提取提示词
            extract_prompt = self._memory_manager.get_extract_prompt(user_msg, assistant_msg)
            
            # 调用 LLM 提取事实
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": extract_prompt}],
                timeout=10
            )
            
            result = response.choices[0].message.content.strip()
            print(f"[LLMPlugin] 事实提取结果：{result[:100]}...")
            
            # 去除 markdown 代码块
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1])
                result = result.strip()
                if result.startswith("json"):
                    result = result[4:].strip()
            
            # 解析 JSON
            data = json.loads(result)
            add_list = data.get("add", [])
            delete_list = data.get("delete", [])
            
            # 处理删除指令
            for delete_item in delete_list:
                category = delete_item.get("category", "")
                tag = delete_item.get("tag", "")
                reason = delete_item.get("reason", "")
                if category and tag:
                    deleted = self._memory_manager.delete_fact(category, tag)
                    if deleted:
                        print(f"[LLMPlugin] 删除事实: [{category}] {tag}，原因: {reason}")
                    else:
                        print(f"[LLMPlugin] 未找到可删除的事实: [{category}] {tag}")
            
            # 保存新增事实
            for fact in add_list:
                category = fact.get("category", "")
                tag = fact.get("tag", "")
                content = fact.get("content", "")
                
                # 过滤无效或无价值的事实
                if not category or not tag or not content:
                    print(f"[LLMPlugin] 跳过无效事实: {fact}")
                    continue
                
                # 过滤"未提供"、"不知道"等无价值内容
                if any(keyword in content for keyword in ["未提供", "不知道", "不清楚", "没有", "无"]):
                    print(f"[LLMPlugin] 跳过无价值事实: {content}")
                    continue
                
                # 验证 Identity 类别：只有用户明确自述时才更新
                if not self._validate_identity_fact(category, tag, content, user_msg):
                    continue
                
                # 检查是否已存在相同内容的事实（去重）
                all_facts = self._memory_manager._get_all_facts_by_category(category)
                content_exists = any(f.get("content", "") == content for f in all_facts)
                if content_exists:
                    print(f"[LLMPlugin] 跳过重复事实: {content}")
                    continue
                
                # Identity 类别同时存入 user_profile
                if category == "Identity" and tag in ["name", "age"]:
                    self._memory_manager.set_user_profile(tag, content, source="extracted")
                    print(f"[LLMPlugin] 已更新用户画像: {tag} = {content}")
                
                self._memory_manager.add_fact(
                    category=category,
                    tag=tag,
                    content=content,
                    source="extracted"
                )
                print(f"[LLMPlugin] 提取事实: [{category}] {tag} = {content}")
            
            if not add_list and not delete_list:
                print("[LLMPlugin] 未提取到有价值的事实")
                
        except Exception as e:
            print(f"[LLMPlugin] 事实提取失败：{e}")

    def _validate_identity_fact(self, category: str, tag: str, content: str, user_msg: str) -> bool:
        """验证身份信息事实的有效性"""
        if category == "Identity" and tag == "name":
            # 用户消息中必须明确包含自述短语才更新名字
            self_intro_phrases = ["我是", "我叫", "我的名字", "大家叫我", "我叫", "名字是"]
            if not any(phrase in user_msg for phrase in self_intro_phrases):
                print(f"[LLMPlugin] 跳过非自述的名字：{content}")
                return False
        return True