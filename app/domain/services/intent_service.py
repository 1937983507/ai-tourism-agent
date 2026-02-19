"""意图理解服务"""
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class IntentService:
    """意图理解服务类"""
    
    def extract_intent(self, user_input: str) -> Dict[str, Any]:
        """
        从用户输入中提取意图信息（城市、天数、偏好等）
        
        Args:
            user_input: 用户输入内容
            
        Returns:
            包含提取信息的字典（city_name, day_count 等）
        """
        result = {}
        
        # 提取城市名（常见城市）
        cities = [
            "北京", "上海", "广州", "深圳", "杭州", "成都", "西安", "南京", "武汉", "重庆",
            "天津", "苏州", "长沙", "郑州", "东莞", "青岛", "沈阳", "宁波", "昆明", "大连",
            "厦门", "合肥", "佛山", "福州", "哈尔滨", "济南", "温州", "石家庄", "长春", "泉州"
        ]
        
        city_name = None
        for city in cities:
            if city in user_input:
                city_name = city
                break
        
        # 如果没找到中文城市，尝试提取英文城市名（简单处理）
        if not city_name:
            # 提取可能的英文城市名（首字母大写的单词）
            words = user_input.split()
            for word in words:
                if word and word[0].isupper() and len(word) > 2:
                    city_name = word
                    break
        
        if city_name:
            result["city_name"] = city_name
            logger.info(f"提取到城市: {city_name}")
        
        # 提取天数
        day_pattern = r'(\d+)\s*[日天]'
        day_match = re.search(day_pattern, user_input)
        if day_match:
            result["day_count"] = int(day_match.group(1))
            logger.info(f"提取到天数: {result['day_count']}")
        else:
            # 默认3天
            result["day_count"] = 3
        
        logger.info(f"意图理解完成，城市: {city_name}, 天数: {result.get('day_count')}")
        return result

