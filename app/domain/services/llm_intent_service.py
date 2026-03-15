"""LLM 意图识别服务"""
import json
import os
from typing import Dict, Any, Optional, TYPE_CHECKING
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory
from app.domain.services.simple_intent_extractor import SimpleIntentExtractor

if TYPE_CHECKING:
    from app.graph.state import AgentState


class LLMIntentService:
    """LLM 意图识别服务类"""

    # 非法 city_name 关键词集合：大区方向、经济区、省份、模糊方位等
    _INVALID_CITY_KEYWORDS = {
        # 大区方向
        "东北", "西北", "华北", "华南", "华东", "华中", "西南", "东南",
        # 经济区 / 城市群
        "长三角", "珠三角", "京津冀", "成渝", "大湾区", "环渤海", "中原城市群",
        # 省份 / 自治区（省级，不等于城市）
        "云南", "西藏", "新疆", "四川", "广东", "湖南", "湖北",
        "贵州", "广西", "福建", "浙江", "江苏", "安徽", "江西",
        "山东", "山西", "河南", "河北", "陕西", "甘肃", "宁夏",
        "青海", "内蒙古", "黑龙江", "吉林", "辽宁", "海南",
        # 直辖市省级别名
        "京", "沪", "津", "渝",
        # 特别行政区 / 港澳台
        "香港", "澳门", "台湾",
        # 省份组合简称
        "江浙沪", "陕甘", "川渝", "云贵川", "两广",
        # 模糊方位
        "南方", "北方", "内陆", "沿海", "边疆",
    }

    # 已知城市名集合，用于多城市检测
    _KNOWN_CITIES = {
        # 一线 / 新一线
        "北京", "上海", "广州", "深圳", "成都", "重庆", "杭州", "武汉", "西安",
        "南京", "天津", "苏州", "长沙", "郑州", "青岛", "沈阳", "宁波", "东莞",
        "无锡", "昆明", "哈尔滨", "大连", "福州", "厦门", "合肥", "济南", "温州",
        "南宁", "贵阳", "太原", "石家庄", "长春", "南昌", "兰州", "呼和浩特",
        "乌鲁木齐", "海口", "西宁", "银川",
        # 华东城市
        "嘉兴", "湖州", "金华", "台州", "衢州", "义乌", "镇江", "南通", "盐城",
        "扬州", "泰州", "徐州", "淮安", "连云港", "宿迁", "常州", "芜湖",
        "蚌埠", "淮南", "马鞍山", "铜陵", "安庆", "黄山市",
        # 华南城市
        "汕尾", "揭阳", "茂名", "阳江", "清远", "韶关", "河源", "梅州",
        "汕头", "湛江", "北海", "珠海", "中山", "佛山", "江门", "肇庆",
        "惠州", "潮州", "漳州",
        # 华中城市
        "宜昌", "襄阳", "荆州", "黄石", "十堰", "恩施", "神农架",
        "岳阳", "常德", "株洲", "湘潭", "衡阳", "邵阳", "张家界", "吉首",
        "洛阳", "开封", "新乡", "焦作", "许昌", "平顶山", "南阳", "信阳",
        # 华北城市
        "保定", "唐山", "秦皇岛", "邯郸", "承德", "张家口", "大同", "朔州",
        "忻州", "临汾", "运城", "晋城", "长治",
        # 西南城市
        "遵义", "安顺", "凯里", "铜仁", "兴义", "泸州", "宜宾", "南充",
        "达州", "绵阳", "德阳", "乐山", "眉山", "雅安", "甘孜", "阿坝",
        "大理", "丽江", "香格里拉", "昭通", "曲靖", "玉溪", "普洱", "西双版纳",
        "德宏", "怒江", "迪庆",
        # 西北城市
        "宝鸡", "咸阳", "延安", "榆林", "汉中", "安康", "商洛",
        "天水", "张掖", "嘉峪关", "武威", "酒泉", "敦煌", "甘南",
        "固原", "中卫", "石嘴山",
        "吐鲁番", "喀什", "伊宁", "库尔勒", "阿克苏", "和田", "哈密",
        # 东北城市
        "延吉", "牡丹江", "伊春", "漠河", "满洲里", "绥芬河", "佳木斯",
        "鸡西", "鹤岗", "双鸭山", "七台河", "黑河", "大庆", "齐齐哈尔",
        "通化", "白山", "四平", "辽源", "白城", "松原",
        "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口", "阜新", "辽阳",
        "盘锦", "铁岭", "朝阳", "葫芦岛",
        # 热门旅游目的地
        "三亚", "三沙", "拉萨", "桂林", "丽江", "张家界", "黄山", "九寨沟",
        "凤凰", "阳朔", "稻城", "亚丁", "色达", "若尔盖", "格尔木",
        "西塔", "北戴河", "青岛崂山", "泰山", "武夷山", "庐山", "峨眉山",
        "黄龙", "西柏坡", "婺源", "宏村", "西递",
        # 历史文化名城
        "绍兴", "扬州", "平遥", "大同", "徽州", "歙县",
        "赣州", "景德镇", "潮州", "泉州",
        # 沿海 / 海岛
        "舟山", "象山", "嵊泗", "普陀山", "厦门", "平潭", "东山",
        "阳江", "汕尾", "北海", "涠洲岛", "三亚", "万宁", "琼海", "文昌",
    }

    def __init__(self):
        """初始化 LLM 意图识别服务"""
        file_path = os.path.abspath(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
        prompt_dir = os.path.join(app_dir, "prompt")
        # 意图识别服务，用于识别用户意图并提取信息
        self.system_prompt_path = os.path.join(prompt_dir, "intent-recognition-system-prompt.txt")
        self.user_prompt_path = os.path.join(prompt_dir, "intent-recognition-user-prompt.txt")

    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            with open(self.system_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"系统提示词文件不存在: {self.system_prompt_path}")

    def _load_user_prompt_template(self) -> str:
        """加载用户提示词模板"""
        try:
            with open(self.user_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"用户提示词文件不存在: {self.user_prompt_path}")

    def _get_last_user_input(self, state: "AgentState") -> str:
        """从 state 中提取最后一条用户输入"""
        messages = state.get("messages", [])
        if not messages:
            return ""
        
        # 从后往前找最后一条用户消息
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content if hasattr(msg, 'content') else str(msg)
        return ""

    def _validate_city_name(self, city_name: Optional[str], user_input: str = "") -> Optional[str]:
        """
        校验 city_name 是否为合法的具体城市，非法则返回 None。

        检查顺序：
        1. 优先检查 user_input 中是否出现 >=2 个城市（即使模型只提取了一个）
        2. 检查 city_name 本身是否为非法地理区域词
        3. 检查 city_name 本身是否包含多个城市
        """
        if city_name is None:
            return None
        cleaned = city_name.strip().rstrip("市区县")

        # 优先检查原始 user_input 中的城市数量
        if user_input:
            matched_in_input = [city for city in self._KNOWN_CITIES if city in user_input]
            if len(matched_in_input) >= 2:
                logger.warning(
                    f"user_input 中包含多个城市 {matched_in_input}，city_name '{city_name}' 置为 null"
                )
                return None

        # 检查 city_name 本身是否为非法地理区域词
        if cleaned in self._INVALID_CITY_KEYWORDS:
            logger.warning(f"city_name '{city_name}' 为非法地理区域词，已置为 null")
            return None

        # 检查 city_name 本身是否拼合了多个城市（如 LLM 返回"成都重庆"）
        matched_in_name = [city for city in self._KNOWN_CITIES if city in cleaned]
        if len(matched_in_name) >= 2:
            logger.warning(f"city_name '{city_name}' 包含多个城市 {matched_in_name}，已置为 null")
            return None

        return cleaned if cleaned else None


    def _validate_day_count(self, day_count) -> "Optional[int]":
        """
        校验并归一化 day_count。
        - 转换为整数
        - 值域必须在 [1, 30] 以内，否则返回 None
        """
        if day_count is None or day_count == "null":
            return None
        try:
            value = int(day_count)
        except (ValueError, TypeError):
            logger.warning(f"day_count '{day_count}' 无法转换为整数，已置为 null")
            return None
        if value < 1 or value > 30:
            logger.warning(f"day_count '{day_count}' 超出合法范围 [1, 30]，已置为 null")
            return None
        return value

    def recognize_intent(self, state: "AgentState") -> Dict[str, Any]:
        """
        使用 LLM 识别用户意图并提取信息

        Args:
            state: Agent 状态对象

        Returns:
            包含意图识别结果的字典：
            - intent_type: "tourism" | "non_tourism" | "tourism_need_guidance"
            - city_name: 城市名称（如果提取到）
            - day_count: 天数（如果提取到）
            - confidence: 置信度
        """
        try:
            # 从 state 中提取信息
            user_input = self._get_last_user_input(state)
            conversation_history = state.get("messages", [])
            current_city = state.get("city_name")
            current_day_count = state.get("day_count")
            in_guidance_mode = state.get("in_guidance_mode", False)
            
            # 加载系统提示词
            system_prompt = self._load_system_prompt()
            user_prompt_template = self._load_user_prompt_template()

            # 构建上下文信息
            context_parts = []
            if in_guidance_mode:
                context_parts.append("注意：当前处于旅游规划引导模式，用户可能在回答引导问题。")
            if current_city:
                context_parts.append(f"已知城市：{current_city}")
            if current_day_count:
                context_parts.append(f"已知天数：{current_day_count}")
            
            # 构建对话信息上下文
            context_str = "\n".join(context_parts) if context_parts else ""
            context_block = f"{context_str}\n" if context_str else "\n"

            # 构建用户提示（从 prompt 文件读取）
            user_prompt = user_prompt_template.format(
                context_block=context_block,
            )
            
            # 创建 LLM 实例（使用 JSON 格式）
            llm = LLMFactory.create_llm(
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            # 构建消息列表
            messages = [SystemMessage(content=system_prompt)]

            # 添加对话历史（如果有）
            if conversation_history:
                # 只取最近几条消息作为上下文
                for msg in conversation_history[-20:]:
                    messages.append(msg)
            
            # 添加用户提示词
            messages.append(HumanMessage(content=user_prompt))

            # 调用 LLM
            response = llm.invoke(messages)
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # 尝试解析 JSON 响应
            try:
                result = json.loads(response_content)
                
                # 验证和标准化结果
                intent_type = result.get("intent_type", "tourism_need_guidance")
                city_name = result.get("city_name")
                day_count = result.get("day_count")
                confidence = result.get("confidence", 0.5)

                # 处理 null 值，并进行后置合法性校验（传入 user_input 做多城市检测）
                if city_name == "null" or city_name is None:
                    city_name = None
                else:
                    city_name = self._validate_city_name(city_name, user_input)

                # city_name 被校验为非法时，若当前是 tourism 则降级为 tourism_need_guidance
                if city_name is None and intent_type == "tourism":
                    intent_type = "tourism_need_guidance"

                # 校验 day_count 合法性（值域 [1, 30]）
                day_count = self._validate_day_count(day_count)

                logger.info(
                    f"意图识别结果: intent_type={intent_type}, city_name={city_name}, "
                    f"day_count={day_count}, confidence={confidence}"
                )

                return {
                    "intent_type": intent_type,
                    "city_name": city_name,
                    "day_count": day_count,
                    "confidence": confidence
                }
            except json.JSONDecodeError as e:
                # 意图识别的 JSON 解析失败
                logger.error(f"解析 JSON 响应失败: {e}, 响应内容: {response_content}")
                # 尝试从文本中提取信息
                return self._fallback_extraction(user_input)

        except Exception as e:
            logger.error(f"意图识别异常: {e}", exc_info=True)
            # 降级到简单提取
            user_input = self._get_last_user_input(state)
            return self._fallback_extraction(user_input)

    def _fallback_extraction(self, user_input: str) -> Dict[str, Any]:
        """降级提取方法（当 LLM 调用失败时使用规则匹配）"""
        # 使用统一的简单意图提取器
        city, day_count = SimpleIntentExtractor.extract_from_input(user_input)

        # 对降级提取的城市也做合法性校验，同样传入 user_input
        city = self._validate_city_name(city, user_input)

        # 校验 day_count 合法性（值域 [1, 30]）
        day_count = self._validate_day_count(day_count)

        tourism_keywords = ["旅游", "旅行", "游玩", "景点", "攻略", "行程", "路线"]
        is_tourism = any(keyword in user_input for keyword in tourism_keywords)

        if city or day_count:
            is_tourism = True

        if is_tourism:
            return {
                "intent_type": "tourism_need_guidance",
                "city_name": city,
                "day_count": day_count,
                "confidence": 0.5
            }
        else:
            return {
                "intent_type": "non_tourism",
                "city_name": None,
                "day_count": None,
                "confidence": 0.5
            }
