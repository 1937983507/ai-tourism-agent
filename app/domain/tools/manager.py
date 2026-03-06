"""工具管理器"""
from typing import List
from loguru import logger
from langchain.tools import BaseTool
from app.domain.tools.weather import weather_forecast
from app.domain.tools.poi import poi_search


def get_tools() -> List[BaseTool]:
    """获取所有工具列表"""
    tools = [
        weather_forecast,
        poi_search,
        # 后续可以添加更多工具
    ]
    
    logger.info(f"已注册 {len(tools)} 个工具: {[tool.name for tool in tools]}")
    return tools

