"""
编排调度Agent模块。

Description:
    作为系统的核心调度中心，负责：
    - 接收和解析用户请求
    - 分解任务为子任务
    - 协调其他Agent的执行顺序
    - 汇总和整合最终结果
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from src.agents.base import AgentResult, AgentRole, AgentRuntimeState, BaseAgent
from src.agents.llm_json import extract_json
from src.graph.state import GenerationRequest


class OrchestratorAgent(BaseAgent[AgentRuntimeState]):
    """编排调度Agent。

    作为系统的"大脑"，负责整体流程的编排和协调。

    Attributes:
        role: 固定为 ORCHESTRATOR。

    Example:
        >>> agent = OrchestratorAgent()
        >>> result = await agent.execute(state)
    """

    def __init__(self, **kwargs: Any) -> None:
        """初始化编排器Agent。"""
        super().__init__(role=AgentRole.ORCHESTRATOR, **kwargs)
        self._setup_prompts()

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # 任务分解提示
        task_decomposition_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个专业的电商营销内容编排专家。"
                    "你的任务是分析用户需求，制定合理的生成计划。\n\n"
                    "请根据商品信息和生成需求，输出以下内容：\n"
                    "1. 任务类型判断（仅图片/仅视频/图片+视频）\n"
                    "2. 推荐的生成顺序\n"
                    "3. 预估的关键节点\n\n"
                    "输出格式为JSON。",
                ),
                (
                    "human",
                    "商品信息：{product_info}\n"
                    "生成需求：{generation_request}\n\n"
                    "请分析并输出任务规划。",
                ),
            ]
        )
        self.register_prompt("task_decomposition", task_decomposition_prompt)

    async def execute(self, state: AgentRuntimeState) -> AgentResult:
        """执行编排任务。

        Args:
            state: 当前状态。

        Returns:
            执行结果，包含任务规划信息。
        """
        try:
            # 验证输入
            if state.product_info is None:
                return AgentResult(
                    success=False,
                    error="缺少商品信息",
                )

            # 分析任务需求
            task_plan = await self._analyze_task(state)

            # 更新状态
            state.mark_step_completed("orchestration")

            return AgentResult(
                success=True,
                data={
                    "task_plan": task_plan,
                    "next_step": "requirement_analysis",
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"编排执行失败: {e}",
            )

    async def _analyze_task(self, state: AgentRuntimeState) -> dict[str, Any]:
        """分析任务需求。

        Args:
            state: 当前状态。

        Returns:
            任务规划字典。
        """
        product = state.product_info
        request = state.generation_request or GenerationRequest()

        # 构建输入
        product_info_str = f"""
        名称: {product.name}
        类目: {product.category}
        描述: {product.description}
        卖点数量: {len(product.selling_points)}
        """

        request_str = f"""
        任务类型: {request.task_type}
        图片类型: {request.image_types}
        视频时长: {request.video_duration}秒
        风格偏好: {request.style_preference or "自动推荐"}
        """

        # 调用LLM分析
        prompt = self.get_prompt("task_decomposition")
        if prompt:
            response = await self.invoke_llm(
                prompt,
                {
                    "product_info": product_info_str,
                    "generation_request": request_str,
                },
            )
            # 解析响应，提取任务规划
            return self._parse_task_plan(response)

        # 默认规划
        return {
            "task_type": request.task_type,
            "execution_order": [
                "requirement_analysis",
                "creative_planning",
                "visual_design",
                "generation",
                "quality_review",
            ],
            "estimated_steps": 5,
        }

    def _parse_task_plan(self, response: str) -> dict[str, Any]:
        """解析任务规划响应。

        Args:
            response: LLM响应文本。

        Returns:
            解析后的任务规划。
        """
        parsed = extract_json(response)
        if parsed is not None:
            return parsed

        # 返回默认规划
        return {
            "task_type": "image_and_video",
            "execution_order": [
                "requirement_analysis",
                "creative_planning",
                "visual_design",
                "generation",
                "quality_review",
            ],
        }
