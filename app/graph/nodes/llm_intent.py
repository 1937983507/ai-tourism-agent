"""LLM 意图识别节点"""
from loguru import logger
from app.graph.state import AgentState
from app.domain.services.llm_intent_service import LLMIntentService
from typing import Optional, Dict, List, Tuple

# 创建服务实例
_llm_intent_service = LLMIntentService()

def _parse_customization_tokens(req: str) -> Tuple[Dict[str, str], Dict[str, List[str]], List[str]]:
    """
    将半结构化定制化需求拆成 token。
    期望格式：token 形如 key=value，token 用 ';' 分隔；interests 使用 ',' 分隔多值。
    """
    if not req:
        return {}, {}, []

    # 统一分隔符
    normalized = req.replace("；", ";").strip()
    parts = [p.strip() for p in normalized.split(";") if p.strip()]

    single: Dict[str, str] = {}
    multi: Dict[str, List[str]] = {}
    raw_items: List[str] = []

    for p in parts:
        if "=" not in p:
            raw_items.append(p)
            continue
        key, val = p.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if key == "interests":
            multi[key] = [x.strip() for x in val.replace("，", ",").split(",") if x.strip()]
        else:
            single[key] = val
    return single, multi, raw_items


def _merge_customization_requirements(existing: Optional[str], new_req: Optional[str]) -> Optional[str]:
    """
    多轮对话合并定制化需求：
    - 同类 token（key）覆盖旧值
    - interests 追加去重
    - 其他无法解析的 token 追加（去重）
    """
    if new_req is None:
        return existing
    new_req = new_req.strip()
    if not new_req:
        return existing
    if not existing or not existing.strip():
        return new_req

    e_single, e_multi, e_raw = _parse_customization_tokens(existing)
    n_single, n_multi, n_raw = _parse_customization_tokens(new_req)

    # key=value 的覆盖（默认只按新值覆盖）
    for k, v in n_single.items():
        e_single[k] = v

    # interests 追加去重
    if "interests" in n_multi:
        prev = e_multi.get("interests", [])
        merged = []
        seen = set()
        for x in prev + n_multi["interests"]:
            if x not in seen:
                merged.append(x)
                seen.add(x)
        e_multi["interests"] = merged

    # raw token 追加去重
    raw_merged = []
    seen_raw = set()
    for x in e_raw + n_raw:
        if x not in seen_raw:
            raw_merged.append(x)
            seen_raw.add(x)

    # 重建输出（保持稳定顺序，方便 RAG）
    order = ["companions", "diet", "elderly", "kids", "interests", "pace", "accessibility", "budget"]
    tokens: List[str] = []
    for k in order:
        if k in e_single:
            tokens.append(f"{k}={e_single[k]}")
        if k == "interests" and "interests" in e_multi and e_multi["interests"]:
            tokens.append("interests=" + ",".join(e_multi["interests"]))

    # 把无法识别的 raw token 拼回去
    tokens.extend(raw_merged)

    return ";".join([t for t in tokens if t])


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

        # customization_requirements：支持多轮追加/重写
        if intent_result.get("customization_requirements") is not None:
            merged = _merge_customization_requirements(
                state.get("customization_requirements"),
                intent_result.get("customization_requirements"),
            )
            result["customization_requirements"] = merged

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


