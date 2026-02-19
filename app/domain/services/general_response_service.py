"""通用回复服务"""
import logging
import os
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory

logger = logging.getLogger(__name__)


class GeneralResponseService:
    """通用回复服务类"""
    
    def __init__(self):
        """初始化通用回复服务"""
        # 获取项目根目录
        current_dir = os.path.dirname(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        prompt_dir = os.path.join(app_dir, "prompt")
        self.system_prompt_path = os.path.join(prompt_dir, "general-response-system-prompt.txt")
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        if os.path.exists(self.system_prompt_path):
            with open(self.system_prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return """你是一位友好的AI助手。请理解用户的问题或需求，提供友好、有帮助的回答。"""
    
    def generate_response(
        self,
        user_input: str,
        conversation_history: List = None
    ) -> Dict[str, Any]:
        """
        生成通用回复
        
        Args:
            user_input: 用户输入
            conversation_history: 对话历史（可选）
            
        Returns:
            包含回复的字典：
            - response: AI 的回复
            - messages: 包含回复消息的列表
        """
        try:
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
                for msg in conversation_history[-3:]:
                    messages.append(msg)
            
            # 添加当前用户输入
            messages.append(HumanMessage(content=user_input))
            
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


