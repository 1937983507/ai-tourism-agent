"""快速启动脚本"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.agent_host,
        port=settings.agent_port,
        reload=True,
        log_level=settings.log_level.lower()
    )







