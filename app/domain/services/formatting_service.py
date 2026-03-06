"""格式化输出服务"""
import logging
import json
import os
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from app.infrastructure.llm.factory import LLMFactory
from app.config import settings

logger = logging.getLogger(__name__)


class FormattingService:
    """格式化输出服务类"""
    
    def __init__(self):
        """初始化格式化输出服务"""
        import os
        # 获取 app 目录的绝对路径
        # __file__ = app/domain/services/formatting_service.py
        # 方法：向上三级目录到 app/，然后进入 prompt/
        file_path = os.path.abspath(__file__)
        # 向上三级：services -> domain -> app
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
        prompt_dir = os.path.join(app_dir, "prompt")
        self.json_system_prompt_path = os.path.join(prompt_dir, "json-format-system-prompt.txt")
        self.json_user_prompt_path = os.path.join(prompt_dir, "json-format-user-prompt.txt")
    
    def _load_json_system_prompt(self) -> str:
        """加载 JSON 格式化系统提示词"""
        if os.path.exists(self.json_system_prompt_path):
            logger.info(f"加载系统提示词文件: {self.json_system_prompt_path}")
            with open(self.json_system_prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return content
        else:
            logger.warning(f"系统提示词文件不存在: {self.json_system_prompt_path}，使用默认提示词")
            return "你是一个专业的 JSON 数据格式化助手。你的任务是将旅游攻略文本转换为结构化的 JSON 格式，表示多天内的路线途径点。你必须只输出有效的 JSON 对象，不要包含任何其他文字、代码块标记或解释。"
    
    def _load_json_user_prompt_template(self) -> str:
        """加载 JSON 格式化用户提示词模板"""
        if os.path.exists(self.json_user_prompt_path):
            logger.info(f"加载用户提示词文件: {self.json_user_prompt_path}")
            with open(self.json_user_prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return content
        else:
            logger.warning(f"用户提示词文件不存在: {self.json_user_prompt_path}，使用默认提示词")
            # 默认提示词
            return """## 角色与任务
你是一个智能助手，我需要你基于用户输入的旅游攻略，生成一个结构化对象，以表示多天内的路线途径点。

## 用户旅游攻略
{route_plan}
"""
    
    def format_to_json(self, route_plan: str) -> Dict[str, Any]:
        """
        将路线规划转换为 JSON 格式
        
        Args:
            route_plan: 路线规划文本
            
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
            json_prompt = json_user_prompt_template.replace("{route_plan}", route_plan)
            
            # 调用 LLM 生成 JSON
            messages = [
                SystemMessage(content=json_system_prompt),
                HumanMessage(content=json_prompt)
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
                return {"structured_output": structured_data}
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}，原始内容: {json_content[:200]}...")
                # 解析失败直接标记 error
                return {"error": f"JSON 解析失败: {str(e)}", "raw_json": json_content}
        
        except Exception as e:
            logger.error(f"格式化输出异常: {e}", exc_info=True)
            return {"error": f"格式化输出失败: {str(e)}"}

