# src/core/state_machine.py
import threading
from typing import Callable, Optional, List
from loguru import logger
from src.core.state import RobotState, StateTransition


class StateMachine:
    """线程安全的状态机"""
    
    def __init__(self):
        self._state: RobotState = RobotState.IDLE
        self._lock: threading.RLock = threading.RLock()
        self._listeners: List[Callable[[RobotState, RobotState], None]] = []
    
    @property
    def state(self) -> RobotState:
        """获取当前状态"""
        with self._lock:
            return self._state
    
    def add_listener(self, callback: Callable[[RobotState, RobotState], None]) -> None:
        """
        添加状态变化监听器
        callback 参数: (old_state, new_state)
        """
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[RobotState, RobotState], None]) -> None:
        """移除监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self, old_state: RobotState, new_state: RobotState) -> None:
        """通知所有监听器"""
        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                logger.error(f"监听器回调异常: {e}")
    
    def transition_to(self, new_state: RobotState) -> bool:
        """
        请求状态转换
        返回: 是否成功
        """
        with self._lock:
            old_state = self._state
            
            # 相同状态，直接返回成功
            if old_state == new_state:
                return True
            
            # 检查转换是否允许
            if not StateTransition.can_transition(old_state, new_state):
                logger.warning(f"拒绝转换: {old_state.value} -> {new_state.value}")
                return False
            
            # 执行转换
            logger.info(f"[StateMachine] {old_state.value} -> {new_state.value}")
            self._state = new_state
            
            # 通知监听器（在锁内但列表拷贝，避免回调死锁）
            listeners = self._listeners.copy()
        
        # 在锁外通知，避免回调中再次调用状态转换导致死锁
        for listener in listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                logger.error(f"[StateMachine] 监听器回调异常: {e}")
        
        return True
    
    def can_transition_to(self, new_state: RobotState) -> bool:
        """检查是否可以转换到目标状态"""
        with self._lock:
            return StateTransition.can_transition(self._state, new_state)
    
    def force_set_state(self, new_state: RobotState) -> None:
        """
        强制设置状态（仅用于测试，不触发监听器）
        警告：生产代码不要使用
        """
        with self._lock:
            self._state = new_state