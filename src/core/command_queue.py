# src/core/command_queue.py
import threading
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict, Any, Callable
from collections import deque
from loguru import logger

from src.core.interrupt import is_interrupted


class CommandType(Enum):
    """指令类型 - 决定执行策略"""
    PREEMPTIVE = 1   # 抢占型：立即打断当前，清空队列
    EXCLUSIVE = 2    # 独占型：执行期间屏蔽同类
    QUEUED = 3       # 排队型：按序执行，不互相打断
    CONCURRENT = 4   # 并发型：不占用资源，可同时执行


@dataclass
class Command:
    """指令数据类"""
    intent: str
    params: Dict[str, Any]
    command_type: CommandType
    resources: Set[str] = field(default_factory=set)
    timestamp: float = field(default_factory=time.time)
    callback: Optional[Callable[[Any], None]] = None


class CommandQueue:
    """指令队列 - 优先级 + 资源锁 + 并发控制"""
    
    def __init__(self):
        self._queue: deque = deque()
        self._lock: threading.RLock = threading.RLock()
        self._current_command: Optional[Command] = None
        self._resource_locks: Dict[str, bool] = {}  # 资源占用状态
        self._is_processing: bool = False
        self._condition: threading.Condition = threading.Condition(self._lock)
    
    def _can_execute(self, cmd: Command) -> bool:
        """检查指令是否可以立即执行"""
        # 抢占型总是可以执行
        if cmd.command_type == CommandType.PREEMPTIVE:
            return True
        
        # 检查资源是否被占用
        for res in cmd.resources:
            if self._resource_locks.get(res, False):
                return False
        
        return True
    
    def _lock_resources(self, resources: Set[str]) -> None:
        """锁定资源"""
        for res in resources:
            self._resource_locks[res] = True
    
    def _unlock_resources(self, resources: Set[str]) -> None:
        """释放资源"""
        for res in resources:
            self._resource_locks[res] = False
    
    def _execute(self, cmd: Command) -> None:
        """执行指令（内部方法）"""
        self._current_command = cmd
        self._lock_resources(cmd.resources)
        
        # 调用回调执行指令
        if cmd.callback:
            try:
                cmd.callback(cmd)
            except Exception as e:
                logger.error(f"[CommandQueue] 指令执行异常: {e}")
        
        self._current_command = None
        self._unlock_resources(cmd.resources)
    
    def submit(self, cmd: Command) -> bool:
        """
        提交指令
        返回: 是否成功提交（注意：不等于执行完成）
        """
        with self._lock:
            # 抢占型指令：清空队列，打断当前
            if cmd.command_type == CommandType.PREEMPTIVE:
                self._queue.clear()
                self._condition.notify()
                # 如果有当前指令，它会自然结束或被打断
                # 直接在当前线程执行（立即）
                self._execute(cmd)
                return True
            
            # 如果可以立即执行
            if not self._is_processing and self._can_execute(cmd):
                self._is_processing = True
                self._execute(cmd)
                self._is_processing = False
                # 处理队列中下一个
                self._process_next()
                return True
            
            # 否则加入队列
            self._queue.append(cmd)
            self._condition.notify()
            return True
    
    def _process_next(self) -> None:
        """处理队列中的下一个指令"""
        with self._lock:
            while self._queue:
                cmd = self._queue[0]
                if self._can_execute(cmd):
                    self._queue.popleft()
                    self._is_processing = True
                    self._execute(cmd)
                    self._is_processing = False
                else:
                    # 资源被占，等待
                    break
    
    def get_queue_size(self) -> int:
        """获取队列长度"""
        with self._lock:
            return len(self._queue)
    
    def get_current_command(self) -> Optional[Command]:
        """获取当前正在执行的指令"""
        with self._lock:
            return self._current_command
    
    def clear(self) -> None:
        """清空队列（不打断当前执行）"""
        with self._lock:
            self._queue.clear()
    
    def is_busy(self) -> bool:
        """队列是否繁忙（有正在执行的指令或有等待队列）"""
        with self._lock:
            return self._is_processing or len(self._queue) > 0
    
    def get_resource_status(self) -> Dict[str, bool]:
        """获取资源占用状态（用于调试）"""
        with self._lock:
            return self._resource_locks.copy()
    
    def interrupt_current(self) -> None:
        """打断当前正在执行的指令（不打断状态机）"""
        logger.info("[CommandQueue] 打断当前指令")
        with self._lock:
            self.clear()
        # 注意：实际的打断需要插件代码中检查 is_interrupted()
        # 这里只负责清空队列和通知