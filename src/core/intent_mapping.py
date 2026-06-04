# src/core/intent_mapping.py
# 意图到指令类型的映射配置
# 自动推导 + 手动覆盖机制

from src.core.command_queue import CommandType
from src.core.intent_keywords import INTENT_CATEGORIES

# ==================== 分类默认策略 ====================
# 根据意图分类自动推导指令类型
CATEGORY_DEFAULT_COMMAND_TYPE = {
    "SYSTEM": CommandType.PREEMPTIVE,      # 系统指令 - 立即抢占执行
    "MOTOR": CommandType.EXCLUSIVE,        # 运动指令 - 独占执行
    "ASSISTANT": CommandType.CONCURRENT,   # 助理指令 - 并发执行
    "ENTERTAINMENT": CommandType.CONCURRENT, # 娱乐指令 - 并发执行
    "QUERY": CommandType.CONCURRENT,       # 查询指令 - 并发执行
}

# ==================== 手动覆盖规则 ====================
# 特殊意图需要手动指定不同的指令类型
OVERRIDE_COMMAND_TYPE = {
    # SYSTEM 类别覆盖
    "SYSTEM_STATUS": CommandType.CONCURRENT,  # 查询状态不抢占
    
    # MOTOR 类别覆盖
    "STOP": CommandType.PREEMPTIVE,           # 停止指令需要立即执行
    
    # ENTERTAINMENT 类别覆盖
    "TAKE_PHOTO": CommandType.EXCLUSIVE,      # 拍照需要独占资源
    "START_RECORDING": CommandType.EXCLUSIVE, # 录像需要独占资源
    "STOP_RECORDING": CommandType.PREEMPTIVE, # 停止录像立即执行
}

# ==================== 自动生成映射 ====================
# 基于分类自动推导 + 手动覆盖
INTENT_TO_COMMAND_TYPE = {}

# 1. 先根据分类设置默认值
for category, intents in INTENT_CATEGORIES.items():
    default_type = CATEGORY_DEFAULT_COMMAND_TYPE.get(category, CommandType.QUEUED)
    for intent in intents:
        INTENT_TO_COMMAND_TYPE[intent] = default_type

# 2. 应用手动覆盖规则
INTENT_TO_COMMAND_TYPE.update(OVERRIDE_COMMAND_TYPE)


def get_command_type(intent: str) -> CommandType:
    """获取意图对应的指令类型"""
    return INTENT_TO_COMMAND_TYPE.get(intent, CommandType.QUEUED)