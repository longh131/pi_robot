# src/core/base_plugin.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from src.core.state import RobotState


class BasePlugin(ABC):
    """
    插件基类
    所有插件必须继承此类并实现所有抽象方法
    """
    
    def __init__(self, name: str):
        self.name = name
        self._enabled: bool = True
        self._brain: Optional[Any] = None  # Brain实例引用
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    def set_enabled(self, enabled: bool) -> None:
        """启用/禁用插件"""
        self._enabled = enabled
    
    def set_brain(self, brain: Any) -> None:
        """设置Brain引用（由Brain调用）"""
        self._brain = brain
    
    # ========== 生命周期方法（可选实现） ==========
    
    def on_load(self) -> None:
        """插件加载时调用（初始化）"""
        pass
    
    def on_unload(self) -> None:
        """插件卸载时调用（清理资源）"""
        pass
    
    def on_state_change(self, old_state: RobotState, new_state: RobotState) -> None:
        """状态变化时调用"""
        pass
    
    # ========== 核心方法（必须实现） ==========
    
    @abstractmethod
    def execute(self, intent: str, params: Dict[str, Any]) -> Any:
        """
        执行指令
        返回: 执行结果
        """
        pass
    
    @abstractmethod
    def get_supported_intents(self) -> list:
        """
        返回此插件支持的所有意图列表
        用于Brain路由
        """
        pass