"""对话引导服务"""
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory

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
            return """你是一位友好的旅游助手。通过友好对话引导用户提供旅游目的地和天数信息。
保持友好、自然的对话风格，一次只问一个问题。"""
    
    def guide_conversation(
        self,
        user_input: str,
        conversation_history: List,
        current_city: Optional[str] = None,
        current_day_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        引导对话，获取缺失的信息
        
        Args:
            user_input: 用户当前输入
            conversation_history: 对话历史（消息列表）
            current_city: 当前已知的城市（如果有）
            current_day_count: 当前已知的天数（如果有）
            
        Returns:
            包含引导回复和可能提取到的信息的字典：
            - response: AI 的引导回复
            - city_name: 如果从对话中提取到城市
            - day_count: 如果从对话中提取到天数
            - messages: 包含回复消息的列表
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

请根据对话历史，友好地引导用户提供缺失的信息（城市或天数）。如果用户已经提供了完整信息，请确认并表示感谢。"""
            
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
            
            # 尝试从用户输入中提取信息（作为补充）
            extracted_city, extracted_day_count = self._extract_from_input(user_input)
            
            # 如果提取到新信息，更新
            final_city = extracted_city or current_city
            final_day_count = extracted_day_count or current_day_count
            
            logger.info(f"对话引导完成: city={final_city}, day_count={final_day_count}")
            
            return {
                "response": response_content,
                "city_name": final_city,
                "day_count": final_day_count,
                "messages": [AIMessage(content=response_content)]
            }
        
        except Exception as e:
            logger.error(f"对话引导异常: {e}", exc_info=True)
            # 降级回复
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
    
    def _extract_from_input(self, user_input: str) -> Tuple[Optional[str], Optional[int]]:
        """从用户输入中简单提取城市和天数（作为补充）"""
        import re
        
        # 提取城市（简单匹配）
        cities = [
            "北京", "上海", "广州", "深圳", "杭州", "成都", "西安", "南京", "武汉", "重庆",
            "天津", "苏州", "长沙", "郑州", "东莞", "青岛", "沈阳", "宁波", "昆明", "大连",
            "厦门", "合肥", "佛山", "福州", "哈尔滨", "济南", "温州", "石家庄", "长春", "泉州"
        ]
        
        city = None
        for c in cities:
            if c in user_input:
                city = c
                break
        
        # 提取天数
        day_count = None
        day_pattern = r'(\d+)\s*[日天]'
        day_match = re.search(day_pattern, user_input)
        if day_match:
            try:
                day_count = int(day_match.group(1))
            except ValueError:
                pass
        
        return city, day_count

