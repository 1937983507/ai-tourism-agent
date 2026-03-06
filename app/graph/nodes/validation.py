"""输入验证节点"""
from typing import Dict, Any
from loguru import logger
from app.graph.state import AgentState
from app.domain.services.validation_service import ValidationService

# 创建服务实例
_validation_service = ValidationService()


def validate_input_node(state: AgentState) -> dict:
    """输入验证节点"""
    logger.info("执行输入验证节点")
    
    # 只返回需要更新的字段
    result = {}
    
    if not state.get("messages") or len(state["messages"]) == 0:
        result["error"] = "输入内容不能为空"
        return result
    
    last_message = state["messages"][-1]
    user_input = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    # 调用验证服务
    validation_result = _validation_service.validate_input(user_input)
    
    # 如果有错误，返回错误信息
    if validation_result.get("error"):
        result["error"] = validation_result["error"]
        return result
    
    logger.info("输入验证通过")
    return result  # 返回空字典表示验证通过


def check_validation_result(state: AgentState) -> str:
    """检查验证结果，决定下一步"""
    if state.get("error"):
        return "error"
    return "continue"

