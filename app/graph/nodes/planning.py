"""路线规划节点"""
import logging
from typing import Dict, Any
from app.graph.state import AgentState
from langchain_core.messages import HumanMessage
from app.domain.services.planning_service import PlanningService

logger = logging.getLogger(__name__)

# 创建服务实例
_planning_service = PlanningService()


def plan_route_node(state: AgentState) -> dict:
    """路线规划节点：基于天气和景点信息生成旅游攻略"""
    logger.info("执行路线规划节点")
    
    try:
        # 获取天气和景点信息
        weather_info = state.get("weather_data")
        poi_info = state.get("poi_data")
        
        # 获取用户原始需求
        user_message = ""
        if state.get("messages"):
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_message = msg.content if hasattr(msg, 'content') else str(msg)
                    break
        
        # 调用规划服务生成路线
        planning_result = _planning_service.plan_route(
            weather_info=weather_info,
            poi_info=poi_info,
            user_message=user_message
        )
        
        # 如果有错误，返回错误信息
        if planning_result.get("error"):
            return planning_result
        
        # 返回路线规划结果
        return planning_result
    
    except Exception as e:
        logger.error(f"路线规划节点异常: {e}", exc_info=True)
        return {"error": f"路线规划失败: {str(e)}"}

