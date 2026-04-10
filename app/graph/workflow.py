"""LangGraph 工作流定义"""
from langgraph.graph import StateGraph, END
from loguru import logger
from app.graph.state import AgentState
from app.graph.nodes import (
    validate_input_node,
    llm_intent_recognition_node,  # LLM 意图识别节点
    conversation_guidance_node,   # 对话引导节点
    general_response_node,        # 通用回复节点
    parallel_trigger_node,        # 并行触发节点
    fetch_weather_node,
    fetch_poi_node,
    rag_retrieve_node,
    plan_route_node,
    format_output_node,
    handle_error_node,
    check_validation_result,
    check_intent_result,
    check_guidance_complete
)
from app.infrastructure.checkpoint.saver import create_checkpointer
from app.infrastructure.checkpoint.saver import ainit_checkpointer


def _try_display_graph(compiled_graph):
    """仅在 Jupyter/IPython 环境中可视化工作流图，避免服务启动时输出无意义的对象表示"""
    try:
        from IPython import get_ipython
        if get_ipython() is not None:
            from IPython.display import Image, display
            display(Image(data=compiled_graph.get_graph().draw_mermaid_png()))
    except Exception:
        pass


def create_agent_graph():
    """创建 Agent 工作流图（显式定义节点和边）"""
    logger.info("创建 Agent 工作流图")
    
    # 创建 Checkpoint Saver
    checkpointer = create_checkpointer()
    logger.info(f"Checkpointer 类型: {type(checkpointer).__name__}")
    
    # 创建状态图
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("validate_input", validate_input_node)           # 输入验证
    graph.add_node("llm_intent_recognition", llm_intent_recognition_node)  # LLM 意图识别
    graph.add_node("conversation_guidance", conversation_guidance_node)    # 对话引导
    graph.add_node("general_response", general_response_node)              # 通用回复
    graph.add_node("parallel_trigger", parallel_trigger_node)      # 并行触发节点
    graph.add_node("fetch_weather", fetch_weather_node)             # 获取天气
    graph.add_node("fetch_poi", fetch_poi_node)                     # 获取景点
    graph.add_node("rag_retrieve", rag_retrieve_node)               # RAG 向量检索
    graph.add_node("plan_route", plan_route_node)                   # 路线规划
    graph.add_node("format_output", format_output_node)             # 格式化输出
    graph.add_node("handle_error", handle_error_node)               # 错误处理
    
    # 设置入口
    graph.set_entry_point("validate_input")
    
    # 添加边和条件路由
    # 验证 -> LLM 意图识别（如果通过）或错误处理（如果失败）
    graph.add_conditional_edges(
        "validate_input",
        check_validation_result,
        {
            "continue": "llm_intent_recognition",
            "error": "handle_error"
        }
    )
    
    # LLM 意图识别 -> 根据结果路由
    graph.add_conditional_edges(
        "llm_intent_recognition",
        check_intent_result,
        {
            "tourism": "parallel_trigger",  # 旅游意图且信息完整，触发并行执行
            "tourism_need_guidance": "conversation_guidance",  # 旅游意图但信息不完整，需要引导
            "non_tourism": "general_response"  # 非旅游意图，直接回复
        }
    )
    
    # 对话引导 -> 检查是否完成
    graph.add_conditional_edges(
        "conversation_guidance",
        check_guidance_complete,
        {
            "complete": "parallel_trigger",  # 已获取完整信息，触发并行执行
            "continue_guidance": END  # 仍需继续引导，等待下一轮用户输入
        }
    )
    
    # 通用回复 -> 结束
    graph.add_edge("general_response", END)
    
    # 并行触发节点 -> 同时触发天气、景点、RAG（并行执行）
    graph.add_edge("parallel_trigger", "fetch_weather")
    graph.add_edge("parallel_trigger", "fetch_poi")
    graph.add_edge("parallel_trigger", "rag_retrieve")

    # 天气、景点、RAG 均完成后 -> 路线规划
    # LangGraph 会等待所有入边节点都完成后才执行 plan_route
    graph.add_edge("fetch_weather", "plan_route")
    graph.add_edge("fetch_poi", "plan_route")
    graph.add_edge("rag_retrieve", "plan_route")
    
    # 路线规划 -> 格式化输出
    graph.add_edge("plan_route", "format_output")
    
    # 格式化输出 -> 结束
    graph.add_edge("format_output", END)
    
    # 错误处理 -> 结束
    graph.add_edge("handle_error", END)
    
    # 编译图（传入 checkpointer 以启用状态持久化）
    compiled_graph = graph.compile(checkpointer=checkpointer)
    
    logger.info(f"Agent 工作流图创建完成，checkpointer 已绑定: {checkpointer is not None}")

    _try_display_graph(compiled_graph)

    return compiled_graph


async def init_agent_graph():
    """在应用启动阶段初始化 Agent 图（便于 async checkpointer 正确初始化）。"""
    global _agent_graph
    if _agent_graph is not None:
        return _agent_graph

    # 确保 checkpointer 在 async 上下文中初始化（sqlite async saver 需要）
    await ainit_checkpointer()
    _agent_graph = create_agent_graph()
    return _agent_graph


# 全局图实例（延迟初始化）
_agent_graph = None


def get_agent_graph():
    """获取 Agent 图实例（单例）"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph

