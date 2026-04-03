"""路线规划服务"""
import os
from typing import Dict, Any, Optional, TYPE_CHECKING
from loguru import logger
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory
from app.config import settings

if TYPE_CHECKING:
    from app.graph.state import AgentState


class PlanningService:
    """路线规划服务类"""
    
    def __init__(self):
        """初始化路线规划服务"""
        file_path = os.path.abspath(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
        prompt_dir = os.path.join(app_dir, "prompt")
        # 路线规划服务，用于生成旅游路线规划
        self.system_prompt_path = os.path.join(prompt_dir, "route-planning-system-prompt.txt")
        self.user_prompt_path = os.path.join(prompt_dir, "route-planning-user-prompt.txt")
    
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
        
    def plan_route(self, state: "AgentState") -> Dict[str, Any]:
        """
        生成旅游路线规划
        
        Args:
            state: Agent 状态对象
            
        Returns:
            包含路线规划的字典，如果失败则包含 error 字段
        """
        try:
            # 从 state 中提取信息
            weather_info = state.get("weather_data")
            poi_info = state.get("poi_data")
            rag_context = state.get("rag_context")
            city_name = state.get("city_name")
            day_count = state.get("day_count")
            customization_requirements = state.get("customization_requirements")
            if customization_requirements:
                user_message = f"用户将在 {city_name} 旅游 {day_count} 天；用户定制化需求：{customization_requirements}"
            else:
                user_message = f"用户将在 {city_name} 旅游 {day_count} 天"
            
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
            rag_info_str = (rag_context or "").strip() or "暂无相关游记检索结果（或未配置向量库）"

            user_prompt = user_prompt_template.format(
                weather_info=weather_info_str,
                poi_info=poi_info_str,
                rag_info=rag_info_str,
                user_message=user_message,
            )
            
            # 调用 LLM（流式调用）
            # agent_service.py 中的 astream_events 会实时捕获这个流式调用过程中的每个 chunk
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # 流式调用并收集完整内容（用于最终返回和状态更新）
            route_plan_parts = []
            chunk_count = 0
            total_chunk_length = 0
            last_finish_reason = None  # 记录最后一个chunk的finish_reason
            
            try:
                for chunk in llm.stream(messages):
                    # 检查finish_reason（如果chunk有该属性）
                    if hasattr(chunk, 'response_metadata'):
                        metadata = chunk.response_metadata
                        if metadata and 'finish_reason' in metadata:
                            last_finish_reason = metadata['finish_reason']
                            if last_finish_reason == 'length':
                                logger.warning(f"[PLANNING] ⚠️ 检测到finish_reason='length'，输出因token限制被截断！")
                            elif last_finish_reason:
                                logger.info(f"[PLANNING] finish_reason: {last_finish_reason}")
                    
                    if hasattr(chunk, 'content') and chunk.content:
                        content = chunk.content
                        route_plan_parts.append(content)
                        chunk_count += 1
                        chunk_length = len(content)
                        total_chunk_length += chunk_length
                
                route_plan = "".join(route_plan_parts)
                final_length = len(route_plan)
                
                logger.info(f"[PLANNING] LLM流式调用完成 - 总chunks: {chunk_count}, 最终内容长度: {final_length}, finish_reason: {last_finish_reason}")
                
            except Exception as stream_error:
                logger.error(f"[PLANNING] LLM流式调用异常: {stream_error}", exc_info=True)
                # 即使流式调用失败，也尝试返回已收集的内容
                if route_plan_parts:
                    route_plan = "".join(route_plan_parts)
                    logger.warning(f"[PLANNING] 流式调用异常，但已收集部分内容，长度: {len(route_plan)}")
                else:
                    raise
            
            logger.info(f"[PLANNING] 路线规划完成，最终内容长度: {len(route_plan)}")
            return {
                "route_plan": route_plan,
                "messages": [AIMessage(content=route_plan)]
            }
        
        except Exception as e:
            logger.error(f"路线规划异常: {e}", exc_info=True)
            return {"error": f"路线规划失败: {str(e)}"}

