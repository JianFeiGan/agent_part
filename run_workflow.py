#!/usr/bin/env python
"""
商品视觉生成工作流示例脚本。

Description:
    演示如何使用多Agent协作系统生成商品图片和视频。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.graph import GenerationRequest, ProductVisualWorkflow
from src.models.product import Product, ProductCategory, SellingPoint

console = Console()


async def run_demo() -> None:
    """运行演示工作流。"""
    console.print(Panel.fit(
        "[bold blue]商品视觉生成系统[/bold blue]\n"
        "多Agent协作的图片/视频自动生成",
        title="🚀 Welcome",
    ))

    # ========== 步骤 1: 创建商品信息 ==========
    console.print("\n[bold green]步骤 1:[/bold green] 创建商品信息")

    product = Product(
        product_id="demo_001",
        name="智能运动手表 Pro Max",
        brand="TechWatch",
        category=ProductCategory.DIGITAL,
        description="""
        全新一代智能运动手表，配备 1.4 英寸 AMOLED 高清屏幕。
        支持 24 小时心率监测、睡眠追踪、运动数据分析。
        IP68 级防水设计，游泳洗澡无需摘下。
        典型使用场景续航长达 14 天，支持磁吸快充。
        """,
        selling_points=[
            SellingPoint(
                title="心率实时监测",
                description="24小时不间断心率监测，异常情况及时提醒",
                priority=5,
            ),
            SellingPoint(
                title="14天超长续航",
                description="典型使用场景下续航 14 天，告别电量焦虑",
                priority=4,
            ),
            SellingPoint(
                title="IP68级防水",
                description="游泳、洗澡无需摘下，全天候佩戴",
                priority=3,
            ),
            SellingPoint(
                title="AMOLED高清屏",
                description="1.4英寸高清屏幕，色彩鲜艳，阳光下清晰可见",
                priority=3,
            ),
        ],
    )

    # 显示商品信息
    table = Table(title="商品信息")
    table.add_column("属性", style="cyan")
    table.add_column("值", style="green")
    table.add_row("商品ID", product.product_id or "N/A")
    table.add_row("商品名称", product.name)
    table.add_row("品牌", product.brand or "N/A")
    table.add_row("类目", product.category.value)
    table.add_row("卖点数量", str(len(product.selling_points)))
    console.print(table)

    # ========== 步骤 2: 创建生成请求 ==========
    console.print("\n[bold green]步骤 2:[/bold green] 配置生成请求")

    request = GenerationRequest(
        task_id="task_demo_001",
        task_type="image_and_video",  # 生成图片和视频
        image_types=["main", "scene", "selling_point"],
        image_count_per_type=1,
        video_duration=30.0,
        video_style="professional",
        style_preference="科技感、现代简约、高端大气",
        quality_level="standard",
    )

    # 显示请求配置
    req_table = Table(title="生成配置")
    req_table.add_column("配置项", style="cyan")
    req_table.add_column("值", style="yellow")
    req_table.add_row("任务类型", request.task_type)
    req_table.add_row("图片类型", str(request.image_types))
    req_table.add_row("视频时长", f"{request.video_duration}秒")
    req_table.add_row("风格偏好", request.style_preference or "自动推荐")
    console.print(req_table)

    # ========== 步骤 3: 运行工作流 ==========
    console.print("\n[bold green]步骤 3:[/bold green] 执行工作流...")
    console.print("[dim]正在初始化 Agent 系统...[/dim]")

    try:
        workflow = ProductVisualWorkflow()

        console.print("[dim]开始处理，请稍候...[/dim]")
        console.print()

        # 运行工作流
        result = await workflow.run(product, request)

        # ========== 步骤 4: 显示结果 ==========
        console.print("\n" + "═" * 60)
        console.print("[bold blue]✅ 工作流执行完成！[/bold blue]")
        console.print("═" * 60)

        # 结果摘要
        summary_table = Table(title="执行结果摘要")
        summary_table.add_column("指标", style="cyan")
        summary_table.add_column("值", style="green")
        summary_table.add_row("当前步骤", result.current_step)
        summary_table.add_row("已完成步骤", str(result.completed_steps))
        summary_table.add_row("生成图片数", str(len(result.generated_images)))
        summary_table.add_row("生成视频", "是" if result.generated_video else "否")
        summary_table.add_row("质量评分", f"{result.quality_score:.2f}" if result.quality_score else "N/A")
        summary_table.add_row("发现问题", f"{len(result.issues)} 个")
        console.print(summary_table)

        # 显示生成的图片
        if result.generated_images:
            console.print("\n[bold]生成的图片：[/bold]")
            img_table = Table()
            img_table.add_column("#", style="dim")
            img_table.add_column("类型", style="cyan")
            img_table.add_column("状态", style="green")
            img_table.add_column("URL", style="blue")
            for i, img in enumerate(result.generated_images, 1):
                status = "✅" if img.get("status") == "completed" else "⏳"
                img_table.add_row(
                    str(i),
                    img.get("image_type", "unknown"),
                    status,
                    img.get("url", "URL待生成")[:50] + "...",
                )
            console.print(img_table)

        # 显示生成的视频
        if result.generated_video:
            console.print("\n[bold]生成的视频：[/bold]")
            video = result.generated_video
            console.print(f"  📹 标题: {video.get('title', 'N/A')}")
            console.print(f"  ⏱️ 时长: {video.get('duration', 'N/A')}秒")
            console.print(f"  🔗 URL: {video.get('url', 'URL待生成')}")

        # 显示最终结果
        if result.final_results:
            console.print("\n" + "─" * 40)
            console.print(Panel(
                f"[bold]{result.final_results.get('recommendation', 'N/A')}[/bold]\n\n"
                f"完成时间: {result.final_results.get('completed_at', 'N/A')}",
                title="📊 最终报告",
                border_style="blue",
            ))

    except Exception as e:
        console.print(f"\n[bold red]❌ 执行失败: {e}[/bold red]")
        console.print_exception()


async def quick_start() -> None:
    """快速开始 - 最简示例。"""
    console.print("[bold blue]快速开始示例[/bold blue]\n")

    # 最简配置
    product = Product(
        name="便携蓝牙音箱",
        category=ProductCategory.DIGITAL,
        description="小巧便携，音质出色，续航持久",
    )

    request = GenerationRequest(
        task_type="image_only",  # 仅生成图片，更快
        image_types=["main"],
    )

    console.print(f"商品: {product.name}")
    console.print(f"类目: {product.category.value}")
    console.print("正在生成...\n")

    workflow = ProductVisualWorkflow()
    result = await workflow.run(product, request)

    console.print(f"[green]✅ 完成！生成了 {len(result.generated_images)} 张图片[/green]")


def main() -> None:
    """主函数。"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        asyncio.run(quick_start())
    else:
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()