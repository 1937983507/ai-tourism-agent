"""景点搜索工具"""
import httpx
from typing import Optional
from loguru import logger
from langchain.tools import tool
from app.config import settings


@tool
def poi_search(city_name: str, poi_count: int = 10) -> str:
    """
    根据城市名获取景点信息
    
    Args:
        city_name: 城市名称，例如: 北京、上海、西安（不要加后缀）
        poi_count: 要返回的景点数量，例如: 10
    
    Returns:
        景点信息 JSON 字符串
    """
    logger.info(f"调用 POI 搜索工具，城市: {city_name}, 数量: {poi_count}")
    
    try:
        # 参数验证
        if not city_name or not city_name.strip():
            return '{"error": "城市名称不能为空"}'
        
        if poi_count is None or poi_count <= 0:
            poi_count = 10
        
        # 处理城市名称：如果尾缀含有"市"，则删除
        city_name = city_name.strip()
        if city_name.endswith("市"):
            city_name = city_name[:-1]
            # logger.info(f"城市名称处理后: {city_name}")
        
        # 通过 HTTP 调用 Java 服务的工具接口
        java_url = f"{settings.java_service_url}/api/tools/poi"
        params = {
            "city_name": city_name,
            "count": poi_count
        }
        
        headers = {}
        if settings.java_service_internal_token:
            headers["Authorization"] = f"Bearer {settings.java_service_internal_token}"
        
        # trust_env=False: 避免使用系统代理，防止对 localhost 的请求被代理拦截导致 502
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            response = client.get(java_url, params=params, headers=headers)
            
            if not response.is_success:
                logger.error(f"Java POI 接口调用失败: {response.status_code}")
                return f'{{"error": "查询景点信息失败: HTTP {response.status_code}"}}'
            
            result = response.json()
            import json
            return json.dumps(result, ensure_ascii=False, indent=2)
    
    except httpx.TimeoutException:
        logger.error("Java POI 接口调用超时")
        return '{"error": "查询景点信息超时，请稍后重试"}'
    except Exception as e:
        logger.error(f"POI 搜索异常: {e}", exc_info=True)
        return f'{{"error": "查询景点信息失败: {str(e)}"}}'

