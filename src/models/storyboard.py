"""
分镜脚本模型。

Description:
    定义视频分镜相关的数据结构，包括分镜脚本、场景、镜头等。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from enum import Enum

from pydantic import BaseModel, Field


class ShotType(str, Enum):
    """镜头类型枚举。"""

    WIDE = "wide"  # 远景
    MEDIUM = "medium"  # 中景
    CLOSE_UP = "close_up"  # 特写
    EXTREME_CLOSE_UP = "extreme_close_up"  # 大特写
    PAN = "pan"  # 摇镜头
    TILT = "tilt"  # 俯仰镜头
    ZOOM = "zoom"  # 推拉镜头
    DOLLY = "dolly"  # 移动镜头


class TransitionType(str, Enum):
    """转场类型枚举。"""

    CUT = "cut"  # 直接切换
    FADE = "fade"  # 淡入淡出
    DISSOLVE = "dissolve"  # 溶解
    WIPE = "wipe"  # 擦除
    ZOOM = "zoom"  # 缩放转场
    SLIDE = "slide"  # 滑动


class SceneType(str, Enum):
    """场景类型枚举。"""

    PRODUCT_INTRO = "product_intro"  # 产品介绍
    FEATURE_HIGHLIGHT = "feature_highlight"  # 功能展示
    USAGE_SCENARIO = "usage_scenario"  # 使用场景
    COMPARISON = "comparison"  # 对比展示
    TESTIMONIAL = "testimonial"  # 用户证言
    CALL_TO_ACTION = "call_to_action"  # 行动号召
    BRAND_MOMENT = "brand_moment"  # 品牌时刻


class TextOverlay(BaseModel):
    """文字叠加层。"""

    content: str = Field(..., description="文字内容")
    position: str = Field(default="center", description="位置: top/center/bottom")
    font_size: int = Field(default=24, description="字体大小")
    color: str = Field(default="#FFFFFF", description="字体颜色")
    background: str | None = Field(default=None, description="背景色")
    animation: str | None = Field(default=None, description="动画效果")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "超长续航7天",
                    "position": "center",
                    "font_size": 32,
                    "color": "#FFFFFF",
                    "background": "#00000080",
                }
            ]
        }
    }


class Scene(BaseModel):
    """分镜场景。"""

    scene_id: int = Field(..., description="场景序号")
    scene_type: SceneType = Field(..., description="场景类型")
    duration: float = Field(..., description="时长(秒)", ge=0.5, le=60)

    # 镜头信息
    shot_type: ShotType = Field(..., description="镜头类型")
    camera_movement: str | None = Field(default=None, description="镜头运动描述")

    # 场景描述
    description: str = Field(..., description="场景详细描述")
    visual_prompt: str = Field(..., description="视觉生成提示词")

    # 叠加元素
    text_overlays: list[TextOverlay] = Field(default_factory=list, description="文字叠加层")
    audio_description: str | None = Field(default=None, description="音频描述")

    # 转场
    transition_in: TransitionType = Field(default=TransitionType.CUT, description="入场转场")
    transition_out: TransitionType = Field(default=TransitionType.CUT, description="出场转场")

    # 素材引用
    product_focus: str | None = Field(default=None, description="聚焦的产品卖点")
    asset_references: list[str] = Field(default_factory=list, description="引用的素材ID")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "scene_id": 1,
                    "scene_type": "product_intro",
                    "duration": 3.0,
                    "shot_type": "medium",
                    "description": "产品正面展示，品牌Logo淡入",
                    "visual_prompt": "Smart watch product shot, "
                    "front view, clean background, "
                    "brand logo fade in",
                    "text_overlays": [{"content": "TechFit 智能手表", "position": "bottom"}],
                    "transition_in": "fade",
                    "transition_out": "dissolve",
                }
            ]
        }
    }


class Storyboard(BaseModel):
    """分镜脚本模型。"""

    # 基本信息
    storyboard_id: str | None = Field(default=None, description="分镜ID")
    title: str = Field(..., description="分镜标题")
    description: str = Field(..., description="分镜描述")

    # 视频参数
    total_duration: float = Field(..., description="总时长(秒)", ge=5, le=180)
    aspect_ratio: str = Field(default="16:9", description="宽高比")
    resolution: str = Field(default="1080p", description="分辨率")

    # 场景列表
    scenes: list[Scene] = Field(default_factory=list, description="场景列表")

    # 风格设定
    visual_style: str = Field(..., description="视觉风格")
    color_grading: str | None = Field(default=None, description="调色风格")

    # 音频设定
    background_music_style: str | None = Field(default=None, description="背景音乐风格")
    voiceover_style: str | None = Field(default=None, description="旁白风格")

    # 元数据
    tags: list[str] = Field(default_factory=list, description="标签")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "智能手表产品介绍",
                    "description": "30秒产品展示视频，突出核心卖点",
                    "total_duration": 30.0,
                    "aspect_ratio": "16:9",
                    "resolution": "1080p",
                    "scenes": [
                        {
                            "scene_id": 1,
                            "scene_type": "product_intro",
                            "duration": 5.0,
                            "shot_type": "medium",
                            "description": "开场产品展示",
                            "visual_prompt": "Product hero shot",
                        }
                    ],
                    "visual_style": "科技感",
                }
            ]
        }
    }

    def add_scene(self, scene: Scene) -> None:
        """添加场景。

        Args:
            scene: 场景对象。
        """
        self.scenes.append(scene)
        self._update_duration()

    def remove_scene(self, scene_id: int) -> bool:
        """移除场景。

        Args:
            scene_id: 场景ID。

        Returns:
            是否成功移除。
        """
        for i, scene in enumerate(self.scenes):
            if scene.scene_id == scene_id:
                self.scenes.pop(i)
                self._update_duration()
                return True
        return False

    def _update_duration(self) -> None:
        """更新总时长。"""
        self.total_duration = sum(scene.duration for scene in self.scenes)

    def get_scene(self, scene_id: int) -> Scene | None:
        """获取指定场景。

        Args:
            scene_id: 场景ID。

        Returns:
            场景对象，不存在则返回 None。
        """
        for scene in self.scenes:
            if scene.scene_id == scene_id:
                return scene
        return None

    def get_scene_count(self) -> int:
        """获取场景数量。

        Returns:
            场景数量。
        """
        return len(self.scenes)

    def validate_duration(self) -> bool:
        """验证场景时长之和是否等于总时长。

        Returns:
            是否验证通过。
        """
        calculated = sum(scene.duration for scene in self.scenes)
        return abs(calculated - self.total_duration) < 0.1
