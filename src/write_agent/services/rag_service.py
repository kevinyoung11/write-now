"""
RAG 服务 - 基于硅基流动 Embedding + 可切换向量库
"""
import json
import re
from typing import Optional

import httpx
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from sqlalchemy import text

from write_agent.core import get_settings, get_logger
from write_agent.core.database import create_app_engine, normalize_database_url
from write_agent.observability import emit_obs_event, obs_scope

logger = get_logger(__name__)
settings = get_settings()

# Chroma 持久化目录，仅作为本地 SQLite 开发兜底。
CHROMA_DIR = settings.chroma_dir
POSTGRES_SCHEMES = ("postgres://", "postgresql://")
VECTOR_TABLE_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _is_postgres_url(database_url: str) -> bool:
    return normalize_database_url(database_url).startswith(POSTGRES_SCHEMES)


def _safe_vector_table_name(table_name: str) -> str:
    if not VECTOR_TABLE_PATTERN.fullmatch(table_name):
        raise ValueError("SUPABASE_VECTOR_TABLE 只能包含字母、数字和下划线，且不能以数字开头")
    return table_name


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in embedding) + "]"


def ensure_pgvector_schema(database_url: str | None = None, table_name: str | None = None) -> None:
    """确保 Supabase/Postgres 已启用 pgvector 并创建素材向量表。"""
    url = database_url or settings.database_url
    if not _is_postgres_url(url):
        return

    table = _safe_vector_table_name(table_name or settings.supabase_vector_table)
    engine = create_app_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id BIGSERIAL PRIMARY KEY,
                    material_id INTEGER NOT NULL UNIQUE REFERENCES materials(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding vector NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_{table}_material_id "
                f"ON {table} (material_id)"
            )
        )


class SiliconFlowEmbeddings(Embeddings):
    """硅基流动 Embedding 实现"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入文档"""
        embeddings = []
        for text in texts:
            embedding = self._embed_single(text)
            embeddings.append(embedding)
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """嵌入查询"""
        return self._embed_single(text)

    def _embed_single(self, text: str) -> list[float]:
        """单个文本嵌入"""
        url = f"{self.base_url}/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": text,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["data"][0]["embedding"]


class EmbeddingService:
    """嵌入服务 - 使用硅基流动 API"""

    def __init__(self):
        self.embeddings = SiliconFlowEmbeddings(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
            model=settings.siliconflow_embedding_model,
        )
        logger.info(f"Embedding 服务初始化完成，使用模型: {settings.siliconflow_embedding_model}")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """获取文本的嵌入向量"""
        return self.embeddings.embed_documents(texts)

    def embed_query(self, query: str) -> list[float]:
        """获取查询的嵌入向量"""
        return self.embeddings.embed_query(query)


class ChromaVectorStore:
    """本地 Chroma fallback，用于 SQLite 开发环境。"""

    def __init__(self, embeddings: Embeddings):
        self.vector_store = Chroma(
            collection_name="materials",
            embedding_function=embeddings,
            persist_directory=CHROMA_DIR,
        )
        logger.info(f"Chroma 向量库初始化完成，持久化目录: {CHROMA_DIR}")

    def add_material(self, material_id: int, content: str, metadata: dict | None = None):
        meta = metadata.copy() if metadata else {}
        meta["material_id"] = material_id
        doc = Document(page_content=content, metadata=meta)
        self.vector_store.add_documents([doc])

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        results = self.vector_store.similarity_search_with_score(query=query, k=top_k)
        retrieved = []
        for doc, score in results:
            material_id = doc.metadata.get("material_id", 0)
            similarity = 1 / (1 + score)
            retrieved.append(
                {
                    "material_id": material_id,
                    "content": doc.page_content,
                    "score": round(similarity, 3),
                }
            )
        return retrieved

    def delete_material(self, material_id: int):
        self.vector_store.delete(where={"material_id": material_id})


class SupabasePgVectorStore:
    """Supabase/Postgres pgvector 素材向量库。"""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        self.database_url = settings.database_url
        self.table_name = _safe_vector_table_name(settings.supabase_vector_table)
        ensure_pgvector_schema(self.database_url, self.table_name)
        self.engine = create_app_engine(self.database_url)
        logger.info(f"Supabase pgvector 向量库初始化完成，表: {self.table_name}")

    def add_material(self, material_id: int, content: str, metadata: dict | None = None):
        embedding = self.embedding_service.embed_query(content)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        embedding_literal = _vector_literal(embedding)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {self.table_name}
                        (material_id, content, metadata, embedding, created_at, updated_at)
                    VALUES
                        (:material_id, :content, CAST(:metadata AS jsonb), CAST(:embedding AS vector), NOW(), NOW())
                    ON CONFLICT (material_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                    """
                ),
                {
                    "material_id": material_id,
                    "content": content,
                    "metadata": metadata_json,
                    "embedding": embedding_literal,
                },
            )

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        query_embedding = _vector_literal(self.embedding_service.embed_query(query))
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        material_id,
                        content,
                        1 - (embedding <=> CAST(:embedding AS vector)) AS score
                    FROM {self.table_name}
                    ORDER BY embedding <=> CAST(:embedding AS vector)
                    LIMIT :top_k
                    """
                ),
                {"embedding": query_embedding, "top_k": top_k},
            ).mappings().all()

        return [
            {
                "material_id": int(row["material_id"]),
                "content": row["content"],
                "score": round(float(row["score"] or 0), 3),
            }
            for row in rows
        ]

    def delete_material(self, material_id: int):
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {self.table_name} WHERE material_id = :material_id"),
                {"material_id": material_id},
            )


class RAGService:
    """RAG 服务 - 使用 Supabase pgvector 或本地 Chroma 向量数据库"""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        backend = settings.rag_vector_backend.strip().lower()
        if backend == "auto":
            backend = "supabase_pgvector" if _is_postgres_url(settings.database_url) else "chroma"

        if backend == "supabase_pgvector":
            self.vector_store = SupabasePgVectorStore(self.embedding_service)
        elif backend == "chroma":
            self.vector_store = ChromaVectorStore(self.embedding_service.embeddings)
        else:
            raise ValueError("RAG_VECTOR_BACKEND 仅支持 auto、supabase_pgvector 或 chroma")

        self.backend = backend
        logger.info(f"RAG 服务初始化完成，backend={backend}")

    def add_material(self, material_id: int, content: str, metadata: dict = None):
        """
        添加素材到向量库

        Args:
            material_id: 素材 ID
            content: 素材内容
            metadata: 元数据
        """
        self.vector_store.add_material(material_id, content, metadata)
        logger.info(f"素材已添加到向量库: material_id={material_id}")

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict]:
        """
        检索相关素材

        Args:
            query: 查询文本
            top_k: 返回条数

        Returns:
            [{"material_id": 1, "content": "...", "score": 0.95}]
        """
        with obs_scope("SVC.RAG.RETRIEVE", "RAG_RETRIEVE"):
            emit_obs_event(
                level="INFO",
                message="svc.rag.search.start",
                payload={"query_len": len(query or ""), "top_k": top_k},
            )
            retrieved = self.vector_store.search(query, top_k)

            logger.info(f"RAG 检索完成，返回 {len(retrieved)} 条结果")
            emit_obs_event(
                level="INFO",
                message="svc.rag.search.done",
                payload={"returned": len(retrieved)},
            )
            return retrieved

    def delete_material(self, material_id: int):
        """从向量库删除素材"""
        self.vector_store.delete_material(material_id)
        logger.info(f"素材已从向量库删除: material_id={material_id}")


# 全局单例
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取 RAG 服务单例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
