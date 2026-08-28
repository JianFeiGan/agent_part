"""llm_json 统一 JSON 提取工具单测。"""

import json

import pytest

from src.agents.llm_json import extract_json, extract_json_list


class TestExtractJson:
    """extract_json 测试。"""

    def test_pure_json(self) -> None:
        """纯 JSON 文本直接解析。"""
        text = '{"a": 1, "b": "x"}'
        assert extract_json(text) == {"a": 1, "b": "x"}

    def test_fenced_json_block(self) -> None:
        """```json 围栏代码块可解析。"""
        text = '以下是结果：\n```json\n{"theme": "科技感"}\n```\n请参考。'
        assert extract_json(text) == {"theme": "科技感"}

    def test_plain_fence_without_language_tag(self) -> None:
        """无语言标注的 ``` 围栏也可解析。"""
        text = '```\n{"k": "v"}\n```'
        assert extract_json(text) == {"k": "v"}

    def test_json_with_surrounding_text(self) -> None:
        """前后混杂说明文字时截取花括号之间部分。"""
        text = '好的，这是我的方案 {"overall_score": 0.9} 希望有帮助'
        assert extract_json(text) == {"overall_score": 0.9}

    def test_nested_braces(self) -> None:
        """嵌套对象正常解析。"""
        text = '{"outer": {"inner": 1}}'
        assert extract_json(text) == {"outer": {"inner": 1}}

    def test_invalid_json_returns_none(self) -> None:
        """非法 JSON 返回 None。"""
        assert extract_json("这不是 JSON") is None

    def test_empty_text_returns_none(self) -> None:
        """空文本返回 None。"""
        assert extract_json("") is None
        assert extract_json(None) is None  # type: ignore[arg-type]

    def test_non_dict_top_level_returns_none(self) -> None:
        """顶层非对象（如数组）返回 None。"""
        assert extract_json("[1, 2, 3]") is None

    def test_markdown_with_trailing_comma_falls_back(self) -> None:
        """围栏内容非法但正文含合法 JSON 时可兜底。"""
        text = '```json\n{"a": 1,}\n```\n结果: {"b": 2}'
        assert extract_json(text) == {"b": 2}


class TestExtractJsonList:
    """extract_json_list 测试。"""

    def test_pure_list(self) -> None:
        """纯数组文本。"""
        text = json.dumps([{"image_type": "main"}, {"image_type": "scene"}])
        result = extract_json_list(text)
        assert result == [{"image_type": "main"}, {"image_type": "scene"}]

    def test_list_with_surrounding_text(self) -> None:
        """前后混杂说明文字的数组。"""
        text = '生成的提示词如下 [ {"prompt": "p1"} ] 请查收'
        assert extract_json_list(text) == [{"prompt": "p1"}]

    def test_invalid_returns_none(self) -> None:
        """非法内容返回 None。"""
        assert extract_json_list("没有数组") is None

    def test_non_list_top_level_returns_none(self) -> None:
        """顶层非数组返回 None。"""
        assert extract_json_list('{"a": 1}') is None

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ('[{"a": 1}]', [{"a": 1}]),
            ("[]", []),
            ('前缀 [] 后缀', []),
        ],
    )
    def test_parametrized_lists(self, text: str, expected: list) -> None:
        """常见数组形态。"""
        assert extract_json_list(text) == expected
