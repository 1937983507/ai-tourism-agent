"""格式化输出节点"""
from typing import Dict, Any
from loguru import logger
from app.graph.state import AgentState
from app.domain.services.formatting_service import FormattingService
from app.domain.services.callback_service import CallbackService

# 创建服务实例
_formatting_service = FormattingService()
_callback_service = CallbackService()


def format_output_node(state: AgentState) -> dict:
    """格式化输出节点：调用 LLM 生成 JSON 格式的结构化输出，并回调Java后端"""
    logger.info("执行格式化输出节点")
    
    # 只返回需要更新的字段
    result = {}
    
    try:
        # 获取路线规划内容
        route_plan = state.get("route_plan")
        poi_data = state.get("poi_data")
        session_id = state.get("session_id")
        user_id = state.get("user_id")
        
        if not route_plan:
            logger.warning("路线规划内容为空，跳过结构化输出")
            return result
        
        # 调用格式化服务生成 JSON
        formatting_result = _formatting_service.format_to_json(route_plan, poi_data=poi_data)
        
        # 如果有错误，返回错误信息（但保留原始数据）
        if formatting_result.get("error"):
            logger.warning(f"格式化输出失败: {formatting_result.get('error')}")
            # 如果生成 JSON 失败，使用原始数据
            if state.get("route_plan"):
                result["structured_output"] = {
                    "route_plan": state.get("route_plan"),
                    "weather_data": state.get("weather_data"),
                    "poi_data": state.get("poi_data"),
                    "rag_context": state.get("rag_context"),
                    "customization_requirements": state.get("customization_requirements"),
                    "error": "JSON 生成失败，返回原始数据"
                }
        else:
            # 返回格式化结果
            result.update(formatting_result)
            
            # 如果成功生成结构化输出，调用Java后端的callback接口
            structured_output = formatting_result.get("structured_output")

            # format_to_json 已负责校验格式/空 dailyRoutes 等无效情况（会返回 error），这里只做最小触发条件判断
            if structured_output and session_id and user_id:
                try:
                    # 异步发送回调（不阻塞主流程）
                    success = _callback_service.send_structured_output(
                        session_id=session_id,
                        user_id=user_id,
                        structured_output=structured_output
                    )
                    if success:
                        logger.info(f"结构化输出回调成功，session_id: {session_id}")
                    else:
                        logger.warning(f"结构化输出回调失败，session_id: {session_id}")
                except Exception as callback_error:
                    logger.error(f"回调Java后端异常: {callback_error}", exc_info=True)
                    # 回调失败不影响主流程，继续返回结果
    
    except Exception as e:
        logger.error(f"格式化输出节点异常: {e}", exc_info=True)
        # 如果生成 JSON 失败，使用原始数据
        if state.get("route_plan"):
            result["structured_output"] = {
                "route_plan": state.get("route_plan"),
                "weather_data": state.get("weather_data"),
                "poi_data": state.get("poi_data"),
                "rag_context": state.get("rag_context"),
                "customization_requirements": state.get("customization_requirements"),
                "error": "JSON 生成失败，返回原始数据"
            }
    
    return result

