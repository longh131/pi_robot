import sqlite3
import json
from typing import Dict, List, Optional

# 提取提示词
EXTRACT_PROMPT = """分析以下对话，提取用户相关的事实信息。

对话：
用户：{user_msg}
助手：{assistant_msg}

请严格按以下JSON格式输出（只输出JSON，不要其他内容）：
{{
  "add": [
    {{"category": "Identity", "tag": "name", "content": "用户叫凯尼"}},
    {{"category": "Preference", "tag": "music", "content": "用户喜欢摇滚乐"}}
  ],
  "delete": [
    {{"category": "Preference", "tag": "sport", "reason": "用户明确表示不再喜欢足球"}}
  ]
}}

说明：
- add: 需要新增或更新的事实列表
- delete: 需要删除的事实列表（当用户明确表示否定、放弃、不再等时）
- reason: 删除原因，用于日志记录

类别说明：
- Identity: 身份信息（姓名、职业、年龄等）
- Preference: 偏好（食物、音乐、电影等）
- Habit: 习惯（作息、运动、爱好等）
- Event: 事件（生日、纪念日、行程等）

删除判断规则（用户说"不再"、"不喜欢"、"不玩"、"没有"等否定表达时）：
- 如果用户说"我不喜欢足球了"，删除 sports 相关记录
- 如果用户说"我现在喜欢篮球了"，先删除 sports，再添加 basketball
- 如果用户说"我没有养宠物了"，删除 pet 相关记录

重要规则：
1. 只提取用户相关的明确信息
2. tag使用英文简短标签（用于去重）
3. 只返回有信息价值的事实
4. 如果没有有价值的信息，add 和 delete 都返回空列表：{{"add": [], "delete": []}}
5. 当用户明确表达否定时，必须生成 delete 指令
"""


class MemoryManager:
    def __init__(self, db_path: str = "data/robot_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                source TEXT DEFAULT 'manual',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                tag TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                source TEXT DEFAULT 'extracted',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                intent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        print(f"[MemoryManager] 数据库初始化完成: {self.db_path}")

    def get_user_profile(self, key: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM user_profile WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def set_user_profile(self, key: str, value: str, source: str = 'manual'):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_profile (key, value, source)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value, source))
        conn.commit()
        conn.close()

    def get_all_profile(self) -> Dict[str, str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_profile")
        rows = cursor.fetchall()
        conn.close()
        return {key: value for key, value in rows}

    def add_fact(self, category: str, tag: str, content: str,
                 weight: float = 1.0, source: str = 'extracted'):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO facts (category, tag, content, weight, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tag) DO UPDATE SET
                content = excluded.content,
                weight = excluded.weight,
                updated_at = CURRENT_TIMESTAMP
        """, (category, tag, content, weight, source))
        conn.commit()
        conn.close()

    def delete_fact(self, category: str, tag: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM facts WHERE category = ? AND tag = ?
        """, (category, tag))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def get_relevant_facts(self, query: str, limit: int = 5) -> List[Dict]:
        """获取与查询相关的事实（改进匹配逻辑）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 按字符拆分查询（支持中文、英文和数字）
        import re
        # 匹配单个中文字符、英文单词和数字
        query_keywords = []
        for char in query:
            # 判断是否是中文字符
            if '\u4e00' <= char <= '\u9fff':
                query_keywords.append(char)
        
        # 再提取英文单词和数字
        words = re.findall(r'[a-zA-Z]+|\d+', query)
        query_keywords.extend(words)
        
        # 去重并过滤空字符
        query_keywords = list(set([kw.strip() for kw in query_keywords if kw.strip()]))
        
        # 如果没有提取到关键词，使用完整查询
        if not query_keywords:
            query_keywords = [query]
        
        # 使用 OR 连接多个关键词模式
        patterns = []
        params = []
        
        # 匹配查询中的每个词
        for keyword in query_keywords[:10]:  # 最多使用10个关键词
            pattern = f"%{keyword}%"
            patterns.append(f"(category LIKE ? OR tag LIKE ? OR content LIKE ?)")
            params.extend([pattern, pattern, pattern])
        
        where_clause = " OR ".join(patterns)
        query_sql = f"""
            SELECT category, tag, content, weight
            FROM facts
            WHERE {where_clause}
            ORDER BY weight DESC, updated_at DESC
            LIMIT ?
        """
        params.append(limit)
        cursor.execute(query_sql, params)
        
        rows = cursor.fetchall()
        conn.close()
        return [{"category": r[0], "tag": r[1], "content": r[2], "weight": r[3]}
                for r in rows]

    def add_message(self, role: str, content: str, intent: Optional[str] = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (role, content, intent) VALUES (?, ?, ?)",
            (role, content, intent)
        )
        conn.commit()
        conn.close()

    def get_recent_messages(self, limit: int = 10) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content, intent, created_at
            FROM messages
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1], "intent": r[2], "created_at": r[3]}
                for r in reversed(rows)]

    def build_memory_context(self, current_query: str) -> str:
        """构建记忆上下文（混合策略：Identity全量 + user_profile全量 + 其他检索）"""
        context_parts = []

        # 1. user_profile 全量注入
        profile = self.get_all_profile()
        if profile:
            context_parts.append("【用户画像】")
            for key, value in profile.items():
                context_parts.append(f"- {key}: {value}")
            context_parts.append("")

        # 2. Identity 类别全量注入
        identity_facts = self._get_all_facts_by_category("Identity")
        if identity_facts:
            context_parts.append("【身份信息】")
            for fact in identity_facts:
                context_parts.append(f"- {fact['content']}")
            context_parts.append("")

        # 3. 其他类别（Preference/Habit/Event）关键词检索
        other_facts = self.get_relevant_facts_exclude_category(current_query, exclude_category="Identity", limit=5)
        if other_facts:
            context_parts.append("【相关记忆】")
            for fact in other_facts:
                context_parts.append(f"- {fact['content']}")

        return "\n".join(context_parts) if context_parts else ""

    def _get_all_facts_by_category(self, category: str) -> List[Dict]:
        """获取指定类别的所有事实"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, tag, content, weight
            FROM facts
            WHERE category = ?
            ORDER BY updated_at DESC
        """, (category,))
        rows = cursor.fetchall()
        conn.close()
        return [{"category": r[0], "tag": r[1], "content": r[2], "weight": r[3]}
                for r in rows]

    def get_relevant_facts_exclude_category(self, query: str, exclude_category: str, limit: int = 5) -> List[Dict]:
        """获取排除指定类别的相关事实"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        import re
        query_keywords = []
        for char in query:
            if '\u4e00' <= char <= '\u9fff':
                query_keywords.append(char)
        
        words = re.findall(r'[a-zA-Z]+|\d+', query)
        query_keywords.extend(words)
        query_keywords = list(set([kw.strip() for kw in query_keywords if kw.strip()]))
        
        if not query_keywords:
            query_keywords = [query]
        
        patterns = []
        params = []
        
        for keyword in query_keywords[:10]:
            pattern = f"%{keyword}%"
            patterns.append(f"(category LIKE ? OR tag LIKE ? OR content LIKE ?)")
            params.extend([pattern, pattern, pattern])
        
        where_clause = " OR ".join(patterns)
        query_sql = f"""
            SELECT category, tag, content, weight
            FROM facts
            WHERE category != ? AND ({where_clause})
            ORDER BY weight DESC, updated_at DESC
            LIMIT ?
        """
        params.insert(0, exclude_category)
        params.append(limit)
        cursor.execute(query_sql, params)
        
        rows = cursor.fetchall()
        conn.close()
        return [{"category": r[0], "tag": r[1], "content": r[2], "weight": r[3]}
                for r in rows]

    def get_extract_prompt(self, user_msg: str, assistant_msg: str) -> str:
        return EXTRACT_PROMPT.format(user_msg=user_msg, assistant_msg=assistant_msg)