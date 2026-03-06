"""天气预报工具"""
import logging
import httpx
from typing import Optional, Tuple
from langchain.tools import tool
from app.config import settings

logger = logging.getLogger(__name__)

# 地理编码 API
ENCODE_API_URL = "http://api.openweathermap.org/geo/1.0/direct"
# Open-Meteo API
OPEN_METEO_API_URL = "https://api.open-meteo.com/v1/forecast"


@tool
def weather_forecast(city_name: str, day_count: int = 7) -> str:
    """
    根据城市名获取未来若干天的逐天天气预报，天数范围1-16
    
    Args:
        city_name: 城市名称，例如: 北京 / Shanghai / New York
        day_count: 要返回的预测天数，范围1-16
    
    Returns:
        天气预报 JSON 字符串
    """
    logger.info(f"调用天气工具，城市: {city_name}, 天数: {day_count}")
    
    try:
        # 参数验证
        if not city_name or not city_name.strip():
            return "城市名称不能为空"
        
        if day_count < 1:
            day_count = 1
        if day_count > 16:
            day_count = 16
        
        # 1. 地理编码获取经纬度
        lat, lon = _get_city_coordinates(city_name)
        if lat is None or lon is None:
            return "获取城市经纬度失败，请检查城市名称"
        
        # 2. 调用 Open-Meteo API
        from datetime import date, timedelta
        today = date.today() + timedelta(1)
        end_date = today + timedelta(days=day_count - 1)
        
        url = (
            f"{OPEN_METEO_API_URL}?"
            f"latitude={lat}&longitude={lon}&"
            f"start_date={today}&end_date={end_date}&"
            f"daily=temperature_2m_min,temperature_2m_max,temperature_2m_mean,"
            f"precipitation_sum,snowfall_sum,windspeed_10m_max,windgusts_10m_max,winddirection_10m_dominant&"
            f"timezone=auto"
        )
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            if not response.is_success:
                logger.error(f"Open-Meteo API 调用失败: {response.status_code}")
                return "暂时无法获取天气数据，请忽略此错误"
            
            data = response.json()
            daily = data.get("daily", {})
            
            # 3. 格式化返回结果
            result = []
            times = daily.get("time", [])
            t_min = daily.get("temperature_2m_min", [])
            t_max = daily.get("temperature_2m_max", [])
            t_mean = daily.get("temperature_2m_mean", [])
            precip = daily.get("precipitation_sum", [])
            
            for i in range(len(times)):
                day_weather = {
                    "日期": times[i],
                    "最低温(℃)": round(t_min[i], 1) if i < len(t_min) else 0,
                    "最高温(℃)": round(t_max[i], 1) if i < len(t_max) else 0,
                    "平均温(℃)": round(t_mean[i], 1) if i < len(t_mean) else 0,
                    "降水量(mm)": round(precip[i], 1) if i < len(precip) else 0,
                }
                result.append(day_weather)
            
            import json
            return json.dumps(result, ensure_ascii=False, indent=2)
    
    except Exception as e:
        logger.error(f"获取天气数据异常: {e}", exc_info=True)
        return "获取天气数据时发生错误，请忽略此错误"


def _get_city_coordinates(city_name: str) -> Tuple[Optional[float], Optional[float]]:
    """获取城市经纬度"""
    try:
        api_key = settings.openweather_api_key
        if not api_key:
            logger.warning("OpenWeather API Key 未配置")
            return None, None
        
        url = f"{ENCODE_API_URL}?q={city_name}&limit=1&appid={api_key}"
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            if not response.is_success:
                logger.error(f"地理编码 API 调用失败: {response.status_code}")
                return None, None
            
            data = response.json()
            if not data or len(data) == 0:
                logger.warning(f"未找到城市: {city_name}")
                return None, None
            
            city_data = data[0]
            lat = city_data.get("lat")
            lon = city_data.get("lon")
            
            logger.info(f"城市 {city_name} 的坐标: ({lat}, {lon})")
            return lat, lon
    
    except Exception as e:
        logger.error(f"获取城市坐标异常: {e}", exc_info=True)
        return None, None

