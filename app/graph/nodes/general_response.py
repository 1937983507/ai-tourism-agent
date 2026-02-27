"""通用回复节点"""
import logging
from typing import Dict, Any
from app.graph.state import AgentState
from app.domain.services.general_response_service import GeneralResponseService

logger = logging.getLogger(__name__)

# 创建服务实例
_general_response_service = GeneralResponseService()


def general_response_node(state: AgentState) -> dict:
    """通用回复节点：处理非旅游意图，直接调用 LLM 进行回复"""
    logger.info("执行通用回复节点")
    
    result = {}
    
    try:
        # 直接调用 LLM 进行回复
        response_result = _general_response_service.generate_response(state)
        
        # 添加 AI 回复消息
        if response_result.get("messages"):
            result["messages"] = response_result["messages"]
        
        logger.info("通用回复生成完成")
        
    except Exception as e:
        logger.error(f"通用回复节点异常: {e}", exc_info=True)
        result["error"] = f"通用回复失败: {str(e)}"
    
    return result


