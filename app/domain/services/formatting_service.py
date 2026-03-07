"""格式化输出服务"""
import json
import os
from typing import Dict, Any, Optional
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory
from app.config import settings


class FormattingService:
    """格式化输出服务类"""
    
    def __init__(self):
        """初始化格式化输出服务"""
        import os
        file_path = os.path.abspath(__file__)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
        prompt_dir = os.path.join(app_dir, "prompt")
        # 将旅游攻略文本转化为JSON字符串
        self.json_system_prompt_path = os.path.join(prompt_dir, "json-format-system-prompt.txt")
        self.json_user_prompt_path = os.path.join(prompt_dir, "json-format-user-prompt.txt")
    
    def _load_json_system_prompt(self) -> str:
        """加载 JSON 格式化系统提示词"""
        try:
            with open(self.json_system_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"系统提示词文件不存在: {self.json_system_prompt_path}")
    
    def _load_json_user_prompt_template(self) -> str:
        """加载 JSON 格式化用户提示词模板"""
        try:
            with open(self.json_user_prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"用户提示词文件不存在: {self.json_user_prompt_path}")
    
    def _parse_poi_data(self, poi_data: str) -> Optional[Dict[str, Any]]:
        """
        解析 POI 数据，提取名称和经纬度信息用于匹配
        
        Args:
            poi_data: POI 数据 JSON 字符串
            
        Returns:
            包含 POI 名称到经纬度映射的字典，如果解析失败则返回 None
        """
        if not poi_data:
            return None
        
        try:
            poi_json = json.loads(poi_data)
            
            # 检查数据格式
            if not isinstance(poi_json, dict):
                logger.warning("POI 数据格式不正确，不是 JSON 对象")
                return None
            
            # 提取 data 数组
            data_list = poi_json.get("data", [])
            if not isinstance(data_list, list):
                logger.warning("POI 数据中缺少 data 数组")
                return None
            
            # 构建 POI 名称到经纬度的映射字典
            # 使用列表存储，因为可能有同名 POI
            poi_map = {}
            for poi in data_list:
                if not isinstance(poi, dict):
                    continue
                
                # 提取需要的字段（支持多种命名格式）
                poi_name = (
                    poi.get("poi_name") or 
                    poi.get("poiName") or 
                    poi.get("name")
                )
                poi_longitude = (
                    poi.get("poi_longitude") or 
                    poi.get("poiLongitude") or 
                    poi.get("longitude")
                )
                poi_latitude = (
                    poi.get("poi_latitude") or 
                    poi.get("poiLatitude") or 
                    poi.get("latitude")
                )
                
                # 只保留有名称和经纬度的 POI
                if poi_name and poi_longitude is not None and poi_latitude is not None:
                    # 标准化名称（去除空格，转为小写用于匹配）
                    normalized_name = poi_name.strip().lower()
                    if normalized_name not in poi_map:
                        poi_map[normalized_name] = []
                    poi_map[normalized_name].append({
                        "name": poi_name,  # 保留原始名称
                        "longitude": float(poi_longitude),
                        "latitude": float(poi_latitude)
                    })
            
            # logger.info(f"POI 数据解析完成，共 {len(poi_map)} 个唯一 POI 名称")
            return poi_map
            
        except json.JSONDecodeError as e:
            logger.warning(f"POI 数据 JSON 解析失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"POI 数据解析异常: {e}")
            return None
    
    def _match_poi_name(self, keyword: str, poi_map: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        匹配地点名称到 POI 数据
        
        Args:
            keyword: 地点名称（来自路线数据）
            poi_map: POI 名称到经纬度的映射字典
            
        Returns:
            包含 longitude 和 latitude 的字典，如果无法匹配则返回 None
        """
        if not keyword or not poi_map:
            return None
        
        # 标准化关键词（去除空格，转为小写）
        normalized_keyword = keyword.strip().lower()
        
        # 精确匹配
        if normalized_keyword in poi_map:
            # 如果有多个匹配，取第一个
            matched_poi = poi_map[normalized_keyword][0]
            return {
                "longitude": matched_poi["longitude"],
                "latitude": matched_poi["latitude"]
            }
        
        # 模糊匹配：检查关键词是否包含 POI 名称，或 POI 名称是否包含关键词
        for poi_name, poi_list in poi_map.items():
            if normalized_keyword in poi_name or poi_name in normalized_keyword:
                matched_poi = poi_list[0]
                return {
                    "longitude": matched_poi["longitude"],
                    "latitude": matched_poi["latitude"]
                }
        
        return None
    
    def _enrich_with_poi_data(self, structured_data: Dict[str, Any], poi_data: Optional[str]) -> Dict[str, Any]:
        """
        使用 POI 数据丰富结构化路线数据，填充经纬度信息
        
        Args:
            structured_data: LLM 生成的结构化路线数据
            poi_data: POI 数据 JSON 字符串
            
        Returns:
            填充了经纬度信息的结构化数据
        """
        if not poi_data:
            logger.info("POI 数据为空，跳过经纬度填充")
            return structured_data
        
        # 解析 POI 数据
        poi_map = self._parse_poi_data(poi_data)
        if not poi_map:
            logger.warning("POI 数据解析失败，跳过经纬度填充")
            return structured_data
        
        # 遍历 dailyRoutes，为每个地点匹配经纬度
        daily_routes = structured_data.get("dailyRoutes", [])
        matched_count = 0
        total_count = 0
        
        for day_route in daily_routes:
            if not isinstance(day_route, dict):
                continue
            
            points = day_route.get("points", [])
            if not isinstance(points, list):
                continue
            
            for point in points:
                if not isinstance(point, dict):
                    continue
                
                total_count += 1
                keyword = point.get("keyword")
                if not keyword:
                    continue
                
                # 匹配 POI 数据
                coordinates = self._match_poi_name(keyword, poi_map)
                if coordinates:
                    point["longitude"] = coordinates["longitude"]
                    point["latitude"] = coordinates["latitude"]
                    matched_count += 1
                else:
                    # 无法匹配时设为 null
                    logger.warning(f"无法匹配 POI 数据: {keyword}")
                    point["longitude"] = None
                    point["latitude"] = None
        
        logger.info(f"POI 数据匹配完成：总计 {total_count} 个地点，成功匹配 {matched_count} 个")
        return structured_data
    
    def format_to_json(self, route_plan: str, poi_data: Optional[str] = None) -> Dict[str, Any]:
        """
        将路线规划转换为 JSON 格式
        
        Args:
            route_plan: 路线规划文本
            poi_data: 可选的 POI 数据 JSON 字符串，用于后处理阶段填充经纬度信息
            
        Returns:
            包含结构化输出的字典，如果失败则包含 error 字段
        """
        if not route_plan:
            logger.warning("路线规划内容为空，跳过结构化输出")
            return {}
        
        try:
            # 使用 LLM 工厂创建 LLM 实例（强制 JSON 格式输出）
            # 注意：某些 API 可能不支持 response_format，但提示词会强制格式
            llm = LLMFactory.create_llm(
                temperature=0.1,  # 降低温度以获得更稳定的格式输出
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            # 加载提示词
            json_system_prompt = self._load_json_system_prompt()
            json_user_prompt_template = self._load_json_user_prompt_template()
            
            # 构建用户提示词
            json_user_prompt = json_user_prompt_template.format(
                route_plan=route_plan
            )
            
            # 调用 LLM 生成 JSON
            messages = [
                SystemMessage(content=json_system_prompt),
                HumanMessage(content=json_user_prompt)
            ]
            
            json_response = llm.invoke(messages)
            json_content = json_response.content if hasattr(json_response, 'content') else str(json_response)
            
            # 清理可能的代码块标记
            json_content = json_content.strip()
            # 移除可能的 ```json 和 ``` 标记
            if json_content.startswith("```json"):
                json_content = json_content[7:]  # 移除 ```json
            elif json_content.startswith("```"):
                json_content = json_content[3:]  # 移除 ```
            if json_content.endswith("```"):
                json_content = json_content[:-3]  # 移除结尾的 ```
            json_content = json_content.strip()
            
            # 记录 JSON 输出到日志
            logger.info(f"结构化输出 (JSON): {json_content}")
            
            # 尝试解析 JSON 以确保格式正确
            try:
                structured_data = json.loads(json_content)
                logger.info("JSON 解析成功，开始校验结构化输出")

                # 校验结构：必须包含非空 dailyRoutes
                validation_error: Optional[str] = None
                if not isinstance(structured_data, dict):
                    validation_error = "结构化输出不是 JSON 对象"
                else:
                    daily_routes = structured_data.get("dailyRoutes")
                    if not isinstance(daily_routes, list):
                        validation_error = "结构化输出缺少 dailyRoutes 或类型不正确"
                    elif len(daily_routes) == 0:
                        validation_error = "结构化输出 dailyRoutes 为空"

                if validation_error:
                    logger.warning(f"结构化输出校验失败: {validation_error}")
                    # 保留 structured_output 方便排查，但通过 error 标记为无效（下游不应触发回调）
                    return {"error": validation_error, "structured_output": structured_data}

                logger.info("结构化输出校验通过")
                
                # 后处理：使用 POI 数据填充经纬度信息
                enriched_data = self._enrich_with_poi_data(structured_data, poi_data)
                logger.info(f"经纬度填充后数据: {enriched_data}")
                
                return {"structured_output": enriched_data}
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}，原始内容: {json_content[:200]}...")
                # 解析失败直接标记 error
                return {"error": f"JSON 解析失败: {str(e)}", "raw_json": json_content}
        
        except Exception as e:
            logger.error(f"格式化输出异常: {e}", exc_info=True)
            return {"error": f"格式化输出失败: {str(e)}"}

