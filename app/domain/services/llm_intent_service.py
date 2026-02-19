"""LLM 意图识别服务"""
import logging
import json
import os
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory

logger = logging.getLogger(__name__)


class LLMIntentService:
    """LLM 意图识别服务类"""
    
    def __init__(self):
        """初始化 LLM 意图识别服务"""
        # 获取项目根目录（从 domain/services/ 向上三级到 app/，再进入 prompt/）
        current_dir = os.path.dirname(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        prompt_dir = os.path.join(app_dir, "prompt")
        self.system_prompt_path = os.path.join(prompt_dir, "intent-recognition-system-prompt.txt")
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        if os.path.exists(self.system_prompt_path):
            with open(self.system_prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return """你是一位专业的意图识别助手。请分析用户输入，识别意图并提取关键信息。
输出 JSON 格式：{"intent_type": "tourism" | "non_tourism" | "tourism_need_guidance", "city_name": "城市名或null", "day_count": 数字或null, "confidence": 0.0-1.0}"""
    
    def recognize_intent(self, user_input: str) -> Dict[str, Any]:
        """
        使用 LLM 识别用户意图并提取信息
        
        Args:
            user_input: 用户输入内容
            
        Returns:
            包含意图识别结果的字典：
            - intent_type: "tourism" | "non_tourism" | "tourism_need_guidance"
            - city_name: 城市名称（如果提取到）
            - day_count: 天数（如果提取到）
            - confidence: 置信度
        """
        try:
            # 加载系统提示词
            system_prompt = self._load_system_prompt()
            
            # 创建 LLM 实例（使用 JSON 格式）
            llm = LLMFactory.create_llm(
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # 构建消息
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"用户输入：{user_input}\n\n请分析用户意图并提取信息。")
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
            return self._fallback_extraction(user_input)
    
    def _fallback_extraction(self, user_input: str) -> Dict[str, Any]:
        """降级提取方法（当 LLM 调用失败时使用）"""
        # 简单的关键词匹配
        tourism_keywords = ["旅游", "旅行", "游玩", "景点", "攻略", "行程", "路线"]
        is_tourism = any(keyword in user_input for keyword in tourism_keywords)
        
        if is_tourism:
            return {
                "intent_type": "tourism_need_guidance",
                "city_name": None,
                "day_count": None,
                "confidence": 0.5
            }
        else:
            return {
                "intent_type": "non_tourism",
                "city_name": None,
                "day_count": None,
                "confidence": 0.5
            }


