"""通用回复服务"""
import os
from typing import Dict, Any, List, TYPE_CHECKING
from loguru import logger
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory

if TYPE_CHECKING:
    from app.graph.state import AgentState


class GeneralResponseService:
    """通用回复服务类"""
    
    def __init__(self):
        """初始化通用回复服务"""
        file_path = os.path.abspath(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
        prompt_dir = os.path.join(app_dir, "prompt")
        # 通用回复服务，用于处理非旅游相关的问题或需求
        self.system_prompt_path = os.path.join(prompt_dir, "general-response-system-prompt.txt")
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            with open(self.system_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"系统提示词文件不存在: {self.system_prompt_path}")
    
    def _get_last_user_input(self, state: "AgentState") -> str:
        """从 state 中提取最后一条用户输入"""
        messages = state.get("messages", [])
        if not messages:
            return ""
        
        # 从后往前找最后一条用户消息
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content if hasattr(msg, 'content') else str(msg)
        
        return ""
    
    def generate_response(self, state: "AgentState") -> Dict[str, Any]:
        """
        生成通用回复
        
        Args:
            state: Agent 状态对象
            
        Returns:
            包含回复的字典：
            - response: AI 的回复
            - messages: 包含回复消息的列表
        """
        try:
            # 从 state 中提取信息
            conversation_history = state.get("messages", [])
            
            # 加载系统提示词
            system_prompt = self._load_system_prompt()
            
            # 创建 LLM 实例
            llm = LLMFactory.create_llm(
                temperature=0.7,
                max_tokens=500
            )
            
            # 构建消息
            messages = [SystemMessage(content=system_prompt)]
            
            # 添加对话历史（如果有）
            if conversation_history:
                # 只取最近几条消息作为上下文
                for msg in conversation_history[-20:]:
                    messages.append(msg)
            
            # 调用 LLM
            response = llm.invoke(messages)
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            logger.info("通用回复生成完成")
            
            return {
                "response": response_content,
                "messages": [AIMessage(content=response_content)]
            }
        
        except Exception as e:
            logger.error(f"通用回复生成异常: {e}", exc_info=True)
            # 降级回复
            response = "抱歉，我现在无法回答您的问题。如果您有旅游相关的问题，我很乐意为您提供帮助。"
            
            return {
                "response": response,
                "messages": [AIMessage(content=response)]
            }


