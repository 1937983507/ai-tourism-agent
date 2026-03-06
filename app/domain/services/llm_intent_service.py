"""LLM 意图识别服务"""
import json
import os
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory
from app.domain.services.simple_intent_extractor import SimpleIntentExtractor

if TYPE_CHECKING:
    from app.graph.state import AgentState


class LLMIntentService:
    """LLM 意图识别服务类"""
    
    def __init__(self):
        """初始化 LLM 意图识别服务"""
        file_path = os.path.abspath(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
        prompt_dir = os.path.join(app_dir, "prompt")
        # 意图识别服务，用于识别用户意图并提取信息
        self.system_prompt_path = os.path.join(prompt_dir, "intent-recognition-system-prompt.txt")
        self.user_prompt_path = os.path.join(prompt_dir, "intent-recognition-user-prompt.txt")
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            with open(self.system_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"系统提示词文件不存在: {self.system_prompt_path}")

    def _load_user_prompt_template(self) -> str:
        """加载用户提示词模板"""
        try:
            with open(self.user_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"用户提示词文件不存在: {self.user_prompt_path}")
    
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
    
    def recognize_intent(self, state: "AgentState") -> Dict[str, Any]:
        """
        使用 LLM 识别用户意图并提取信息
        
        Args:
            state: Agent 状态对象
            
        Returns:
            包含意图识别结果的字典：
            - intent_type: "tourism" | "non_tourism" | "tourism_need_guidance"
            - city_name: 城市名称（如果提取到）
            - day_count: 天数（如果提取到）
            - confidence: 置信度
        """
        try:
            # 从 state 中提取信息
            user_input = self._get_last_user_input(state)
            conversation_history = state.get("messages", [])
            current_city = state.get("city_name")
            current_day_count = state.get("day_count")
            in_guidance_mode = state.get("in_guidance_mode", False)
            
            # 加载系统提示词
            system_prompt = self._load_system_prompt()
            user_prompt_template = self._load_user_prompt_template()
            
            # 构建上下文信息
            context_parts = []
            if in_guidance_mode:
                context_parts.append("注意：当前处于旅游规划引导模式，用户可能在回答引导问题。")
            if current_city:
                context_parts.append(f"已知城市：{current_city}")
            if current_day_count:
                context_parts.append(f"已知天数：{current_day_count}")
            
            # 构建对话历史上下文
            history_context = ""
            if conversation_history:
                history_messages = []
                for msg in conversation_history[-4:]:  # 只取最近4条消息作为上下文
                    if hasattr(msg, 'content'):
                        role = "用户" if isinstance(msg, HumanMessage) else "助手"
                        history_messages.append(f"{role}：{msg.content}")
                if history_messages:
                    history_context = "\n对话历史：\n" + "\n".join(history_messages)
            
            context_str = "\n".join(context_parts) if context_parts else ""
            
            context_block = f"\n\n上下文信息：\n{context_str}\n" if context_str else "\n"
            history_block = f"{history_context}\n" if history_context else ""

            # 构建用户提示（从 prompt 文件读取）
            user_prompt = (
                user_prompt_template
                .replace("{user_input}", user_input)
                .replace("{context_block}", context_block)
                .replace("{history_block}", history_block)
            )
            
            # 创建 LLM 实例（使用 JSON 格式）
            llm = LLMFactory.create_llm(
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # 构建消息
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # 调用 LLM
            response = llm.invoke(messages)
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # 解析 JSON 响应
            try:
                result = json.loads(response_content)
                
                # 验证和标准化结果
                intent_type = result.get("intent_type", "tourism_need_guidance")
                city_name = result.get("city_name")
                day_count = result.get("day_count")
                confidence = result.get("confidence", 0.5)
                
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
                
                logger.info(f"意图识别结果: intent_type={intent_type}, city_name={city_name}, day_count={day_count}, confidence={confidence}")
                
                return {
                    "intent_type": intent_type,
                    "city_name": city_name,
                    "day_count": day_count,
                    "confidence": confidence
                }
            except json.JSONDecodeError as e:
                logger.error(f"解析 JSON 响应失败: {e}, 响应内容: {response_content}")
                # 尝试从文本中提取信息
                return self._fallback_extraction(user_input)
        
        except Exception as e:
            logger.error(f"意图识别异常: {e}", exc_info=True)
            # 降级到简单提取
            user_input = self._get_last_user_input(state)
            return self._fallback_extraction(user_input)
    
    def _fallback_extraction(self, user_input: str) -> Dict[str, Any]:
        """降级提取方法（当 LLM 调用失败时使用规则匹配）"""
        # 使用统一的简单意图提取器
        city, day_count = SimpleIntentExtractor.extract_from_input(user_input)
        
        # 简单的关键词匹配判断是否为旅游意图
        tourism_keywords = ["旅游", "旅行", "游玩", "景点", "攻略", "行程", "路线"]
        is_tourism = any(keyword in user_input for keyword in tourism_keywords)
        
        # 如果提取到城市或天数，也认为是旅游意图
        if city or day_count:
            is_tourism = True
        
        if is_tourism:
            return {
                "intent_type": "tourism_need_guidance",
                "city_name": city,
                "day_count": day_count,
                "confidence": 0.5
            }
        else:
            return {
                "intent_type": "non_tourism",
                "city_name": None,
                "day_count": None,
                "confidence": 0.5
            }


