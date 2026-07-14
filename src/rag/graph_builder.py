"""
Graph RAG 知识图谱自动构建管道。

Description:
    从文档分块中抽取实体和关系，构建知识图谱，
    使用 Leiden 算法进行社区发现，并生成社区摘要。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.models import CommunitySummary, GraphRAGEdge, GraphRAGEntity

logger = logging.getLogger(__name__)


class ExtractedEntity(BaseModel):
    """抽取的实体。

    Attributes:
        name: 实体名称。
        entity_type: 实体类型。
        description: 实体描述。
    """

    name: str = Field(..., description="实体名称")
    entity_type: str = Field(..., description="实体类型")
    description: str = Field(default="", description="实体描述")


class ExtractedRelation(BaseModel):
    """抽取的关系。

    Attributes:
        source_name: 源实体名称。
        target_name: 目标实体名称。
        relationship_type: 关系类型。
        evidence: 关系依据。
    """

    source_name: str = Field(..., description="源实体名称")
    target_name: str = Field(..., description="目标实体名称")
    relationship_type: str = Field(..., description="关系类型")
    evidence: str = Field(default="", description="关系依据")


class GraphBuilderPipeline:
    """Graph RAG 知识图谱自动构建管道。

    从文档分块中抽取实体和关系，去重后持久化到数据库，
    然后使用 Leiden 算法进行社区发现，最后生成社区摘要。

    Example:
        >>> pipeline = GraphBuilderPipeline()
        >>> result = await pipeline.build_from_chunks(
        ...     session, chunks=[...], category="digital"
        ... )
    """

    def __init__(self) -> None:
        """初始化构建管道。"""
        self.settings = get_settings()
        self._llm: Any = None

    async def _get_llm(self) -> Any:
        """懒加载 LLM 客户端。

        Returns:
            LLM 客户端实例。
        """
        if self._llm is None:
            settings = self.settings
            if settings.llm_provider == "qwen":
                from src.clients.qwen_llm_client import get_qwen_llm

                self._llm = get_qwen_llm(settings=settings, temperature=0)
            elif settings.llm_provider == "dashscope" and settings.effective_dashscope_api_key:
                from langchain_community.chat_models import ChatTongyi

                self._llm = ChatTongyi(
                    model=settings.llm_model,
                    dashscope_api_key=settings.effective_dashscope_api_key,
                    temperature=0,
                )
            else:
                from src.clients.qwen_llm_client import get_qwen_llm

                self._llm = get_qwen_llm(settings=settings, temperature=0)
        return self._llm

    async def extract_entities_from_text(
        self,
        text: str,
        entity_types: list[str] | None = None,
    ) -> list[ExtractedEntity]:
        """从文本中抽取实体。

        使用 LLM structured output 抽取实体，失败时返回空列表。

        Args:
            text: 输入文本。
            entity_types: 目标实体类型列表（可选）。

        Returns:
            抽取的实体列表。
        """
        default_types = entity_types or ["产品", "品牌", "技术", "属性", "风格", "场景"]
        prompt = (
            f"请从以下文本中抽取实体。\n\n"
            f"文本：{text}\n\n"
            f"目标实体类型：{', '.join(default_types)}\n\n"
            f"请以 JSON 数组格式返回实体列表，每个实体包含 name、type、description 字段。\n"
            f'示例：[{{"name": "iPhone 15", "type": "产品", "description": "苹果智能手机"}}]\n'
            f"只返回 JSON 数组，不要包含其他内容。"
        )

        try:
            llm = await self._get_llm()
            response = await llm.ainvoke(prompt)
            return self._parse_entities(response.content)
        except Exception as e:
            logger.warning(f"实体抽取失败: {e}")
            return []

    async def extract_relations_from_text(
        self,
        text: str,
        entities: list[ExtractedEntity],
    ) -> list[ExtractedRelation]:
        """从文本中抽取实体间关系。

        使用 LLM structured output 抽取关系，失败时返回空列表。

        Args:
            text: 输入文本。
            entities: 已抽取的实体列表。

        Returns:
            抽取的关系列表。
        """
        if not entities:
            return []

        entity_info = ", ".join([f"{e.name}({e.entity_type})" for e in entities])
        prompt = (
            f"请从以下文本中抽取实体之间的关系。\n\n"
            f"文本：{text}\n"
            f"已知实体：{entity_info}\n\n"
            f"请以 JSON 数组格式返回关系列表，每个关系包含 source、target、type、evidence 字段。\n"
            f'示例：[{{"source": "iPhone 15", "target": "苹果", "type": "生产", "evidence": "苹果推出iPhone 15"}}]\n'
            f"只返回 JSON 数组，不要包含其他内容。"
        )

        try:
            llm = await self._get_llm()
            response = await llm.ainvoke(prompt)
            return self._parse_relations(response.content)
        except Exception as e:
            logger.warning(f"关系抽取失败: {e}")
            return []

    def _parse_entities(self, content: str) -> list[ExtractedEntity]:
        """解析 LLM 返回的实体 JSON。

        Args:
            content: LLM 返回的文本内容。

        Returns:
            解析后的实体列表。
        """
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return []

        entities: list[ExtractedEntity] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            entity_type = item.get("type", item.get("entity_type", "")).strip()
            if not name or not entity_type:
                continue
            entities.append(
                ExtractedEntity(
                    name=name,
                    entity_type=entity_type,
                    description=item.get("description", ""),
                )
            )
        return entities

    def _parse_relations(self, content: str) -> list[ExtractedRelation]:
        """解析 LLM 返回的关系 JSON。

        Args:
            content: LLM 返回的文本内容。

        Returns:
            解析后的关系列表。
        """
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return []

        relations: list[ExtractedRelation] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            source = item.get("source", item.get("source_name", "")).strip()
            target = item.get("target", item.get("target_name", "")).strip()
            rel_type = item.get("type", item.get("relationship_type", "")).strip()
            if not source or not target or not rel_type:
                continue
            relations.append(
                ExtractedRelation(
                    source_name=source,
                    target_name=target,
                    relationship_type=rel_type,
                    evidence=item.get("evidence", ""),
                )
            )
        return relations

    def detect_communities_leiden(
        self,
        entities: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        max_communities: int = 10,
    ) -> list[dict[str, Any]]:
        """使用 Leiden 算法进行社区发现。

        当 python-igraph 或 leidenalg 不可用时，回退到简单连通分量算法。

        Args:
            entities: 实体列表，每个实体包含 id 和 name。
            edges: 边列表，每条边包含 source_id 和 target_id。
            max_communities: 最大社区数。

        Returns:
            社区列表，每个社区包含 community_id、entity_ids、level。
        """
        if not entities:
            return []

        entity_id_map = {e["id"]: idx for idx, e in enumerate(entities)}
        n = len(entities)

        try:
            import igraph as ig

            g = ig.Graph(n=n, directed=False)
            for edge in edges:
                src_idx = entity_id_map.get(edge["source_id"])
                tgt_idx = entity_id_map.get(edge["target_id"])
                if src_idx is not None and tgt_idx is not None:
                    g.add_edge(src_idx, tgt_idx)

            try:
                import leidenalg

                partition = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition)
                communities: list[dict[str, Any]] = []
                for comm_idx, community in enumerate(partition):
                    if comm_idx >= max_communities:
                        break
                    entity_ids = [entities[v]["id"] for v in community]
                    communities.append(
                        {
                            "community_id": f"comm_{comm_idx}",
                            "entity_ids": entity_ids,
                            "level": 0,
                        }
                    )
                return communities
            except ImportError:
                logger.info("leidenalg 不可用，回退到连通分量算法")
                return self._fallback_communities(g, entities, max_communities)

        except ImportError:
            logger.info("igraph 不可用，回退到简单连通分量算法")
            return self._fallback_communities_simple(entities, edges, max_communities)

    def _fallback_communities(
        self,
        graph: Any,
        entities: list[dict[str, Any]],
        max_communities: int,
    ) -> list[dict[str, Any]]:
        """igraph 可用但 leidenalg 不可用时的连通分量回退。

        Args:
            graph: igraph 图对象。
            entities: 实体列表。
            max_communities: 最大社区数。

        Returns:
            社区列表。
        """
        components = graph.connected_components()
        communities: list[dict[str, Any]] = []
        for comm_idx, component in enumerate(components):
            if comm_idx >= max_communities:
                break
            entity_ids = [entities[v]["id"] for v in component]
            communities.append(
                {
                    "community_id": f"comm_{comm_idx}",
                    "entity_ids": entity_ids,
                    "level": 0,
                }
            )
        return communities

    def _fallback_communities_simple(
        self,
        entities: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        max_communities: int,
    ) -> list[dict[str, Any]]:
        """igraph 不可用时的简单连通分量回退。

        Args:
            entities: 实体列表。
            edges: 边列表。
            max_communities: 最大社区数。

        Returns:
            社区列表。
        """
        entity_ids = {e["id"] for e in entities}
        adjacency: dict[Any, set[Any]] = {eid: set() for eid in entity_ids}

        for edge in edges:
            src = edge.get("source_id")
            tgt = edge.get("target_id")
            if src in adjacency and tgt in adjacency:
                adjacency[src].add(tgt)
                adjacency[tgt].add(src)

        visited: set[Any] = set()
        communities: list[dict[str, Any]] = []
        comm_idx = 0

        for entity_id in entity_ids:
            if entity_id in visited:
                continue
            if comm_idx >= max_communities:
                break

            component: list[Any] = []
            stack = [entity_id]
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        stack.append(neighbor)

            communities.append(
                {
                    "community_id": f"comm_{comm_idx}",
                    "entity_ids": component,
                    "level": 0,
                }
            )
            comm_idx += 1

        return communities

    async def generate_community_summary(
        self,
        entity_names: list[str],
        edge_descriptions: list[str],
    ) -> str:
        """使用 LLM 生成社区摘要。

        Args:
            entity_names: 社区内实体名称列表。
            edge_descriptions: 社区内边描述列表。

        Returns:
            社区摘要文本。
        """
        if not entity_names:
            return ""

        entities_text = ", ".join(entity_names)
        edges_text = "\n".join(edge_descriptions) if edge_descriptions else "无关系信息"

        prompt = (
            f"请根据以下实体和关系信息，生成一段简洁的社区摘要。\n\n"
            f"实体：{entities_text}\n\n"
            f"关系：\n{edges_text}\n\n"
            f"请用1-3句话概括这些实体之间的关系和共同特征。"
        )

        try:
            llm = await self._get_llm()
            response = await llm.ainvoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.warning(f"社区摘要生成失败: {e}")
            return f"包含实体: {entities_text}"

    async def build_from_chunks(
        self,
        session: AsyncSession,
        chunks: list[dict[str, Any]],
        category: str,
        *,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """从文档分块构建知识图谱的完整流程。

        流程：实体抽取 -> 关系抽取 -> 去重 -> 持久化 -> 社区发现 -> 社区摘要 -> 持久化

        Args:
            session: 数据库会话。
            chunks: 文档分块列表，每个包含 content 字段。
            category: 商品类目。
            tenant_id: 租户 ID（可选）。

        Returns:
            构建结果统计信息。
        """
        # 1. 实体抽取
        all_entities: list[ExtractedEntity] = []
        all_relations: list[ExtractedRelation] = []

        for chunk in chunks:
            content = chunk.get("content", "")
            if not content:
                continue

            entities = await self.extract_entities_from_text(content)
            all_entities.extend(entities)

            if entities:
                relations = await self.extract_relations_from_text(content, entities)
                all_relations.extend(relations)

        # 2. 去重
        seen_names: dict[str, ExtractedEntity] = {}
        for entity in all_entities:
            key = f"{entity.name}:{entity.entity_type}"
            if key not in seen_names:
                seen_names[key] = entity
        unique_entities = list(seen_names.values())

        # 3. 持久化实体
        entity_name_to_id: dict[str, int] = {}
        for entity in unique_entities:
            stmt = insert(GraphRAGEntity).values(
                tenant_id=tenant_id,
                name=entity.name,
                entity_type=entity.entity_type,
                category=category,
                description=entity.description,
            )
            stmt = stmt.on_conflict_do_nothing()
            await session.execute(stmt)

        # 查询已持久化的实体 ID
        result = await session.execute(
            select(GraphRAGEntity.id, GraphRAGEntity.name).where(
                GraphRAGEntity.category == category,
                GraphRAGEntity.tenant_id == tenant_id
                if tenant_id
                else GraphRAGEntity.tenant_id.is_(None),
            )
        )
        for row in result.all():
            entity_name_to_id[row.name] = row.id

        # 4. 持久化边
        persisted_edges: list[dict[str, Any]] = []
        for relation in all_relations:
            source_id = entity_name_to_id.get(relation.source_name)
            target_id = entity_name_to_id.get(relation.target_name)
            if source_id and target_id and source_id != target_id:
                stmt = insert(GraphRAGEdge).values(
                    tenant_id=tenant_id,
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relationship_type=relation.relationship_type,
                    category=category,
                    evidence=relation.evidence,
                )
                stmt = stmt.on_conflict_do_nothing()
                await session.execute(stmt)
                persisted_edges.append(
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "relationship_type": relation.relationship_type,
                    }
                )

        await session.flush()

        # 5. 社区发现
        entity_dicts = [{"id": eid, "name": name} for name, eid in entity_name_to_id.items()]
        communities = self.detect_communities_leiden(
            entity_dicts,
            persisted_edges,
            max_communities=self.settings.graph_rag_max_communities,
        )

        # 6. 生成社区摘要并持久化
        for community in communities:
            comm_entity_ids = community["entity_ids"]
            comm_entity_names = [
                name for name, eid in entity_name_to_id.items() if eid in comm_entity_ids
            ]

            # 构建边描述
            comm_edge_ids = set(comm_entity_ids)
            edge_descriptions = []
            for edge in persisted_edges:
                if edge["source_id"] in comm_edge_ids and edge["target_id"] in comm_edge_ids:
                    src_name = next(
                        (n for n, i in entity_name_to_id.items() if i == edge["source_id"]), ""
                    )
                    tgt_name = next(
                        (n for n, i in entity_name_to_id.items() if i == edge["target_id"]), ""
                    )
                    edge_descriptions.append(
                        f"{src_name} --[{edge['relationship_type']}]--> {tgt_name}"
                    )

            summary = await self.generate_community_summary(comm_entity_names, edge_descriptions)

            stmt = insert(CommunitySummary).values(
                tenant_id=tenant_id,
                category=category,
                community_id=community["community_id"],
                level=community["level"],
                entity_ids=comm_entity_ids,
                title=f"社区 {community['community_id']}",
                summary=summary,
            )
            stmt = stmt.on_conflict_do_nothing()
            await session.execute(stmt)

        await session.flush()

        result_info = {
            "entity_count": len(unique_entities),
            "relation_count": len(persisted_edges),
            "community_count": len(communities),
            "category": category,
        }

        logger.info(
            f"Graph RAG 构建完成: category='{category}', "
            f"entities={result_info['entity_count']}, "
            f"relations={result_info['relation_count']}, "
            f"communities={result_info['community_count']}"
        )

        return result_info


_graph_builder: GraphBuilderPipeline | None = None


def get_graph_builder() -> GraphBuilderPipeline:
    """获取 GraphBuilderPipeline 单例。

    Returns:
        GraphBuilderPipeline 实例。
    """
    global _graph_builder
    if _graph_builder is None:
        _graph_builder = GraphBuilderPipeline()
    return _graph_builder
