"""路线规划服务"""
import logging
import os
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory
from app.config import settings

logger = logging.getLogger(__name__)


class PlanningService:
    """路线规划服务类"""
    
    def __init__(self):
        """初始化路线规划服务"""
        # 提示词路径已移动到 app/prompt/ 目录
        import os
        # 获取项目根目录（从 domain/services/ 向上三级到 app/，再进入 prompt/）
        current_dir = os.path.dirname(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        prompt_dir = os.path.join(app_dir, "prompt")
        self.system_prompt_path = os.path.join(prompt_dir, "tour-route-planning-system-prompt.txt")
        self.user_prompt_path = os.path.join(prompt_dir, "route-planning-user-prompt.txt")
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        if os.path.exists(self.system_prompt_path):
            with open(self.system_prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return """你是一位智能旅游规划助手，能够根据用户指定的城市或地区，自动生成合理、详细且实用的旅游攻略。"""
    
    def _load_user_prompt_template(self) -> str:
        """加载用户提示词模板"""
        if os.path.exists(self.user_prompt_path):
            with open(self.user_prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # 默认提示词
            return """请根据以下信息生成旅游攻略：

天气信息：
{weather_info}

景点信息：
{poi_info}

用户需求：
{user_message}

请生成一份详细的旅游攻略，包括：
1. 天气概览与出行提示
2. 每日行程规划（第1天、第2天...）
3. 每个景点的简短介绍
4. 根据天气给出出行建议

直接输出完整的旅游建议，不要显式描述执行步骤。
"""
    
    def plan_route(
        self,
        weather_info: Optional[str],
        poi_info: Optional[str],
        user_message: str
    ) -> Dict[str, Any]:
        """
        生成旅游路线规划
        
        Args:
            weather_info: 天气信息
            poi_info: 景点信息
            user_message: 用户原始需求
            
        Returns:
            包含路线规划的字典，如果失败则包含 error 字段
        """
        try:
            # 加载提示词
            system_prompt = self._load_system_prompt()
            user_prompt_template = self._load_user_prompt_template()
            
            # 使用 LLM 工厂创建流式 LLM 实例
            llm = LLMFactory.create_streaming_llm(
                temperature=0.7,
                max_tokens=settings.openai_max_output_tokens
            )
            
            # 格式化用户提示词
            weather_info_str = weather_info or "暂无天气信息"
            poi_info_str = poi_info or "暂无景点信息"
            
            user_prompt = user_prompt_template.format(
                weather_info=weather_info_str,
                poi_info=poi_info_str,
                user_message=user_message
            )
            
            # 调用 LLM（流式调用，收集完整响应）
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # 流式调用并收集完整内容
            route_plan_parts = []
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    route_plan_parts.append(chunk.content)
            
            route_plan = "".join(route_plan_parts)
            
            logger.info("路线规划完成")
            return {
                "route_plan": route_plan,
                "messages": [AIMessage(content=route_plan)]
            }
        
        except Exception as e:
            logger.error(f"路线规划异常: {e}", exc_info=True)
            return {"error": f"路线规划失败: {str(e)}"}

