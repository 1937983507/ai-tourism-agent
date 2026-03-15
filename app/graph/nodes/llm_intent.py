"""LLM 意图识别节点"""
from loguru import logger
from app.graph.state import AgentState
from app.domain.services.llm_intent_service import LLMIntentService

# 创建服务实例
_llm_intent_service = LLMIntentService()


def llm_intent_recognition_node(state: AgentState) -> dict:
    """LLM 意图识别节点：使用 LLM 识别用户意图并提取信息"""
    logger.info("执行 LLM 意图识别节点")
    
    result = {}
    
    try:
        # 识别用户意图并提取信息
        intent_result = _llm_intent_service.recognize_intent(state)
        
        # 更新状态
        result["intent_type"] = intent_result.get("intent_type")
        
        # 如果提取到城市和天数，更新状态
        if intent_result.get("city_name"):
            result["city_name"] = intent_result["city_name"]
        elif state.get("city_name"):
            result["city_name"] = state.get("city_name")
            
        if intent_result.get("day_count"):
            result["day_count"] = intent_result["day_count"]
        elif state.get("day_count"):
            result["day_count"] = state.get("day_count")

        # guidance_reason 只取本轮意图识别的结果，不继承上一轮旧值
        # 若本轮为 None（信息已完整），不写入 result，让 state 自然保留或清空
        if intent_result.get("guidance_reason"):
            result["guidance_reason"] = intent_result["guidance_reason"]
 
        # logger.info(f"LLM 意图识别完成: intent_type={result.get('intent_type')}, city={result.get('city_name')}, days={result.get('day_count')}, guidance_reason={result.get('guidance_reason')}")
        
    except Exception as e:
        logger.exception(f"LLM 意图识别节点异常: {e}")
        # 降级处理：标记为需要引导
        result["intent_type"] = "tourism_need_guidance"
    
    return result


