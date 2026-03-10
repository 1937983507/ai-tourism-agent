"""对话引导服务"""
import os
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from loguru import logger
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory

if TYPE_CHECKING:
    from app.graph.state import AgentState


class ConversationGuidanceService:
    """对话引导服务类"""
    
    def __init__(self):
        """初始化对话引导服务"""
        file_path = os.path.abspath(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
        prompt_dir = os.path.join(app_dir, "prompt")
        # 对话引导服务，用于引导用户提供旅游目的地和天数信息
        self.guidance_system_prompt_path = os.path.join(prompt_dir, "conversation-guidance-system-prompt.txt")
        self.guidance_user_prompt_path = os.path.join(prompt_dir, "conversation-guidance-user-prompt.txt")
        
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            with open(self.guidance_system_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"系统提示词文件不存在: {self.guidance_system_prompt_path}")

    def _load_guidance_user_prompt_template(self) -> str:
        """加载对话引导用户提示词模板"""
        try:
            with open(self.guidance_user_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"对话引导用户提示词文件不存在: {self.guidance_user_prompt_path}")
    
    def guide_conversation(self, state: "AgentState") -> Dict[str, Any]:
        """
        引导对话，获取缺失的信息
        
        Args:
            state: Agent 状态对象
            
        Returns:
            包含引导回复和可能提取到的信息的字典：
            - response: AI 的引导回复
            - city_name: 如果从对话中提取到城市
            - day_count: 如果从对话中提取到天数
            - messages: 包含回复消息的列表
        """
        try:
            # 从 state 中提取信息
            current_city = state.get("city_name")
            current_day_count = state.get("day_count")
            conversation_history = state.get("messages", [])

            # 仅负责生成引导回复：城市/天数等关键信息由上游意图识别节点统一提取并写入 state。
            response_content = self._generate_guidance_response(
                current_city,
                current_day_count,
                conversation_history
            )
            
            logger.info(f"对话引导完成: city={current_city}, day_count={current_day_count}")
            
            return {
                "response": response_content,
                "city_name": current_city,
                "day_count": current_day_count,
                "messages": [AIMessage(content=response_content)]
            }
        
        except Exception as e:
            logger.error(f"对话引导异常: {e}", exc_info=True)

            # 降级：仅做最小化引导回复（不做信息提取）
            current_city = state.get("city_name")
            current_day_count = state.get("day_count")

            missing_info = []
            if not current_city:
                missing_info.append("城市")
            if not current_day_count:
                missing_info.append("天数")
            
            if missing_info:
                response = f"请告诉我您的{'和'.join(missing_info)}信息，以便我为您规划旅游路线。"
            else:
                response = "好的，我已经了解了您的需求。"
            
            return {
                "response": response,
                "city_name": current_city,
                "day_count": current_day_count,
                "messages": [AIMessage(content=response)]
            }
    
    def _generate_guidance_response(
        self,
        current_city: Optional[str],
        current_day_count: Optional[int],
        conversation_history: List,
    ) -> str:
        """
        生成引导回复
        
        Args:
            current_city: 当前已知的城市
            current_day_count: 当前已知的天数
            conversation_history: 对话历史
            
        Returns:
            引导回复文本
        """
        try:
            # 加载系统提示词
            guidance_system_prompt = self._load_system_prompt()
            
            # 构建上下文信息
            context_info = []
            if current_city:
                context_info.append(f"已知城市：{current_city}")
            if current_day_count:
                context_info.append(f"已知天数：{current_day_count}")
            
            context_str = "\n".join(context_info) if context_info else "尚未获取到任何信息"

            # 构建提示词（从 prompt 文件读取）
            guidance_user_prompt_template = self._load_guidance_user_prompt_template()
            guidance_user_prompt = guidance_user_prompt_template.format(
                context_str=context_str,
            )

            # 构建消息
            messages = [SystemMessage(content=guidance_system_prompt)]

            # 添加对话历史（如果有）
            if conversation_history:
                # 只取最近几条消息作为上下文
                for msg in conversation_history[-20:]:
                    messages.append(msg)
            
            # 添加用户提示词
            messages.append(HumanMessage(content=guidance_user_prompt))
            
            # 创建 LLM 实例
            llm = LLMFactory.create_llm(
                temperature=0.7,
                max_tokens=300
            )
            
            # 调用 LLM
            response = llm.invoke(messages)
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            return response_content
            
        except Exception as e:
            logger.warning(f"LLM 生成引导回复失败，使用默认回复: {e}")
            # 降级回复
            missing_info = []
            if not current_city:
                missing_info.append("城市")
            if not current_day_count:
                missing_info.append("天数")
            
            if missing_info:
                return f"请告诉我您的{'和'.join(missing_info)}信息，以便我为您规划旅游路线。"
            else:
                return "好的，我已经了解了您的需求。"

