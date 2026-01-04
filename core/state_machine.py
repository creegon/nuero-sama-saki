# #000000;from state_machine import State, get_state_machine
# -*- coding: utf-8 -*-
"""
State Machine Module
定义 AI 桌宠的状态及状态转换逻辑
合并自原 state_machine/states.py 和 state_machine/transitions.py
"""

from enum import Enum, auto
from typing import Optional, Callable, Dict, List
from loguru import logger


# ==========================================
# States Definition
# ==========================================

class State(Enum):
    """AI 桌宠状态"""
    
    IDLE = auto()        # 空闲等待
    LISTENING = auto()   # 正在听用户说话
    PROCESSING = auto()  # 处理中（STT/LLM）
    SPEAKING = auto()    # 正在说话


# 状态描述
STATE_DESCRIPTIONS = {
    State.IDLE: "空闲等待",
    State.LISTENING: "正在听...",
    State.PROCESSING: "思考中...",
    State.SPEAKING: "说话中..."
}


def get_state_description(state: State) -> str:
    """获取状态描述"""
    return STATE_DESCRIPTIONS.get(state, "未知状态")


# ==========================================
# State Machine Logic
# ==========================================

class StateMachine:
    """
    AI 桌宠状态机
    
    状态转换图：
    
    IDLE <-> LISTENING -> PROCESSING -> SPEAKING -> IDLE
              ^                           |
              └-----------打断-------------┘
    """
    
    def __init__(self):
        self._state = State.IDLE
        self._previous_state: Optional[State] = None
        
        # 状态变化回调
        self.on_state_change: Optional[Callable[[State, State], None]] = None
        
        # 有效的状态转换
        self._valid_transitions: Dict[State, List[State]] = {
            State.IDLE: [State.LISTENING],
            State.IDLE: [State.LISTENING],
            State.LISTENING: [State.IDLE, State.PROCESSING, State.SPEAKING],  # 允许直接转SPEAKING（打断后快速回复）
            State.PROCESSING: [State.SPEAKING, State.LISTENING],  # 可能被打断
            State.SPEAKING: [State.IDLE, State.LISTENING],  # 可能被打断
        }
    
    @property
    def state(self) -> State:
        """当前状态"""
        return self._state
    
    @property
    def previous_state(self) -> Optional[State]:
        """上一个状态"""
        return self._previous_state
    
    def can_transition_to(self, new_state: State) -> bool:
        """检查是否可以转换到目标状态"""
        return new_state in self._valid_transitions.get(self._state, [])
    
    def transition_to(self, new_state: State, force: bool = False) -> bool:
        """
        转换到新状态
        
        Args:
            new_state: 目标状态
            force: 是否强制转换（忽略有效性检查）
            
        Returns:
            是否成功转换
        """
        if not force and not self.can_transition_to(new_state):
            logger.warning(
                f"无效的状态转换: {self._state.name} -> {new_state.name}"
            )
            return False
        
        old_state = self._state
        self._previous_state = old_state
        self._state = new_state
        
        logger.info(
            f"状态转换: {old_state.name} -> {new_state.name} "
            f"({get_state_description(new_state)})"
        )
        
        if self.on_state_change:
            self.on_state_change(old_state, new_state)
        
        return True
    
    def reset(self):
        """重置到初始状态"""
        self._previous_state = self._state
        self._state = State.IDLE
        logger.info("状态机已重置")
    
    # 便捷方法
    def start_listening(self) -> bool:
        """开始听取"""
        return self.transition_to(State.LISTENING)
    
    def stop_listening(self) -> bool:
        """停止听取（回到空闲）"""
        return self.transition_to(State.IDLE)
    
    def start_processing(self) -> bool:
        """开始处理"""
        return self.transition_to(State.PROCESSING)
    
    def start_speaking(self) -> bool:
        """开始说话"""
        return self.transition_to(State.SPEAKING)
    
    def finish_speaking(self) -> bool:
        """说话结束"""
        # 如果已经不在 SPEAKING 状态（比如被打断回到了 LISTENING），则不做操作
        if self._state != State.SPEAKING:
            return False
            
        return self.transition_to(State.IDLE)
    
    def interrupt(self) -> bool:
        """
        打断当前状态（用于用户打断）
        从 SPEAKING 或 PROCESSING 直接回到 LISTENING
        """
        if self._state in [State.SPEAKING, State.PROCESSING]:
            logger.info("用户打断，切换到 LISTENING")
            return self.transition_to(State.LISTENING, force=True)
        return False
    
    # 状态检查
    @property
    def is_idle(self) -> bool:
        return self._state == State.IDLE
    
    @property
    def is_listening(self) -> bool:
        return self._state == State.LISTENING
    
    @property
    def is_processing(self) -> bool:
        return self._state == State.PROCESSING
    
    @property
    def is_speaking(self) -> bool:
        return self._state == State.SPEAKING
    
    @property
    def is_busy(self) -> bool:
        """是否正忙（处理中或说话中）"""
        return self._state in [State.PROCESSING, State.SPEAKING]


# 全局单例
_state_machine: Optional[StateMachine] = None


def get_state_machine() -> StateMachine:
    """获取全局状态机实例"""
    global _state_machine
    if _state_machine is None:
        _state_machine = StateMachine()
    return _state_machine


if __name__ == "__main__":
    # 测试状态机
    sm = StateMachine()
    
    print("测试正常流程:")
    print(f"  初始状态: {sm.state.name}")
    
    sm.start_listening()
    sm.start_processing()
    sm.start_speaking()
    sm.finish_speaking()
    
    print(f"  最终状态: {sm.state.name}")
    
    print("\n测试打断:")
    sm.start_listening()
    sm.start_processing()
    print(f"  处理中: {sm.state.name}")
    sm.interrupt()
    print(f"  打断后: {sm.state.name}")
