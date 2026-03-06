"""路线规划节点"""
from typing import Dict, Any
from loguru import logger
from app.graph.state import AgentState
from app.domain.services.planning_service import PlanningService

# 创建服务实例
_planning_service = PlanningService()


def plan_route_node(state: AgentState) -> dict:
    """路线规划节点：基于天气和景点信息生成旅游攻略"""
    logger.info("执行路线规划节点")
    
    try:
        # 开始生成旅游攻略
        planning_result = _planning_service.plan_route(state)
        
        # 如果有错误，返回错误信息
        if planning_result.get("error"):
            return planning_result
        
        # 返回路线规划结果
        return planning_result
    
    except Exception as e:
        logger.exception(f"路线规划节点异常: {e}")
        return {"error": f"路线规划失败: {str(e)}"}

