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

    @classmethod
    def extract_customization_requirements(cls, user_input: str) -> Optional[str]:
        """
        规则兜底抽取定制化需求（半结构化 token 字符串）。
        仅在 LLM 解析失败/异常时使用，用于尽量保留偏好信息。

        输出格式建议：
        - ';' 分隔多个 token
        - token 形如 key=value
        - interests 使用 ',' 分隔多个兴趣词
        """
        if not user_input or not user_input.strip():
            return None

        tokens = []

        # 出游人群
        if any(x in user_input for x in ["情侣", "约会"]):
            tokens.append("companions=情侣")
        elif any(x in user_input for x in ["家庭", "带娃", "带孩子", "亲子"]):
            tokens.append("companions=家庭")
        elif any(x in user_input for x in ["单人", "一个人", "独自"]):
            tokens.append("companions=单人")

        # 饮食偏好（辣）
        if any(x in user_input for x in ["不吃辣", "不辣", "不能吃辣", "不敢吃辣", "拒绝辣"]):
            tokens.append("diet=不吃辣")
        elif any(x in user_input for x in ["爱吃辣", "喜欢吃辣", "能吃辣", "很辣", "要辣"]):
            tokens.append("diet=爱吃辣")

        # 年龄/同行者
        if any(x in user_input for x in ["有老人", "带老人", "父母同行", "老人一起"]):
            tokens.append("elderly=有老人")
        if any(x in user_input for x in ["有小孩", "带小孩", "带孩子", "孩子一起", "亲子同行"]):
            tokens.append("kids=有小孩")

        interests = []
        if any(x in user_input for x in ["人文", "文化", "博物馆", "历史", "古镇", "古迹"]):
            interests.append("人文景观")
        if any(x in user_input for x in ["自然", "风景", "山", "海", "湖", "森林", "徒步", "自然景观"]):
            interests.append("自然景观")
        if any(x in user_input for x in ["美食", "吃", "特色小吃", "餐厅"]):
            interests.append("美食")

        if interests:
            # 去重保持顺序
            seen = set()
            uniq = []
            for x in interests:
                if x not in seen:
                    uniq.append(x)
                    seen.add(x)
            tokens.append("interests=" + ",".join(uniq))

        return ";".join(tokens) if tokens else None

    @classmethod
    def detect_intent_type(cls, user_input: str, has_city_or_day: bool = False) -> str:
        """
        规则兜底判断意图类型：
        - 若输入包含旅游关键词，或已提取到 city/day，则按 tourism_need_guidance
        - 否则按 non_tourism
        """
        tourism_keywords = ["旅游", "旅行", "游玩", "景点", "攻略", "行程", "路线"]
        is_tourism = any(keyword in user_input for keyword in tourism_keywords)

        if has_city_or_day:
            is_tourism = True

        return "tourism_need_guidance" if is_tourism else "non_tourism"

