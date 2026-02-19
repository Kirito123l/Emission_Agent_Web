"""启动API服务"""
import uvicorn
import logging
import sys

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    stream=sys.stdout,
    force=True  # 强制重新配置
)

# 配置所有相关的日志记录器
for logger_name in ['uvicorn', 'uvicorn.access', 'uvicorn.error', 'api', 'api.main', 'api.routes', '__main__']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = True

if __name__ == "__main__":
    print("=" * 60)
    print("🌿 Emission Agent API Server")
    print("=" * 60)
    print("服务器启动中...")
    print("访问地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("=" * 60)

    # 配置 uvicorn 日志
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(message)s"

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=True,
        log_config=log_config
    )
