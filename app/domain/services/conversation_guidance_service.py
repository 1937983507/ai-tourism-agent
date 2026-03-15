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

    # guidance_reason -> 传给 LLM 的说明文字
    _REASON_DESC_MAP = {
        "missing_city":        "用户未提及旅游城市",
        "ambiguous_city":      "用户提及的城市表达模糊（如东北、江南、西北等大区/方位词），需要引导用户说出具体城市",
        "multi_city":          "用户同时提及了多个城市，需要引导用户选择一个主要目的地",
        "foreign_city":        "用户提及的城市在中国境外，需要引导用户选择国内目的地",
        "missing_day":         "用户未提及旅游天数",
        "invalid_day_zero":    "用户给出的天数为 0，需要引导用户给出合理天数",
        "invalid_day_overflow": "用户给出的天数超过了 30 天上限，需要引导用户缩短天数",
        "ambiguous_day":       "用户的天数表达模糊（如三四天、好几天），需要引导用户给出具体天数",
        "missing_both":        "用户既未提及城市也未提及天数，优先引导用户提供城市",
    }

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
            conversation_history = state.get("messages", [])
            current_city = state.get("city_name")
            current_day_count = state.get("day_count")
            guidance_reason = state.get("guidance_reason")

            # 仅负责生成引导回复：城市/天数等关键信息由上游意图识别节点统一提取并写入 state。
            response_content = self._generate_guidance_response(
                current_city,
                current_day_count,
                conversation_history,
                guidance_reason,
            )

            logger.info(f"对话引导完成: city={current_city}, day_count={current_day_count}, reason={guidance_reason}")

            return {
                "response": response_content,
                "city_name": current_city,
                "day_count": current_day_count,
                "guidance_reason": guidance_reason,
                "messages": [AIMessage(content=response_content)]
            }

        except Exception as e:
            logger.error(f"对话引导异常: {e}", exc_info=True)

            # 降级：仅做最小化引导回复
            current_city = state.get("city_name")
            current_day_count = state.get("day_count")

            missing_info = []
            if not current_city:
                missing_info.append("城市")
            if not current_day_count:
                missing_info.append("天数")
            response = (
                f"请告诉我您的{'和'.join(missing_info)}信息，以便我为您规划旅游路线。"
                if missing_info else "好的，我已经了解了您的需求。"
            )
            return {
                "response": response,
                "city_name": current_city,
                "day_count": current_day_count,
                "guidance_reason": state.get("guidance_reason"),
                "messages": [AIMessage(content=response)]
            }

    def _generate_guidance_response(
        self,
        current_city: Optional[str],
        current_day_count: Optional[int],
        conversation_history: List,
        guidance_reason: Optional[str] = None,
    ) -> str:
        """
        生成引导回复

        Args:
            current_city: 当前已知的城市
            current_day_count: 当前已知的天数
            conversation_history: 对话历史
            guidance_reason: 引导原因（来自 state.guidance_reason）

        Returns:
            引导回复文本
        """
        try:
            # 加载系统提示词
            guidance_system_prompt = self._load_system_prompt()

            # 构建已知信息上下文
            context_info = []
            if current_city:
                context_info.append(f"已知城市：{current_city}")
            if current_day_count is not None:
                context_info.append(f"已知天数：{current_day_count}")
            
            context_str = "\n".join(context_info) if context_info else "尚未获取到任何信息"

            # 构建引导原因说明，直接查 _REASON_DESC_MAP
            reason_str = self._REASON_DESC_MAP.get(
                guidance_reason or "",
                "信息不完整，请引导用户补充城市或天数"
            )
            guidance_reason_str = f"引导原因：{reason_str}"

            # 格式化 user prompt
            guidance_user_prompt_template = self._load_guidance_user_prompt_template()
            guidance_user_prompt = guidance_user_prompt_template.format(
                context_str=context_str,
                guidance_reason_str=guidance_reason_str,
            )

            # 构建消息列表
            messages = [SystemMessage(content=guidance_system_prompt)]

            # 添加对话历史（如果有）
            # 只保留 HumanMessage，过滤掉历史 AIMessage
            # 避免 LLM 将上一轮自己的引导语拼接到新回复末尾
            if conversation_history:
                from langchain_core.messages import HumanMessage as _HumanMessage
                human_history = [msg for msg in conversation_history if isinstance(msg, _HumanMessage)]
                for msg in human_history[-5:]:
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
            return "好的，我已经了解了您的需求。"
