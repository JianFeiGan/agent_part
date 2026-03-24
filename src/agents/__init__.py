"""
Agent模块。

包含所有协作Agent的实现：
- OrchestratorAgent: 编排调度中心
- RequirementAnalyzerAgent: 需求分析
- CreativePlannerAgent: 创意策划
- VisualDesignerAgent: 视觉设计
- ImageGeneratorAgent: 图片生成
- VideoGeneratorAgent: 视频生成
- QualityReviewerAgent: 质量审核
"""

from src.agents.base import AgentResult, AgentRole, AgentStatus, BaseAgent
from src.agents.base import AgentState as BaseAgentState
from src.agents.creative_planner import CreativePlannerAgent
from src.agents.image_generator import ImageGeneratorAgent, generate_product_image
from src.agents.orchestrator import OrchestratorAgent
from src.agents.quality_reviewer import QualityReviewerAgent
from src.agents.requirement_analyzer import RequirementAnalyzerAgent
from src.agents.video_generator import (
    VideoGeneratorAgent,
    generate_product_video,
    generate_storyboard,
)
from src.agents.visual_designer import VisualDesignerAgent

__all__ = [
    # 基类
    "BaseAgent",
    "AgentRole",
    "AgentStatus",
    "BaseAgentState",
    "AgentResult",
    # 具体Agent
    "OrchestratorAgent",
    "RequirementAnalyzerAgent",
    "CreativePlannerAgent",
    "VisualDesignerAgent",
    "ImageGeneratorAgent",
    "VideoGeneratorAgent",
    "QualityReviewerAgent",
    # 工具函数
    "generate_product_image",
    "generate_product_video",
    "generate_storyboard",
]
