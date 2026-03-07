"""天气预报工具"""
import os
import time
from typing import Optional, Tuple

import httpx
import jwt
from functools import lru_cache
from loguru import logger
from langchain.tools import tool
from app.config import settings

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
    logger.info(f"调用天气工具，城市: {city_name}, 天数: {day_count}, 提供商: {settings.weather_provider}")
    
    try:
        # 参数验证
        if not city_name or not city_name.strip():
            return "城市名称不能为空"
        
        if day_count < 1:
            day_count = 1
        if day_count > 16:
            day_count = 16
        
        # 根据配置选择天气服务提供商
        if settings.weather_provider.lower() == "qweather":
            return _fetch_weather_qweather(city_name, day_count)
        else:
            # 默认使用 OpenWeather + Open-Meteo
            return _fetch_weather_openweather(city_name, day_count)
    
    except Exception as e:
        logger.error(f"获取天气数据异常: {e}", exc_info=True)
        return "获取天气数据时发生错误，请忽略此错误"


def _fetch_weather_openweather(city_name: str, day_count: int) -> str:
    """使用 OpenWeather + Open-Meteo API 获取天气"""
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


def _fetch_weather_qweather(city_name: str, day_count: int) -> str:
    """使用和风天气 API 获取天气"""
    jwt_token = _generate_qweather_jwt()
    if not jwt_token:
        logger.warning("和风天气 JWT 未正确配置或生成失败，回退到 OpenWeather")
        return _fetch_weather_openweather(city_name, day_count)
    
    try:
        # 1. 获取城市 LocationID（和风天气需要）
        location_id = _get_qweather_location_id(city_name, jwt_token)
        if not location_id:
            logger.warning(f"和风天气未找到城市 {city_name}，回退到 OpenWeather")
            return _fetch_weather_openweather(city_name, day_count)
        
        # 2. 调用和风天气 API（最多支持 15 天预报）
        day_count+=1
        if day_count <= 3:
            period = 3
        elif day_count <= 7:
            period = 7
        elif day_count <= 10:
            period = 10
        else:
            period = 15

        base_url = _get_qweather_base_url()
        url = f"{base_url}/v7/weather/{period}d"
        params = {
            "location": location_id,
            "lang": "zh"
        }
        headers = {
            "Authorization": f"Bearer {jwt_token}"
        }
        
        with httpx.Client(timeout=10.0, headers=headers) as client:
            response = client.get(url, params=params)
            if not response.is_success:
                logger.error(f"和风天气 API 调用失败: {response.status_code}")
                logger.warning("回退到 OpenWeather")
                return _fetch_weather_openweather(city_name, day_count)
            
            data = response.json()
            if data.get("code") != "200":
                logger.error(f"和风天气 API 返回错误: {data.get('code')}, {data.get('msg')}")
                logger.warning("回退到 OpenWeather")
                return _fetch_weather_openweather(city_name, day_count)
            
            # 3. 格式化返回结果
            daily = data.get("daily", [])
            result = []

            # QWeather 返回的 daily 通常包含「今天 + 未来几天」
            # 业务上我们希望与 Open-Meteo 行为对齐：从“明天”开始算 day_count 天
            # 因此这里优先跳过索引 0（今天），从索引 1 开始取 day_count 条
            start_idx = 1 if len(daily) > 1 else 0

            for day_data in daily[start_idx:day_count]:
                day_weather = {
                    "日期": day_data.get("fxDate", ""),
                    "最低温(℃)": float(day_data.get("tempMin", 0)),
                    "最高温(℃)": float(day_data.get("tempMax", 0)),
                    "平均温(℃)": (float(day_data.get("tempMin", 0)) + float(day_data.get("tempMax", 0))) / 2,
                    "降水量(mm)": float(day_data.get("precip", 0)),
                    "天气": day_data.get("textDay", ""),
                    "风向": day_data.get("windDirDay", ""),
                    "风力": day_data.get("windScaleDay", ""),
                }
                result.append(day_weather)
            
            import json
            return json.dumps(result, ensure_ascii=False, indent=2)
    
    except Exception as e:
        logger.error(f"和风天气 API 调用异常: {e}", exc_info=True)
        logger.warning("回退到 OpenWeather")
        return _fetch_weather_openweather(city_name, day_count)


def _get_qweather_location_id(city_name: str, jwt_token: str) -> Optional[str]:
    """获取和风天气的城市 LocationID"""
    try:
        base_url = _get_qweather_base_url()
        url = f"{base_url}/geo/v2/city/lookup"
        params = {
            "location": city_name,
        }
        headers = {
            "Authorization": f"Bearer {jwt_token}"
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params, headers=headers)
            if not response.is_success:
                logger.error(f"和风天气地理编码 API 调用失败: {response.status_code}")
                return None
            
            data = response.json()
            if data.get("code") != "200":
                logger.warning(f"和风天气未找到城市: {city_name}, code: {data.get('code')}")
                return None
            
            locations = data.get("location", [])
            if not locations or len(locations) == 0:
                logger.warning(f"和风天气未找到城市: {city_name}")
                return None
            
            location_id = locations[0].get("id")
            logger.info(f"和风天气找到城市 {city_name} 的 LocationID: {location_id}")
            return location_id
    
    except Exception as e:
        logger.error(f"获取和风天气 LocationID 异常: {e}", exc_info=True)
        return None


def _get_qweather_base_url() -> str:
    """
    获取和风天气基础域名：
    - 优先使用环境变量 QWEATHER_API_HOST（settings.qweather_api_host）
    - 未配置时回退到官方域名 https://devapi.qweather.com
    """
    host = (settings.qweather_api_host or "").strip()
    if not host:
        return "https://devapi.qweather.com"
    # 如果用户只配置了主机名而未带协议，默认加上 https://
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"https://{host.rstrip('/')}"


@lru_cache()
def _load_qweather_private_key() -> Optional[str]:
    """加载和风天气 JWT 私钥 PEM 内容"""
    path = (settings.qweather_jwt_private_key_path or "").strip()
    if not path:
        logger.warning("和风天气 JWT 私钥路径未配置（QWEATHER_JWT_PRIVATE_KEY_PATH），无法生成 JWT")
        return None
    
    # 支持相对路径：相对于当前工作目录
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            key = f.read()
            return key
    except FileNotFoundError:
        logger.error(f"和风天气 JWT 私钥文件未找到: {path}")
    except Exception as e:
        logger.error(f"加载和风天气 JWT 私钥失败: {e}", exc_info=True)
    return None


def _generate_qweather_jwt() -> Optional[str]:
    """根据配置生成和风天气所需的 JWT（EdDSA）"""
    project_id = (settings.qweather_jwt_project_id or "").strip()
    key_id = (settings.qweather_jwt_key_id or "").strip()
    private_key = _load_qweather_private_key()
    
    if not project_id or not key_id or not private_key:
        logger.warning(
            "和风天气 JWT 配置不完整："
            f"project_id={bool(project_id)}, key_id={bool(key_id)}, private_key={bool(private_key)}"
        )
        return None
    
    try:
        now = int(time.time())
        payload = {
            "iat": now - 30,
            "exp": now + 900,
            "sub": project_id,
        }
        headers = {
            "kid": key_id,
        }
        token = jwt.encode(payload, private_key, algorithm="EdDSA", headers=headers)
        return token
    except Exception as e:
        logger.error(f"生成和风天气 JWT 失败: {e}", exc_info=True)
        return None


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

