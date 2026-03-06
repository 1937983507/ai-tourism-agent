"""Checkpoint Saver 初始化"""
import atexit
import asyncio
from contextlib import AbstractContextManager
from loguru import logger
from langgraph.checkpoint.memory import MemorySaver
from app.config import settings
import os

_checkpointer = None
_checkpointer_cm: AbstractContextManager | None = None
_checkpointer_async_cm = None
_sqlite_async_conn = None


def _enter_cm(cm: AbstractContextManager):
    """
    LangGraph 新版本里部分 Saver 的 from_conn_string 返回的是 context manager；
    这里统一做一次 __enter__，并在进程退出时 __exit__ 释放资源。
    """
    global _checkpointer_cm
    _checkpointer_cm = cm
    saver = cm.__enter__()
    atexit.register(lambda: cm.__exit__(None, None, None))
    return saver


async def _aenter_async_cm(cm):
    """进入 async context manager 并缓存，供 shutdown 时关闭。"""
    global _checkpointer_async_cm
    _checkpointer_async_cm = cm
    return await cm.__aenter__()


async def aclose_checkpointer():
    """应用关闭时释放 async checkpointer 资源（如 sqlite 连接）。"""
    global _checkpointer_async_cm, _sqlite_async_conn
    if _checkpointer_async_cm is not None:
        try:
            await _checkpointer_async_cm.__aexit__(None, None, None)
        finally:
            _checkpointer_async_cm = None
    if _sqlite_async_conn is not None:
        try:
            await _sqlite_async_conn.close()
        finally:
            _sqlite_async_conn = None


async def ainit_checkpointer():
    """在异步上下文中初始化 checkpointer。"""
    global _checkpointer, _sqlite_async_conn
    if _checkpointer is not None:
        logger.debug(f"Checkpointer 已初始化，类型: {type(_checkpointer).__name__}")
        return _checkpointer

    checkpoint_type = settings.checkpoint_type.lower()
    logger.info(f"初始化 Checkpointer，类型: {checkpoint_type}")
    
    if checkpoint_type == "sqlite":
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        db_path = settings.sqlite_db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        logger.info(f"使用 SQLite Checkpoint，路径: {db_path}")
        # 避免使用 from_conn_string（其内部会创建 aiosqlite conn，但当前 aiosqlite 版本没有 is_alive，
        # 而 langgraph 会调用 conn.is_alive() 导致 500）。
        conn = await aiosqlite.connect(db_path)
        if not hasattr(conn, "is_alive"):
            # 兼容 langgraph：补一个 is_alive；连接未 close 时认为存活
            conn.is_alive = lambda: True  # type: ignore[attr-defined]
        _sqlite_async_conn = conn
        _checkpointer = AsyncSqliteSaver(conn)
        logger.info(f"SQLite Checkpointer 初始化完成")
        return _checkpointer
    elif checkpoint_type == "memory":
        logger.info("使用内存 Checkpoint（默认）")
        _checkpointer = MemorySaver()
        return _checkpointer

    # 其他类型保持原逻辑（当前环境可能未安装）
    return create_checkpointer()


def create_checkpointer():
    """创建 Checkpoint Saver"""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    checkpoint_type = settings.checkpoint_type.lower()
    
    if checkpoint_type == "memory":
        # 默认使用内存 Checkpoint
        logger.info("使用内存 Checkpoint（默认）")
        _checkpointer = MemorySaver()
        return _checkpointer
    
    elif checkpoint_type == "sqlite":
        try:
            # 你们的 Agent 调用的是 graph.astream / graph.ainvoke（async），必须使用异步 Checkpointer
            # 否则会在 aget_tuple 等方法上抛 NotImplementedError
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            db_path = settings.sqlite_db_path
            # 确保目录存在
            os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
            
            logger.info(f"使用 SQLite Checkpoint，路径: {db_path}")
            # 不能在运行中的 event loop 里调用 asyncio.run；因此 sqlite 建议在 FastAPI startup 阶段调用 ainit_checkpointer()。
            try:
                asyncio.get_running_loop()
                raise RuntimeError(
                    "AsyncSqliteSaver must be initialized in an async context. "
                    "Call ainit_checkpointer() during FastAPI startup."
                )
            except RuntimeError as e:
                # 若错误原因是“没有运行中的 event loop”，可用 asyncio.run 同步初始化（脚本/本地测试场景）
                if "no running event loop" in str(e).lower():
                    _checkpointer = asyncio.run(ainit_checkpointer())
                    atexit.register(lambda: asyncio.run(aclose_checkpointer()))
                    return _checkpointer
                raise
        except ImportError:
            logger.warning("SQLite Checkpoint 未安装，使用内存 Checkpoint")
            _checkpointer = MemorySaver()
            return _checkpointer
    
    elif checkpoint_type == "postgres":
        conn_string = settings.postgres_conn_string
        if not conn_string:
            logger.warning("PostgreSQL 连接字符串未配置，使用内存 Checkpoint")
            _checkpointer = MemorySaver()
            return _checkpointer
        
        try:
            from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import-not-found]
            logger.info("使用 PostgreSQL Checkpoint")
            cm_or_saver = PostgresSaver.from_conn_string(conn_string)
            if hasattr(cm_or_saver, "__enter__") and not hasattr(cm_or_saver, "get_next_version"):
                _checkpointer = _enter_cm(cm_or_saver)  # type: ignore[arg-type]
            else:
                _checkpointer = cm_or_saver
            return _checkpointer
        except ImportError:
            logger.warning("PostgreSQL Checkpoint 未安装，使用内存 Checkpoint")
            _checkpointer = MemorySaver()
            return _checkpointer
    
    else:
        # 默认使用内存 Checkpoint
        logger.info("使用内存 Checkpoint")
        _checkpointer = MemorySaver()
        return _checkpointer

