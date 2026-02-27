"""对话引导服务"""
import logging
import os
import json
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory
from app.domain.services.simple_intent_extractor import SimpleIntentExtractor

if TYPE_CHECKING:
    from app.graph.state import AgentState

logger = logging.getLogger(__name__)


class ConversationGuidanceService:
    """对话引导服务类"""
    
    def __init__(self):
        """初始化对话引导服务"""
        # 获取项目根目录
        current_dir = os.path.dirname(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        prompt_dir = os.path.join(app_dir, "prompt")
        self.system_prompt_path = os.path.join(prompt_dir, "conversation-guidance-system-prompt.txt")
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        if os.path.exists(self.system_prompt_path):
            with open(self.system_prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return """你是一位友好的旅游助手。通过友好对话引导用户提供旅游目的地和天数信息。保持友好、自然的对话风格，一次只问一个问题。"""
    
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
            user_input = self._get_last_user_input(state)
            conversation_history = state.get("messages", [])
            current_city = state.get("city_name")
            current_day_count = state.get("day_count")
            
            # 第一步：使用 LLM 从用户输入中提取信息
            extracted_city, extracted_day_count = self._extract_with_llm(
                user_input, 
                conversation_history,
                current_city, 
                current_day_count
            )
            
            # 合并提取的信息和已有信息
            final_city = extracted_city or current_city
            final_day_count = extracted_day_count or current_day_count
            
            # 第二步：生成引导回复
            response_content = self._generate_guidance_response(
                final_city,
                final_day_count,
                conversation_history,
                user_input
            )
            
            logger.info(f"对话引导完成: city={final_city}, day_count={final_day_count}")
            
            return {
                "response": response_content,
                "city_name": final_city,
                "day_count": final_day_count,
                "messages": [AIMessage(content=response_content)]
            }
        
        except Exception as e:
            logger.error(f"对话引导异常: {e}", exc_info=True)
            # 降级：使用规则匹配提取信息
            user_input = self._get_last_user_input(state)
            extracted_city, extracted_day_count = SimpleIntentExtractor.extract_from_input(user_input)
            
            # 合并提取的信息和已有信息
            current_city = state.get("city_name")
            current_day_count = state.get("day_count")
            final_city = extracted_city or current_city
            final_day_count = extracted_day_count or current_day_count
            
            # 降级回复
            missing_info = []
            if not final_city:
                missing_info.append("城市")
            if not final_day_count:
                missing_info.append("天数")
            
            if missing_info:
                response = f"请告诉我您的{'和'.join(missing_info)}信息，以便我为您规划旅游路线。"
            else:
                response = "好的，我已经了解了您的需求。"
            
            return {
                "response": response,
                "city_name": final_city,
                "day_count": final_day_count,
                "messages": [AIMessage(content=response)]
            }
    
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
    
    def _extract_with_llm(
        self,
        user_input: str,
        conversation_history: List,
        current_city: Optional[str] = None,
        current_day_count: Optional[int] = None
    ) -> tuple[Optional[str], Optional[int]]:
        """
        使用 LLM 从用户输入中提取城市和天数信息
        
        Returns:
            (城市名, 天数) 元组
        """
        try:
            # 构建上下文信息
            context_info = []
            if current_city:
                context_info.append(f"已知城市：{current_city}")
            if current_day_count:
                context_info.append(f"已知天数：{current_day_count}")
            
            context_str = "\n".join(context_info) if context_info else "尚未获取到任何信息"
            
            # 构建提示词
            extraction_prompt = f"""当前已知信息：
{context_str}

对话历史：
{self._format_conversation_history(conversation_history)}

用户最新输入：{user_input}

请从用户输入中提取旅游信息。输出 JSON 格式：
{{"city_name": "城市名或null", "day_count": 数字或null}}

注意：
1. 如果用户输入中没有提到城市或天数，对应字段返回 null
2. 如果已知信息中有城市或天数，但用户输入中没有新的信息，返回 null（保持已有信息）
3. 只提取用户明确提到的新信息"""
            
            # 创建 LLM 实例（使用 JSON 格式）
            llm = LLMFactory.create_llm(
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            # 构建消息
            messages = [
                SystemMessage(content="你是一个信息提取助手，从用户输入中提取旅游相关信息。"),
                HumanMessage(content=extraction_prompt)
            ]
            
            # 调用 LLM
            response = llm.invoke(messages)
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # 解析 JSON 响应
            result = json.loads(response_content)
            
            city_name = result.get("city_name")
            day_count = result.get("day_count")
            
            # 处理 null 值
            if city_name == "null" or city_name is None:
                city_name = None
            if day_count == "null" or day_count is None:
                day_count = None
            else:
                try:
                    day_count = int(day_count) if day_count else None
                except (ValueError, TypeError):
                    day_count = None
            
            logger.info(f"LLM 提取信息: city={city_name}, day_count={day_count}")
            return city_name, day_count
            
        except Exception as e:
            logger.warning(f"LLM 提取信息失败，降级到规则匹配: {e}")
            # 降级到规则匹配
            return SimpleIntentExtractor.extract_from_input(user_input)
    
    def _generate_guidance_response(
        self,
        current_city: Optional[str],
        current_day_count: Optional[int],
        conversation_history: List,
        user_input: str
    ) -> str:
        """
        生成引导回复
        
        Args:
            current_city: 当前已知的城市
            current_day_count: 当前已知的天数
            conversation_history: 对话历史
            user_input: 用户输入
            
        Returns:
            引导回复文本
        """
        try:
            # 加载系统提示词
            system_prompt = self._load_system_prompt()
            
            # 构建上下文信息
            context_info = []
            if current_city:
                context_info.append(f"已知城市：{current_city}")
            if current_day_count:
                context_info.append(f"已知天数：{current_day_count}")
            
            context_str = "\n".join(context_info) if context_info else "尚未获取到任何信息"
            
            # 构建提示词
            guidance_prompt = f"""当前已知信息：
{context_str}

对话历史：
{self._format_conversation_history(conversation_history)}

用户最新输入：{user_input}

请根据当前已知信息，友好地引导用户提供缺失的信息（城市或天数）。
- 如果城市和天数都已知，请确认信息并表示感谢
- 如果缺少城市，请询问目的地
- 如果缺少天数，请询问旅游天数
- 保持友好、自然的对话风格，一次只问一个问题"""
            
            # 创建 LLM 实例
            llm = LLMFactory.create_llm(
                temperature=0.7,
                max_tokens=300
            )
            
            # 构建消息
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=guidance_prompt)
            ]
            
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
    
    def _format_conversation_history(self, history: List) -> str:
        """格式化对话历史"""
        if not history:
            return "（无历史对话）"
        
        formatted = []
        for msg in history[-5:]:  # 只取最近5条消息
            if isinstance(msg, HumanMessage):
                formatted.append(f"用户：{msg.content if hasattr(msg, 'content') else str(msg)}")
            elif isinstance(msg, AIMessage):
                formatted.append(f"助手：{msg.content if hasattr(msg, 'content') else str(msg)}")
        
        return "\n".join(formatted) if formatted else "（无历史对话）"

