"""数据获取节点"""
from typing import Dict, Any
from loguru import logger
from app.graph.state import AgentState
from app.domain.services.data_service import DataService

# 创建服务实例
_data_service = DataService()


def fetch_weather_node(state: AgentState) -> dict:
    """天气查询节点：调用天气工具获取预报信息"""
    logger.info("执行天气查询节点")
    
    # 只返回需要更新的字段，避免并行节点更新冲突
    result = {}
    
    # 从状态中获取城市信息
    city_name = state.get("city_name")
    day_count = state.get("day_count", 7)
    
    # 调用数据服务获取天气信息
    weather_data = _data_service.fetch_weather(city_name, day_count)
    result["weather_data"] = weather_data
    
    return result


def fetch_poi_node(state: AgentState) -> dict:
    """景点查询节点：调用 POI 搜索工具获取景点信息"""
    logger.info("执行景点查询节点")
    
    # 只返回需要更新的字段，避免并行节点更新冲突
    result = {}
    
    # 从状态中获取城市信息
    city_name = state.get("city_name")
    day_count = state.get("day_count", 7)
    
    # 调用数据服务获取景点信息
    poi_data = _data_service.fetch_poi(city_name, day_count*3)
    result["poi_data"] = poi_data
    
    return result

