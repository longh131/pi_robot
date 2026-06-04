# src/core/interrupt.py
import threading
from loguru import logger

# 全局打断Event
_interrupt_event = threading.Event()


def trigger_interrupt():
    """触发全局打断（设置Event）"""
    _interrupt_event.set()
    logger.info("[Interrupt] 全局打断已触发")


def reset_interrupt():
    """重置打断状态（清除Event）"""
    _interrupt_event.clear()
    logger.info("[Interrupt] 打断状态已重置")


def is_interrupted():
    """检查是否被打断"""
    return _interrupt_event.is_set()


def wait_for_interrupt(timeout=None):
    """等待打断（阻塞，可选超时）"""
    return _interrupt_event.wait(timeout=timeout)
