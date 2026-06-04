# src/core/state.py
from enum import Enum
from typing import Set, Tuple, Optional


class RobotState(Enum):
    """机器人状态枚举"""
    IDLE = "idle"      # 待机：监听唤醒词
    AWAKE = "awake"    # 唤醒：语音交互中
    REMOTE = "remote"  # 远程：网页控制中


class StateTransition:
    """状态转换规则（硬编码，AI不参与决策）"""
    
    # 允许的转换: (from_state, to_state)
    _ALLOWED: Set[Tuple[RobotState, RobotState]] = {
        # 从待机可以进入
        (RobotState.IDLE, RobotState.AWAKE),
        (RobotState.IDLE, RobotState.REMOTE),
        # 从唤醒只能回到待机
        (RobotState.AWAKE, RobotState.IDLE),
        # 从远程只能回到待机
        (RobotState.REMOTE, RobotState.IDLE),
    }
    
    # 拒绝时的提示消息
    _ERROR_MESSAGES: dict[Tuple[RobotState, RobotState], str] = {
        (RobotState.AWAKE, RobotState.REMOTE): "小派正在工作中，请稍后再试",
        (RobotState.REMOTE, RobotState.AWAKE): "远程控制中，请先断开连接",
    }
    
    @classmethod
    def can_transition(cls, from_state: RobotState, to_state: RobotState) -> bool:
        """检查状态转换是否允许"""
        if from_state == to_state:
            return True
        return (from_state, to_state) in cls._ALLOWED
    
    @classmethod
    def get_error_message(cls, from_state: RobotState, to_state: RobotState) -> Optional[str]:
        """获取拒绝转换时的提示消息"""
        return cls._ERROR_MESSAGES.get((from_state, to_state))
    
    @classmethod
    def get_allowed_transitions(cls, from_state: RobotState) -> list[RobotState]:
        """获取从当前状态允许转换到的所有状态"""
        return [to for (f, to) in cls._ALLOWED if f == from_state]