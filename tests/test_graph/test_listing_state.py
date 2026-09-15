"""刊登工作流状态定义测试。"""

import typing
from operator import add

from src.graph.listing_state import ListingState
from src.models.listing import ListingProduct, Platform


def _product() -> ListingProduct:
    return ListingProduct(sku="S-1", title="Test Product")


def test_state_defaults() -> None:
    state = ListingState(product=_product(), target_platforms=[Platform.AMAZON])
    assert state.task_id is None
    assert state.blocked_platforms == []
    assert state.errors == []


def test_errors_field_uses_add_reducer() -> None:
    """errors 必须声明 add reducer，否则并行节点同时写 errors 会冲突报错。"""
    hints = typing.get_type_hints(ListingState, include_extras=True)
    metadata = getattr(hints["errors"], "__metadata__", ())
    assert add in metadata


def test_accepts_task_id_and_blocked_platforms() -> None:
    state = ListingState(
        product=_product(),
        task_id=42,
        blocked_platforms=[Platform.EBAY],
    )
    assert state.task_id == 42
    assert state.blocked_platforms == [Platform.EBAY]
