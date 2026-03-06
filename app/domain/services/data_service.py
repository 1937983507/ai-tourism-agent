"""数据获取服务"""
from typing import Dict, Any, Optional
from loguru import logger
from app.domain.tools.manager import get_tools


class DataService:
    """数据获取服务类"""
    
    def fetch_weather(self, city_name: Optional[str], day_count: int = 7) -> Optional[str]:
        """
        获取天气信息
        
        Args:
            city_name: 城市名称
            day_count: 查询天数
            
        Returns:
            天气信息字符串，如果失败返回 None
        """
        if not city_name:
            logger.warning("未提取到城市信息")
            return None
        
        try:
            # 调用天气工具
            tools = get_tools()
            weather_tool = next((t for t in tools if t.name == "weather_forecast"), None)
            
            if weather_tool:
                try:
                    # LangChain 工具调用方式
                    weather_result = weather_tool.invoke({
                        "city_name": city_name,
                        "day_count": day_count
                    })
                    logger.info(f"天气查询成功，城市: {city_name}")
                    return weather_result
                except Exception as e:
                    logger.warning(f"天气查询失败: {e}，将使用默认值")
                    return None
            else:
                logger.warning("天气工具未找到")
                return None
        
        except Exception as e:
            logger.exception(f"天气查询异常: {e}")
            return None
    
    def fetch_poi(self, city_name: Optional[str], poi_count: int = 10) -> Optional[str]:
        """
        获取景点信息
        
        Args:
            city_name: 城市名称
            poi_count: 景点数量
            
        Returns:
            景点信息字符串，如果失败返回 None
        """
        if not city_name:
            logger.warning("未提取到城市信息")
            return None
        
        try:
            # 调用 POI 工具
            tools = get_tools()
            poi_tool = next((t for t in tools if t.name == "poi_search"), None)
            
            if poi_tool:
                try:
                    # LangChain 工具调用方式
                    poi_result = poi_tool.invoke({
                        "city_name": city_name,
                        "poi_count": poi_count
                    })
                    logger.info(f"POI 查询成功，城市: {city_name}")
                    return poi_result
                except Exception as e:
                    logger.warning(f"POI 查询失败: {e}，将使用默认值")
                    return None
            else:
                logger.warning("POI 工具未找到")
                return None
        
        except Exception as e:
            logger.exception(f"POI 查询异常: {e}")
            return None

