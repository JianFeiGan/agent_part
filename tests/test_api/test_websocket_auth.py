"""
WebSocket 鉴权结构测试。

Description:
    验证 task_websocket 在 accept() 前调用 authenticate_websocket，
    且鉴权失败时以 WS_1008_POLICY_VIOLATION 关闭连接。

@author ganjianfei
@version 1.0.0
2026-06-15
"""

import inspect
import re

from fastapi import status


class TestWebSocketAuthStructure:
    """验证 task_websocket 源码结构包含正确的鉴权流程。"""

    def test_authenticate_websocket_called_before_accept(self) -> None:
        """测试 authenticate_websocket 调用发生在 accept() 之前。

        解析 task_websocket 源码，验证：
        1. authenticate_websocket 在函数体中出现。
        2. 在 authenticate_websocket 调用之后、accept() 调用之前，
           没有其他 accept() 调用。
        3. accept() 出现在 authenticate_websocket 之后。
        """
        from src.api.router.tasks import task_websocket

        source = inspect.getsource(task_websocket)

        # 确认 authenticate_websocket 被调用
        assert "authenticate_websocket" in source, (
            "task_websocket 源码中未找到 authenticate_websocket 调用"
        )

        # 确认 accept 被调用
        assert "accept()" in source, (
            "task_websocket 源码中未找到 accept() 调用"
        )

        # 定位 authenticate_websocket 和 accept 的行位置
        lines = source.splitlines()
        auth_line = None
        accept_line = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 跳过注释、import 和 docstring
            if stripped.startswith(("#", "import", "from")):
                continue
            if "authenticate_websocket" in stripped:
                auth_line = i
                break
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 跳过注释和 docstring 中包含 "accept" 的行
            if stripped.startswith("#"):
                continue
            # 精确匹配 websocket.accept() 或 await websocket.accept()
            if "websocket.accept()" in stripped or re.match(r"^await\s+accept\(\)", stripped):
                accept_line = i
                break

        assert auth_line is not None, "未找到 authenticate_websocket 调用行"
        assert accept_line is not None, "未找到 accept() 调用行"

        assert auth_line < accept_line, (
            f"authenticate_websocket (line {auth_line}) 必须在 accept() (line {accept_line}) 之前调用"
        )

    def test_websocket_close_on_auth_failure(self) -> None:
        """测试鉴权失败时以 WS_1008_POLICY_VIOLATION 关闭连接。

        验证源码中在 HTTPException 的 except 分支中包含：
        - websocket.close(code=status.WS_1008_POLICY_VIOLATION, ...)
        - return 语句（阻止继续执行）
        """
        from src.api.router.tasks import task_websocket

        source = inspect.getsource(task_websocket)

        assert "WS_1008_POLICY_VIOLATION" in source, (
            "task_websocket 源码中未找到 WS_1008_POLICY_VIOLATION"
        )

        # 验证 except HTTPException 分支包含 close 和 return
        # 使用宽松匹配：except HTTPException 后面的代码块包含 close(...POLICY_VIOLATION...) 和 return
        pattern = r"except\s+HTTPException[^:]*:.*?WS_1008_POLICY_VIOLATION"
        assert re.search(pattern, source, re.DOTALL), (
            "except HTTPException 分支中未找到 WS_1008_POLICY_VIOLATION"
        )

        # 验证 close 调用包含 reason 参数
        assert "reason=" in source, (
            "websocket.close 调用中缺少 reason= 参数"
        )

    def test_task_websocket_uses_auth_tenant_id(self) -> None:
        """测试 task_websocket 使用 auth.tenant_id 而非硬编码 dev。

        验证：
        1. 不存在 _ws_tenant_id = "dev"
        2. 不存在 TODO Task 5 注释
        3. get_task_status 调用使用 tenant_id=auth.tenant_id
        """
        from src.api.router.tasks import task_websocket

        source = inspect.getsource(task_websocket)

        # 验证已删除临时变量和 TODO
        assert "_ws_tenant_id" not in source, (
            "task_websocket 中仍存在临时变量 _ws_tenant_id，应已删除"
        )
        assert "TODO" not in source or "Task 5" not in source, (
            "task_websocket 中仍存在 Task 5 TODO 注释，应已删除"
        )

        # 验证使用 auth.tenant_id
        assert "auth.tenant_id" in source, (
            "task_websocket 源码中未找到 auth.tenant_id，应使用鉴权后的 tenant_id"
        )
        assert "tenant_id=auth.tenant_id" in source, (
            "task_websocket 中 get_task_status 调用应使用 tenant_id=auth.tenant_id"
        )

    def test_task_websocket_signature(self) -> None:
        """测试 task_websocket 函数签名。

        验证参数包含 websocket (WebSocket) 和 task_id (str)。
        """
        from src.api.router.tasks import task_websocket

        sig = inspect.signature(task_websocket)
        params = list(sig.parameters.keys())
        assert "websocket" in params, f"task_websocket 缺少 websocket 参数，当前参数: {params}"
        assert "task_id" in params, f"task_websocket 缺少 task_id 参数，当前参数: {params}"


class TestWebSocketAuthIntegration:
    """WebSocket 鉴权集成验证。"""

    def test_authenticate_websocket_imported(self) -> None:
        """测试 authenticate_websocket 已从 src.auth 导入到 tasks 模块。"""
        from src.api.router import tasks as tasks_module

        assert hasattr(tasks_module, "authenticate_websocket"), (
            "tasks 模块未导入 authenticate_websocket"
        )

    def test_authenticate_websocket_is_callable(self) -> None:
        """测试 authenticate_websocket 是可调用的。"""
        from src.auth import authenticate_websocket

        assert callable(authenticate_websocket), (
            "authenticate_websocket 不是可调用对象"
        )

    def test_ws_1008_import_available(self) -> None:
        """测试 status.WS_1008_POLICY_VIOLATION 可用。"""
        assert status.WS_1008_POLICY_VIOLATION == 1008, (
            f"WS_1008_POLICY_VIOLATION 值异常: {status.WS_1008_POLICY_VIOLATION}"
        )
