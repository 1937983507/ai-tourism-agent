"""简单意图提取器（规则匹配，作为降级策略）"""
import re
from typing import Optional, Tuple


class SimpleIntentExtractor:
    """简单的意图提取器（规则匹配，作为降级策略）"""
    
    # 常见城市列表
    CITIES = [
        "北京", "上海", "广州", "深圳", "杭州", "成都", "西安", "南京", "武汉", "重庆",
        "天津", "苏州", "长沙", "郑州", "东莞", "青岛", "沈阳", "宁波", "昆明", "大连",
        "厦门", "合肥", "佛山", "福州", "哈尔滨", "济南", "温州", "石家庄", "长春", "泉州"
    ]
    
    # 中文数字映射
    CHINESE_NUMBERS = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10
    }
    
    @classmethod
    def extract_from_input(cls, user_input: str) -> Tuple[Optional[str], Optional[int]]:
        """
        从用户输入中简单提取城市和天数（规则匹配）
        
        Args:
            user_input: 用户输入内容
            
        Returns:
            (城市名, 天数) 元组，未提取到则为 None
        """
        # 提取城市
        city = None
        for c in cls.CITIES:
            if c in user_input:
                city = c
                break
        
        # 提取天数 - 支持多种格式：5天、5日、5、五天等
        day_count = None
        
        # 先尝试匹配数字+天/日
        day_pattern = r'(\d+)\s*[日天]'
        day_match = re.search(day_pattern, user_input)
        if day_match:
            try:
                day_count = int(day_match.group(1))
            except ValueError:
                pass
        
        # 如果没匹配到，尝试匹配纯数字（可能是简短回复如"5天"被简化为"5"）
        if day_count is None:
            number_pattern = r'^(\d+)$'
            number_match = re.search(number_pattern, user_input.strip())
            if number_match:
                try:
                    day_count = int(number_match.group(1))
                    # 限制在合理范围内（1-30天）
                    if not (1 <= day_count <= 30):
                        day_count = None
                except ValueError:
                    pass
        
        # 如果还没匹配到，尝试中文数字
        if day_count is None:
            for chinese, num in cls.CHINESE_NUMBERS.items():
                if chinese in user_input:
                    day_count = num
                    break
        
        return city, day_count

