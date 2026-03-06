"""输入验证服务"""
import re
from typing import Dict, Any
from loguru import logger


class ValidationService:
    """输入验证服务类"""
    
    def validate_input(self, user_input: str) -> Dict[str, Any]:
        """
        验证用户输入
        
        Args:
            user_input: 用户输入内容
            
        Returns:
            包含验证结果的字典，如果有错误则包含 error 字段
        """
        result = {}
        
        # 空内容检查
        if not user_input or not user_input.strip():
            result["error"] = "输入内容不能为空"
            logger.warning("输入内容为空")
            return result
        
        # 长度检查
        if len(user_input) > 1000:
            result["error"] = "输入内容过长，不要超过 1000 字"
            logger.warning("输入内容过长")
            return result
        
        # 敏感词检测
        sensitive_words = [
            "忽略之前的指令", "ignore previous instructions", "ignore above",
            "破解", "hack", "绕过", "bypass", "越狱", "jailbreak"
        ]
        
        user_input_lower = user_input.lower()
        for word in sensitive_words:
            if word.lower() in user_input_lower:
                result["error"] = "输入包含不当内容，请修改后重试"
                logger.warning(f"检测到敏感词: {word}")
                return result
        
        # Prompt 注入检测
        injection_patterns = [
            r"(?i)ignore\s+(?:previous|above|all)\s+(?:instructions?|commands?|prompts?)",
            r"(?i)(?:forget|disregard)\s+(?:everything|all)\s+(?:above|before)",
            r"(?i)(?:pretend|act|behave)\s+(?:as|like)\s+(?:if|you\s+are)",
            r"(?i)system\s*:\s*you\s+are",
            r"(?i)new\s+(?:instructions?|commands?|prompts?)\s*:"
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, user_input):
                result["error"] = "检测到恶意输入，请求被拒绝"
                logger.warning(f"检测到 Prompt 注入: {pattern}")
                return result
        
        logger.info("输入验证通过")
        return result  # 返回空字典表示验证通过

