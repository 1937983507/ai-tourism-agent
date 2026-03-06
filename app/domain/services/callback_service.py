"""回调服务：将结构化输出发送到Java后端"""
import json
import httpx
from typing import Dict, Any, Optional
from loguru import logger
from app.config import settings


class CallbackService:
    """回调服务类"""
    
    def __init__(self):
        """初始化回调服务"""
        self.java_service_url = settings.java_service_url
        self.internal_token = settings.java_service_internal_token
    
    def send_structured_output(
        self,
        session_id: str,
        user_id: str,
        structured_output: Dict[str, Any]
    ) -> bool:
        """
        将结构化输出发送到Java后端的callback接口
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
            structured_output: 结构化输出字典
            
        Returns:
            是否发送成功
        """
        if not session_id or not user_id:
            logger.warning("session_id或user_id为空，跳过回调")
            return False
        
        try:
            # 将结构化输出转换为JSON字符串
            json_str = json.dumps(structured_output, ensure_ascii=False, indent=2)
            
            # 构建请求体
            callback_url = f"{self.java_service_url}/ai_assistant/callback"
            payload = {
                "session_id": session_id,
                "user_id": user_id,
                "structured_output": json_str
            }
            
            # 构建请求头
            headers = {
                "Content-Type": "application/json"
            }
            if self.internal_token:
                headers["Authorization"] = f"Bearer {self.internal_token}"
            
            # 发送POST请求
            # trust_env=False: 避免使用系统代理，防止对 localhost 的请求被代理拦截导致 502
            logger.info(f"发送结构化输出到Java后端，session_id: {session_id}")
            with httpx.Client(timeout=10.0, trust_env=False) as client:
                response = client.post(
                    callback_url,
                    json=payload,
                    headers=headers
                )
                
                if response.is_success:
                    logger.info(f"结构化输出回调成功，session_id: {session_id}")
                    return True
                else:
                    logger.error(
                        f"结构化输出回调失败，session_id: {session_id}, "
                        f"status_code: {response.status_code}, "
                        f"response: {response.text}"
                    )
                    return False
        
        except httpx.TimeoutException:
            logger.error(f"结构化输出回调超时，session_id: {session_id}")
            return False
        except Exception as e:
            logger.error(f"结构化输出回调异常，session_id: {session_id}, error: {e}", exc_info=True)
            return False

